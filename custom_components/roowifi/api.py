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

# Headers that improve compatibility with old embedded HTTP servers
_HEADERS = {"Connection": "close", "Accept": "*/*"}


class CannotConnect(Exception):
    """Raised when the RooWifi module is unreachable."""


class InvalidAuth(Exception):
    """Raised when credentials are rejected."""


class RoowifiClient:
    """Async HTTP client for the RooWifi module.

    Sensor data is read via /roomba.json.
    Commands use /roomba.cgi?button=X (same endpoint as the built-in web UI).
    Raw opcodes can still be sent via async_send_opcode() if needed.
    Auth type (Basic vs Digest) is detected on the first request and cached.
    """

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._host = host
        self._base = f"http://{host}"
        self._username = username
        self._password = password
        self._session = session
        self._basic_auth = aiohttp.BasicAuth(username, password)
        # Cached after first successful auth probe: "basic", "digest", or None
        self._auth_type: str | None = None

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
    # Low-level fetch — single request with known or probed auth
    # ------------------------------------------------------------------

    async def _get(
        self,
        path: str,
        params: dict | None = None,
        timeout: aiohttp.ClientTimeout = _TIMEOUT,
    ) -> str:
        """GET a URL and return the response text.

        On the first call the auth type is detected via challenge-response
        and cached. Subsequent calls skip the probe for Basic auth.
        """
        url = self._base + path
        path_qs = path + ("?" + urlencode(params) if params else "")
        headers = dict(_HEADERS)

        try:
            # If we already know it's Basic, send auth directly — no probe needed.
            if self._auth_type == "basic":
                async with self._session.get(
                    url, params=params, auth=self._basic_auth,
                    headers=headers, timeout=timeout,
                ) as r:
                    if r.status == 401:
                        raise InvalidAuth
                    r.raise_for_status()
                    return await r.text()

            # Probe without auth to receive the server's challenge.
            async with self._session.get(
                url, params=params, headers=headers, timeout=timeout
            ) as r:
                if r.status == 200:
                    # No authentication required on this endpoint.
                    return await r.text()
                if r.status != 401:
                    r.raise_for_status()
                www_auth = r.headers.get("WWW-Authenticate", "")

            # Respond to the challenge.
            if www_auth.lower().startswith("digest"):
                self._auth_type = "digest"
                auth_header = self._build_digest_header("GET", path_qs, www_auth)
                async with self._session.get(
                    url, params=params,
                    headers={**headers, "Authorization": auth_header},
                    timeout=timeout,
                ) as r2:
                    if r2.status == 401:
                        raise InvalidAuth
                    r2.raise_for_status()
                    return await r2.text()
            else:
                self._auth_type = "basic"
                async with self._session.get(
                    url, params=params, auth=self._basic_auth,
                    headers=headers, timeout=timeout,
                ) as r2:
                    if r2.status == 401:
                        raise InvalidAuth
                    r2.raise_for_status()
                    return await r2.text()

        except (InvalidAuth, CannotConnect):
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise CannotConnect(str(err)) from err

    # ------------------------------------------------------------------
    # Public API — sensors
    # ------------------------------------------------------------------

    async def async_get_sensors(self) -> dict:
        """Return the raw rX sensor dict from /roomba.json."""
        try:
            text = await self._get("/roomba.json")
            import json
            data = json.loads(text)
            return data["response"]
        except (KeyError, ValueError) as err:
            raise CannotConnect(f"Unexpected response from /roomba.json: {err}") from err

    # ------------------------------------------------------------------
    # Public API — commands via /roomba.cgi?button=X
    #
    # This is the same endpoint the built-in web UI uses: more reliable
    # than raw opcodes because it mirrors a physical button press and
    # works regardless of the current OI mode.
    # ------------------------------------------------------------------

    async def _button(self, button: str) -> None:
        """Send a button command via /roomba.cgi?button=<button>."""
        result = await self._get(
            "/roomba.cgi", params={"button": button}, timeout=_CMD_TIMEOUT
        )
        if result.strip() == "0":
            raise CannotConnect(
                f"RooWifi button '{button}' returned 0 — command not executed "
                "(a TCP client may still be connected on port 9001)"
            )

    async def async_start_clean(self) -> None:
        # Wake via TCP: the RooWifi pulses the BRC pin when it detects a TCP
        # connection + wake-up byte (opcode 128). Deep sleep needs several
        # seconds to fully boot the OI, so we hold the connection open and
        # send opcode 128 repeatedly before closing and issuing CLEAN.
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, 9001),
                timeout=3.0,
            )
            try:
                for _ in range(3):
                    writer.write(bytes([128]))
                    await writer.drain()
                    await asyncio.sleep(1.0)
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
        except (OSError, asyncio.TimeoutError) as err:
            raise CannotConnect(f"TCP gateway unreachable: {err}") from err

        await asyncio.sleep(0.5)
        await self._button("CLEAN")

    async def async_clean_spot(self) -> None:
        await self._button("SPOT")

    async def async_dock(self) -> None:
        await self._button("DOCK")

    async def async_stop(self) -> None:
        """Press CLEAN again to pause/stop (toggles on Roomba 600 series)."""
        await self._button("CLEAN")

    # ------------------------------------------------------------------
    # Public API — raw opcodes via /rwr.cgi (advanced / future use)
    # ------------------------------------------------------------------

    async def async_send_opcode(self, opcode: int) -> str:
        """Send a raw OI opcode via /rwr.cgi?exec=<opcode>. Returns '1' on success."""
        return await self._get(
            "/rwr.cgi", params={"exec": opcode}, timeout=_CMD_TIMEOUT
        )

    async def async_wake(self) -> None:
        await self.async_send_opcode(128)

    # ------------------------------------------------------------------
    # TCP gateway (port 9001) — required for multi-byte opcodes
    #
    # The RooWifi CGI only supports single-byte opcodes. Commands that
    # need parameter bytes (DRIVE=137, MOTORS=138) must go through the
    # raw TCP gateway. The sensor refresh pauses while connected, so
    # connections are kept as brief as possible.
    # ------------------------------------------------------------------

    async def _tcp_send(self, *packets: bytes) -> None:
        """Open a TCP connection to port 9001, send packets, then close."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, 9001),
                timeout=3.0,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise CannotConnect(f"TCP gateway unreachable: {err}") from err

        try:
            for packet in packets:
                writer.write(packet)
                await writer.drain()
                await asyncio.sleep(0.05)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    @staticmethod
    def _s16(value: int) -> bytes:
        """Encode a signed 16-bit integer as two big-endian bytes."""
        u = value if value >= 0 else value + 65536
        return bytes([(u >> 8) & 0xFF, u & 0xFF])

    async def async_drive(self, velocity: int, radius: int, duration: float) -> None:
        """Wake the Roomba, enter Safe mode, drive, then stop — all via TCP.

        velocity: -500 to 500 mm/s (positive = forward)
        radius:   -2000 to 2000 mm, or 32768 for straight, ±1 for spin in place
        duration: seconds to drive before stopping
        """
        wake_safe = bytes([128]) + bytes([131])
        drive_cmd = bytes([137]) + self._s16(velocity) + self._s16(radius)
        stop_cmd  = bytes([137]) + self._s16(0) + self._s16(32768)

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, 9001),
                timeout=3.0,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise CannotConnect(f"TCP gateway unreachable: {err}") from err

        try:
            writer.write(bytes([128]))      # Wake → Passive mode
            await writer.drain()
            await asyncio.sleep(0.4)
            writer.write(bytes([131]))      # Safe mode
            await writer.drain()
            await asyncio.sleep(0.2)
            writer.write(drive_cmd)         # Drive
            await writer.drain()
            await asyncio.sleep(duration)
            writer.write(stop_cmd)          # Stop
            await writer.drain()
            await asyncio.sleep(0.1)
            writer.write(bytes([128]))      # Back to Passive mode so HTTP CGI works again
            await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def async_motors(self, side: bool = False, vacuum: bool = False, main: bool = False) -> None:
        """Set cleaning motor states via TCP (MOTORS opcode 138).

        MOTORS only works in Safe/Full mode. When turning motors ON we stay
        in Safe mode — sending opcode 128 (Passive) would stop all actuators
        immediately. When turning motors OFF we send 128 which stops everything
        and returns HTTP CGI control.
        Bitmask: bit0 = side brush, bit1 = vacuum, bit2 = main brush.
        """
        bitmask = (0x01 if side else 0) | (0x02 if vacuum else 0) | (0x04 if main else 0)

        if bitmask == 0:
            # Passive mode stops all actuators — simplest way to turn motors off.
            await self._tcp_send(bytes([128]))
            return

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, 9001),
                timeout=3.0,
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise CannotConnect(f"TCP gateway unreachable: {err}") from err

        try:
            writer.write(bytes([128]))              # Passive mode (wake)
            await writer.drain()
            await asyncio.sleep(0.4)
            writer.write(bytes([132]))              # Full mode (no safety checks blocking motors)
            await writer.drain()
            await asyncio.sleep(0.2)
            writer.write(bytes([138, bitmask]))     # Motors ON — stay in Full mode
            await writer.drain()
            await asyncio.sleep(0.2)               # Let Roomba process before closing
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
