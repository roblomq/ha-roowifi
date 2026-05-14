"""RooWifi vacuum platform."""
from __future__ import annotations

import logging

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import CannotConnect
from .const import DOMAIN
from .coordinator import RoowifiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_STATE_CLEANING = "cleaning"
_STATE_DOCKED = "docked"
_STATE_IDLE = "idle"
_STATE_PAUSED = "paused"
_STATE_RETURNING = "returning"

_FEATURES = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.CLEAN_SPOT
    | VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.STATE
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoowifiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([RoowifiVacuum(coordinator)])


def _val(data: dict, key: str) -> int:
    return int((data.get(key) or {}).get("value", 0))


class RoowifiVacuum(CoordinatorEntity[RoowifiDataUpdateCoordinator], StateVacuumEntity):
    """Roomba vacuum entity backed by RooWifi polling."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = _FEATURES

    def __init__(self, coordinator: RoowifiDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator._entry.entry_id}_vacuum"
        self._internal_state = _STATE_IDLE

    @property
    def device_info(self) -> dict:
        return self.coordinator.device_info

    @property
    def state(self) -> str:
        data = self.coordinator.data or {}
        if _val(data, "r14") > 0:
            # Any non-zero charging state means the robot is on the dock
            return _STATE_DOCKED
        return self._internal_state

    @property
    def battery_level(self) -> int | None:
        data = self.coordinator.data or {}
        charge = _val(data, "r18")
        capacity = _val(data, "r19")
        if capacity > 0:
            return min(100, round(charge / capacity * 100))
        return None

    async def _send(self, new_state: str, coro) -> None:
        prev = self._internal_state
        self._internal_state = new_state
        self.async_write_ha_state()
        try:
            await coro
        except CannotConnect as err:
            _LOGGER.error("Roomba command failed: %s", err)
            self._internal_state = prev
            self.async_write_ha_state()
            return
        await self.coordinator.async_refresh()

    async def async_start(self) -> None:
        await self._send(_STATE_CLEANING, self.coordinator.client.async_start_clean())

    async def async_pause(self) -> None:
        await self._send(_STATE_PAUSED, self.coordinator.client.async_stop())

    async def async_stop(self, **kwargs) -> None:
        await self._send(_STATE_IDLE, self.coordinator.client.async_stop())

    async def async_return_to_base(self, **kwargs) -> None:
        await self._send(_STATE_RETURNING, self.coordinator.client.async_dock())

    async def async_clean_spot(self, **kwargs) -> None:
        await self._send(_STATE_CLEANING, self.coordinator.client.async_clean_spot())
