"""RooWifi binary sensor platform."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import RoowifiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _val(data: dict, key: str) -> int:
    return int((data.get(key) or {}).get("value", 0))


@dataclass(frozen=True)
class RoowifiBinarySensorDescription(BinarySensorEntityDescription):
    rx: str = "r0"
    mask: int | None = None   # None = treat whole value as bool


BINARY_SENSORS: tuple[RoowifiBinarySensorDescription, ...] = (
    # r0 = Bumps & Wheel Drops bitmask (OI packet 7)
    # bit0 = bump right, bit1 = bump left, bit2 = wheel drop right, bit3 = wheel drop left
    RoowifiBinarySensorDescription(
        key="bump_right",
        name="Bumper Right",
        device_class=BinarySensorDeviceClass.PROBLEM,
        rx="r0",
        mask=0x01,
    ),
    RoowifiBinarySensorDescription(
        key="bump_left",
        name="Bumper Left",
        device_class=BinarySensorDeviceClass.PROBLEM,
        rx="r0",
        mask=0x02,
    ),
    RoowifiBinarySensorDescription(
        key="wheel_drop_right",
        name="Wheel Drop Right",
        device_class=BinarySensorDeviceClass.PROBLEM,
        rx="r0",
        mask=0x04,
    ),
    RoowifiBinarySensorDescription(
        key="wheel_drop_left",
        name="Wheel Drop Left",
        device_class=BinarySensorDeviceClass.PROBLEM,
        rx="r0",
        mask=0x08,
    ),
    RoowifiBinarySensorDescription(
        key="wall",
        name="Wall Sensor",
        rx="r1",
    ),
    RoowifiBinarySensorDescription(
        key="cliff_left",
        name="Cliff Left",
        device_class=BinarySensorDeviceClass.PROBLEM,
        rx="r2",
    ),
    RoowifiBinarySensorDescription(
        key="cliff_front_left",
        name="Cliff Front Left",
        device_class=BinarySensorDeviceClass.PROBLEM,
        rx="r3",
    ),
    RoowifiBinarySensorDescription(
        key="cliff_front_right",
        name="Cliff Front Right",
        device_class=BinarySensorDeviceClass.PROBLEM,
        rx="r4",
    ),
    RoowifiBinarySensorDescription(
        key="cliff_right",
        name="Cliff Right",
        device_class=BinarySensorDeviceClass.PROBLEM,
        rx="r5",
    ),
    RoowifiBinarySensorDescription(
        key="virtual_wall",
        name="Virtual Wall",
        rx="r6",
    ),
    RoowifiBinarySensorDescription(
        key="dirt_detect",
        name="Dirt Detect",
        rx="r8",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoowifiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RoowifiBinarySensor(coordinator, entry, desc) for desc in BINARY_SENSORS
    )


class RoowifiBinarySensor(
    CoordinatorEntity[RoowifiDataUpdateCoordinator], BinarySensorEntity
):
    """A binary sensor reading from the RooWifi module."""

    _attr_has_entity_name = True
    entity_description: RoowifiBinarySensorDescription

    def __init__(
        self,
        coordinator: RoowifiDataUpdateCoordinator,
        entry: ConfigEntry,
        description: RoowifiBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> dict:
        return self.coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        if not self.coordinator.data:
            return None
        raw = _val(self.coordinator.data, self.entity_description.rx)
        mask = self.entity_description.mask
        if mask is not None:
            return bool(raw & mask)
        return bool(raw)
