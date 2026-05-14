"""RooWifi sensor platform."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CHARGING_STATES, DOMAIN
from .coordinator import RoowifiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _val(data: dict, key: str) -> int:
    return int((data.get(key) or {}).get("value", 0))


def _signed16(v: int) -> int:
    return v - 65536 if v > 32767 else v


def _signed8(v: int) -> int:
    return v - 256 if v > 127 else v


@dataclass(frozen=True)
class RoowifiSensorDescription(SensorEntityDescription):
    fn: Callable[[dict], object] = lambda _: None


SENSORS: tuple[RoowifiSensorDescription, ...] = (
    RoowifiSensorDescription(
        key="battery",
        name="Battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        fn=lambda d: (
            min(100, round(_val(d, "r18") / _val(d, "r19") * 100))
            if _val(d, "r19") > 0 else 0
        ),
    ),
    RoowifiSensorDescription(
        key="voltage",
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        fn=lambda d: round(_val(d, "r15") / 1000, 2),
    ),
    RoowifiSensorDescription(
        key="current",
        name="Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        fn=lambda d: _signed16(_val(d, "r16")),
    ),
    RoowifiSensorDescription(
        key="temperature",
        name="Battery Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        fn=lambda d: _signed8(_val(d, "r17")),
    ),
    RoowifiSensorDescription(
        key="charging_state",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "not_charging",
            "reconditioning",
            "full_charging",
            "trickle_charging",
            "waiting",
            "charging_fault",
        ],
        translation_key="charging_state",
        fn=lambda d: CHARGING_STATES.get(_val(d, "r14")),
    ),
    RoowifiSensorDescription(
        key="distance",
        name="Distance",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        fn=lambda d: _signed16(_val(d, "r12")),
    ),
    RoowifiSensorDescription(
        key="angle",
        name="Angle",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°",
        fn=lambda d: _signed16(_val(d, "r13")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoowifiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RoowifiSensor(coordinator, entry, desc) for desc in SENSORS
    )


class RoowifiSensor(CoordinatorEntity[RoowifiDataUpdateCoordinator], SensorEntity):
    """A sensor reading from the RooWifi module."""

    _attr_has_entity_name = True
    entity_description: RoowifiSensorDescription

    def __init__(
        self,
        coordinator: RoowifiDataUpdateCoordinator,
        entry: ConfigEntry,
        description: RoowifiSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> dict:
        return self.coordinator.device_info

    @property
    def native_value(self) -> object:
        if not self.coordinator.data:
            return None
        try:
            return self.entity_description.fn(self.coordinator.data)
        except (ZeroDivisionError, TypeError, ValueError):
            return None
