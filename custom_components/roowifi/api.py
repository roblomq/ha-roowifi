"""RooWifi HTTP API client with Basic/Digest auth auto-detection."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from urllib.parse import urlencode

import aiohttp

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=8)
_CMD_TIMEOUT = aiohttp.ClientTimeout(total=5)


class CannotConnect(Exception):
    """Raised when the RooWifi module is unreachable."""


class InvalidAuth(Exception):
    """Raised when credentials are rejected."""


class RoowifiClient:
    """Async HTTP client for the RooWifi module.

    Handles both HTTP Basic and HTTP Digest authentication transparently
    by sending an unauthenticated probe first and responding to the
    WWW-Authenticate challenge the server returns.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._base = f"http://{host}"
        self._username = username
        self._password = password
        self._session = session
        self._basic_auth = aiohttp.BasicAuth(username, password)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _build_digest_header(self, method: str, uri: str, www_auth: str) -> str:
        """Calculate an HTTP Digest Authorization header value."""
        p = {
            m.group(1): m.group(2)
            for m in re.finditer(r'(\w+)="?([^",\s]+)"?', www_auth)
        }
        realm = p.get("realm", "")
        nonce = p.get("nonce", "")
        qop = p.get("qop", "")

        def md5(s: str) -> str:
            return hashlib.md5(s.encode()).hexdigest()

        ha1 = md5(f"{self._username}:{realm}:{self._password}")
        ha2 = md5(f"{method}:{uri}")

        if "auth" in qop:
            nc = "00000001"
            cnonce = hashlib.md5(os.urandom(8)).hexdigest()[:8]
            digest = md5(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}")
            return (
                f'Digest username="{self._username}", realm="{realm}", '
                f'nonce="{nonce}", uri="{uri}", qop=auth, '
                f'nc={nc}, cnonce="{cnonce}", response="{digest}"'
            )

        digest = md5(f"{ha1}:{nonce}:{ha2}")
        return (
            f'Digest username="{self._username}", realm="{realm}", '
            f'nonce="{nonce}", uri="{uri}", response="{digest}"'
        )

    # ------------------------------------------------------------------
    # Low-level fetch (challenge-response cycle)
    # ------------------------------------------------------------------

    async def _get_text(
        self, path: str, params: dict | None = None, timeout: aiohttp.ClientTimeout = _TIMEOUT
    ) -> str:
        """GET a URL, handling Basic or Digest auth via challenge-response."""
        url = self._base + path
        path_qs = path + ("?" + urlencode(params) if params else "")

        try:
            # Probe without auth so the server can send its challenge
            async with self._session.get(url, params=params, timeout=timeout) as r:
                if r.status == 200:
                    return await r.text()
                if r.status != 401:
                    r.raise_for_status()
                www_auth = r.headers.get("WWW-Authenticate", "")

            # Respond to the challenge
            if www_auth.lower().startswith("digest"):
                auth_header = self._build_digest_header("GET", path_qs, www_auth)
                headers = {"Authorization": auth_header}
                async with self._session.get(
                    url, params=params, headers=headers, timeout=timeout
                ) as r2:
                    if r2.status == 401:
                        raise InvalidAuth
                    r2.raise_for_status()
                    return await r2.text()
            else:
                # Basic auth
                async with self._session.get(
                    url, params=params, auth=self._basic_auth, timeout=timeout
                ) as r2:
                    if r2.status == 401:
                        raise InvalidAuth
                    r2.raise_for_status()
                    return await r2.text()

        except (InvalidAuth, CannotConnect):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    async def _get_json(self, path: str) -> dict:
        url = self._base + path

        try:
            async with self._session.get(url, timeout=_TIMEOUT) as r:
                if r.status == 200:
                    return await r.json(content_type=None)
                if r.status != 401:
                    r.raise_for_status()
                www_auth = r.headers.get("WWW-Authenticate", "")

            if www_auth.lower().startswith("digest"):
                auth_header = self._build_digest_header("GET", path, www_auth)
                headers = {"Authorization": auth_header}
                async with self._session.get(url, headers=headers, timeout=_TIMEOUT) as r2:
                    if r2.status == 401:
                        raise InvalidAuth
                    r2.raise_for_status()
                    return await r2.json(content_type=None)
            else:
                async with self._session.get(url, auth=self._basic_auth, timeout=_TIMEOUT) as r2:
                    if r2.status == 401:
                        raise InvalidAuth
                    r2.raise_for_status()
                    return await r2.json(content_type=None)

        except (InvalidAuth, CannotConnect):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, KeyError) as err:
            raise CannotConnect(str(err)) from err

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def async_get_sensors(self) -> dict:
        """Return the raw rX sensor dict from /roomba.json."""
        data = await self._get_json("/roomba.json")
        return data["response"]

    async def async_send_opcode(self, opcode: int) -> str:
        """Send a single OI opcode via /rwr.cgi?exec=<opcode>."""
        return await self._get_text("/rwr.cgi", params={"exec": opcode}, timeout=_CMD_TIMEOUT)

    # ------------------------------------------------------------------
    # Composed command sequences
    # ------------------------------------------------------------------

    async def _wake(self) -> None:
        await self.async_send_opcode(128)
        await asyncio.sleep(1)

    async def _wake_and_safe(self) -> None:
        await self.async_send_opcode(128)
        await asyncio.sleep(1)
        await self.async_send_opcode(131)
        await asyncio.sleep(1)

    async def async_start_clean(self) -> None:
        await self._wake_and_safe()
        await self.async_send_opcode(135)

    async def async_clean_spot(self) -> None:
        await self._wake_and_safe()
        await self.async_send_opcode(136)

    async def async_dock(self) -> None:
        await self._wake()
        await self.async_send_opcode(143)

    async def async_stop(self) -> None:
        """Toggle pause/stop by sending Clean opcode once."""
        await self.async_send_opcode(135)

    async def async_wake(self) -> None:
        await self.async_send_opcode(128)
