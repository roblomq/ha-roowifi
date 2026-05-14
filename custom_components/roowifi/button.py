"""RooWifi button platform — manual driving and motor control."""
from __future__ import annotations

import asyncio
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

# Velocity and radius constants for DRIVE (opcode 137)
_SPEED = 200       # mm/s — forward/backward speed
_SPIN = 150        # mm/s — spin-in-place speed
_STRAIGHT = 32768  # special radius value for straight driving
_SPIN_LEFT = -1    # spin counter-clockwise
_SPIN_RIGHT = 1    # spin clockwise
_MOVE_TIME = 0.8   # seconds per forward/backward button press
_SPIN_TIME = 0.6   # seconds per spin press (~90° at _SPIN mm/s)


@dataclass(frozen=True)
class RoowifiButtonDescription(ButtonEntityDescription):
    action: Callable[[RoowifiClient], Awaitable[None]] = field(
        default=lambda _: asyncio.sleep(0)
    )


def _signed16(v: int) -> tuple[int, int]:
    """Split a signed 16-bit integer into (high_byte, low_byte)."""
    u = v if v >= 0 else v + 65536
    return (u >> 8) & 0xFF, u & 0xFF


async def _drive(client: RoowifiClient, velocity: int, radius: int, duration: float) -> None:
    """Wake, enter Safe mode, drive for `duration` seconds, then stop."""
    await client.async_send_opcode(128)   # Wake
    await asyncio.sleep(0.3)
    await client.async_send_opcode(131)   # Safe mode
    await asyncio.sleep(0.2)

    v_hi, v_lo = _signed16(velocity)
    r_hi, r_lo = _signed16(radius)
    await client.async_send_opcode_with_params(137, [v_hi, v_lo, r_hi, r_lo])
    await asyncio.sleep(duration)

    # Stop: velocity 0, radius straight
    s_hi, s_lo = _signed16(0)
    await client.async_send_opcode_with_params(137, [s_hi, s_lo, 0x80, 0x00])


BUTTONS: tuple[RoowifiButtonDescription, ...] = (
    RoowifiButtonDescription(
        key="move_forward",
        name="Move Forward",
        icon="mdi:arrow-up-bold",
        action=lambda c: _drive(c, _SPEED, _STRAIGHT, _MOVE_TIME),
    ),
    RoowifiButtonDescription(
        key="move_backward",
        name="Move Backward",
        icon="mdi:arrow-down-bold",
        action=lambda c: _drive(c, -_SPEED, _STRAIGHT, _MOVE_TIME),
    ),
    RoowifiButtonDescription(
        key="spin_left",
        name="Spin Left",
        icon="mdi:rotate-left",
        action=lambda c: _drive(c, _SPIN, _SPIN_LEFT, _SPIN_TIME),
    ),
    RoowifiButtonDescription(
        key="spin_right",
        name="Spin Right",
        icon="mdi:rotate-right",
        action=lambda c: _drive(c, _SPIN, _SPIN_RIGHT, _SPIN_TIME),
    ),
    RoowifiButtonDescription(
        key="stop_drive",
        name="Stop Driving",
        icon="mdi:stop-circle-outline",
        action=lambda c: c.async_send_opcode_with_params(137, [0x00, 0x00, 0x80, 0x00]),
    ),
    RoowifiButtonDescription(
        key="motors_on",
        name="Cleaning Motors On",
        icon="mdi:fan",
        # Bitmask 7 = side brush (bit0) + vacuum (bit1) + main brush (bit2)
        action=lambda c: c.async_send_opcode_with_params(138, [0x07]),
    ),
    RoowifiButtonDescription(
        key="motors_off",
        name="Cleaning Motors Off",
        icon="mdi:fan-off",
        action=lambda c: c.async_send_opcode_with_params(138, [0x00]),
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
    """A one-shot button that sends a command to the Roomba."""

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
            _LOGGER.error("Button '%s' failed: %s", self.entity_description.key, err)
