"""DataUpdateCoordinator for RooWifi."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, RoowifiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Number of consecutive poll failures allowed before entities go unavailable.
# At 15 s intervals this gives ~45 s of grace time (e.g. while the Roomba
# is sleeping on the dock and the RooWifi responds slowly or not at all).
_MAX_FAILURES = 3


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

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Roomba",
            "manufacturer": "iRobot",
            "model": "Roomba 600 series (RooWifi)",
        }

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
