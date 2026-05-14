"""RooWifi button platform — manual driving and motor control via TCP gateway."""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import RoowifiClient
from .const import DOMAIN
from .coordinator import RoowifiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Driving parameters
_SPEED     = 200    # mm/s — forward/backward
_SPIN_SPD  = 150    # mm/s — spin-in-place
_STRAIGHT  = 32768  # special OI radius value for straight line
_SPIN_L    = 1      # counter-clockwise (OI spec: radius +1 = left)
_SPIN_R    = -1     # clockwise         (OI spec: radius -1 = right)
_MOVE_TIME = 0.8    # seconds per forward/backward press
_SPIN_TIME = 0.6    # seconds per spin press (~90° at _SPIN_SPD mm/s)


@dataclass(frozen=True)
class RoowifiButtonDescription(ButtonEntityDescription):
    action: Callable[[RoowifiClient], Awaitable[None]] = field(
        default=lambda _: __import__("asyncio").sleep(0)
    )


BUTTONS: tuple[RoowifiButtonDescription, ...] = (
    RoowifiButtonDescription(
        key="move_forward",
        name="Move Forward",
        icon="mdi:arrow-up-bold",
        action=lambda c: c.async_drive(_SPEED, _STRAIGHT, _MOVE_TIME),
    ),
    RoowifiButtonDescription(
        key="move_backward",
        name="Move Backward",
        icon="mdi:arrow-down-bold",
        action=lambda c: c.async_drive(-_SPEED, _STRAIGHT, _MOVE_TIME),
    ),
    RoowifiButtonDescription(
        key="spin_left",
        name="Spin Left",
        icon="mdi:rotate-left",
        action=lambda c: c.async_drive(_SPIN_SPD, _SPIN_L, _SPIN_TIME),
    ),
    RoowifiButtonDescription(
        key="spin_right",
        name="Spin Right",
        icon="mdi:rotate-right",
        action=lambda c: c.async_drive(_SPIN_SPD, _SPIN_R, _SPIN_TIME),
    ),
    RoowifiButtonDescription(
        key="stop_drive",
        name="Stop Driving",
        icon="mdi:stop-circle-outline",
        action=lambda c: c.async_drive(0, _STRAIGHT, 0),
    ),
    RoowifiButtonDescription(
        key="motors_on",
        name="Cleaning Motors On",
        icon="mdi:fan",
        action=lambda c: c.async_motors(side=True, vacuum=True, main=True),
    ),
    RoowifiButtonDescription(
        key="motors_off",
        name="Cleaning Motors Off",
        icon="mdi:fan-off",
        action=lambda c: c.async_motors(side=False, vacuum=False, main=False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: RoowifiDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        RoowifiButton(coordinator, entry, desc) for desc in BUTTONS
    )


class RoowifiButton(ButtonEntity):
    """A one-shot button that sends a command to the Roomba via TCP gateway."""

    _attr_has_entity_name = True
    entity_description: RoowifiButtonDescription

    def __init__(
        self,
        coordinator: RoowifiDataUpdateCoordinator,
        entry: ConfigEntry,
        description: RoowifiButtonDescription,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @property
    def device_info(self) -> dict:
        return self._coordinator.device_info

    async def async_press(self) -> None:
        try:
            await self.entity_description.action(self._coordinator.client)
        except Exception as err:
            _LOGGER.error(
                "Button '%s' failed: %s", self.entity_description.key, err
            )
