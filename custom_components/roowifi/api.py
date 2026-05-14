"""RooWifi HTTP API client."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=8)
_CMD_TIMEOUT = aiohttp.ClientTimeout(total=5)


class CannotConnect(Exception):
    """Raised when connection to RooWifi fails."""


class InvalidAuth(Exception):
    """Raised when HTTP 401 is returned."""


class RoowifiClient:
    """Async HTTP client for the RooWifi module."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._base = f"http://{host}"
        self._auth = aiohttp.BasicAuth(username, password)
        self._session = session

    async def async_get_sensors(self) -> dict:
        """Return the raw rX sensor dict from /roomba.json."""
        try:
            async with self._session.get(
                f"{self._base}/roomba.json",
                auth=self._auth,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise InvalidAuth
                resp.raise_for_status()
                data = await resp.json(content_type=None)
                return data["response"]
        except InvalidAuth:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, KeyError) as err:
            raise CannotConnect(str(err)) from err

    async def async_send_opcode(self, opcode: int) -> str:
        """Send a single OI opcode via /rwr.cgi?exec=<opcode>. Returns '1' on success."""
        try:
            async with self._session.get(
                f"{self._base}/rwr.cgi",
                params={"exec": opcode},
                auth=self._auth,
                timeout=_CMD_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                return (await resp.text()).strip()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    # --- Composed command sequences -------------------------------------------

    async def _wake(self) -> None:
        await self.async_send_opcode(128)
        await asyncio.sleep(1)

    async def _wake_and_safe(self) -> None:
        await self.async_send_opcode(128)   # Start / wake
        await asyncio.sleep(1)
        await self.async_send_opcode(131)   # Safe mode
        await asyncio.sleep(1)

    async def async_start_clean(self) -> None:
        await self._wake_and_safe()
        await self.async_send_opcode(135)   # Clean

    async def async_clean_spot(self) -> None:
        await self._wake_and_safe()
        await self.async_send_opcode(136)   # Spot

    async def async_dock(self) -> None:
        await self._wake()
        await self.async_send_opcode(143)   # Seek Dock

    async def async_stop(self) -> None:
        """Toggle pause/stop by sending Clean opcode once."""
        await self.async_send_opcode(135)

    async def async_wake(self) -> None:
        await self.async_send_opcode(128)
