"""Config flow for RooWifi integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, InvalidAuth, RoowifiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _schema(defaults: dict | None = None) -> vol.Schema:
    """Return the user step schema, optionally pre-filled with previous input."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
            vol.Required(CONF_USERNAME, default=d.get(CONF_USERNAME, "admin")): str,
            vol.Required(CONF_PASSWORD, default=d.get(CONF_PASSWORD, "roombawifi")): str,
        }
    )


class RoowifiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the UI config flow for RooWifi."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = RoowifiClient(
                host=user_input[CONF_HOST],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )
            try:
                await client.async_get_sensors()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Roomba ({user_input[CONF_HOST]})",
                    data=user_input,
                )

        # Re-show the form with previous input pre-filled so the user
        # does not have to retype everything after a connection error.
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )
