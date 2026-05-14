"""DataUpdateCoordinator for RooWifi."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, RoowifiClient
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


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

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Roomba",
            "manufacturer": "iRobot",
            "model": "Roomba 600-serie (RooWifi)",
        }

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.async_get_sensors()
        except CannotConnect as err:
            raise UpdateFailed(f"Cannot reach RooWifi: {err}") from err
