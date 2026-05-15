"""DataUpdateCoordinator for RooWifi."""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, RoowifiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Number of consecutive poll failures allowed before entities go unavailable.
# At 15 s intervals this gives ~45 s of grace time (e.g. while the Roomba
# is sleeping on the dock and the RooWifi responds slowly or not at all).
_MAX_FAILURES = 3

# Send a wake byte every 3 minutes while docked to prevent the Roomba from
# entering deep sleep, which makes it unresponsive to remote commands.
_KEEP_ALIVE_INTERVAL = timedelta(minutes=3)


class RoowifiDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that polls RooWifi every scan_interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: RoowifiClient,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self._entry = entry
        self._consecutive_failures = 0
        self._keep_alive_unsub: Callable | None = None

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Roomba",
            "manufacturer": "iRobot",
            "model": "Roomba 600 series (RooWifi)",
        }

    def start_keep_alive(self) -> None:
        """Start periodic keep-alive to prevent deep sleep while docked."""
        self._keep_alive_unsub = async_track_time_interval(
            self.hass, self._async_keep_alive, _KEEP_ALIVE_INTERVAL
        )
        _LOGGER.debug("Keep-alive timer started (interval: %s)", _KEEP_ALIVE_INTERVAL)

    def stop_keep_alive(self) -> None:
        """Stop the keep-alive timer."""
        if self._keep_alive_unsub:
            self._keep_alive_unsub()
            self._keep_alive_unsub = None

    async def _async_keep_alive(self, _now=None) -> None:
        """Send opcode 128 via TCP while docked to reset the OI sleep timer."""
        if not self.data:
            return
        charging_state = int((self.data.get("r14") or {}).get("value", 0))
        if charging_state == 0:
            return  # Not docked — don't interfere with cleaning or driving
        try:
            await self.client._tcp_send(bytes([128]))
            _LOGGER.debug("Keep-alive sent (charging state: %d)", charging_state)
        except Exception as err:
            _LOGGER.debug("Keep-alive failed (non-critical): %s", err)

    async def _async_update_data(self) -> dict:
        try:
            data = await self.client.async_get_sensors()
            if self._consecutive_failures > 0:
                _LOGGER.debug(
                    "RooWifi connection restored after %d failed poll(s)",
                    self._consecutive_failures,
                )
            self._consecutive_failures = 0
            return data

        except CannotConnect as err:
            self._consecutive_failures += 1

            if self._consecutive_failures < _MAX_FAILURES and self.data is not None:
                # Keep last known data and stay available during brief outages
                # (e.g. Roomba sleeping in dock, RooWifi temporarily slow).
                _LOGGER.warning(
                    "RooWifi poll failed (%d/%d), keeping last data: %s",
                    self._consecutive_failures,
                    _MAX_FAILURES,
                    err,
                )
                return self.data

            raise UpdateFailed(
                f"RooWifi unreachable after {self._consecutive_failures} attempts: {err}"
            ) from err
