"""Config flow for loqed integration."""
from __future__ import annotations

import logging
from typing import Any
import re
import aiohttp
import voluptuous as vol
from voluptuous.schema_builder import Undefined

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import network

from loqedAPI import loqed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

urlRegex = re.compile(
    r"^(?:http|ftp)s?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


class PlaceholderHub:
    """Placeholder class to make tests pass.
    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self) -> None:
        """Initialize."""
        # self.host = host

    async def authenticate(self, api_key: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass, data):
    """Validate the user input allows us to connect.
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    async with aiohttp.ClientSession() as session:
        apiclient = loqed.APIClient(session, "http://" + data["ip"])
        api = loqed.LoqedAPI(apiclient)
        lock = await api.async_get_lock(
            data["api-key"], data["bkey"], data["key-id"], data["name"]
        )
        print(f"The lock name: {lock.name}")
        print(f"The lock ID: {lock.id}")
        newdata = data
        newdata["ID"] = lock.id

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # if len(data["hass_url"]) > 5:
    #     if re.match(data["hass_url"]) is None:
    #         print("EXTERNAL URL IS INCORRECT")
    #     else:
    #         print("EXTERNAL URL IS CORRECT")

    # Return info that you want to store in the config entry.
    return newdata


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for loqed."""

    VERSION = 1

    async def async_step_dhcp(self, discovery_info: dict):
        print("DISCOVERED:")
        print(discovery_info)
        # await self.async_set_unique_id(int(discovery_info.get(HOSTNAME)[12:], 16))
        # self._abort_if_unique_id_configured()
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        try:
            internal_url = network.get_url(
                self.hass, allow_internal=True, allow_external=False, allow_ip=True
            )
            print("Internal url from hass:" + internal_url)
            if internal_url.startswith("172"):
                internal_url = "http://<IP>:8123"
        except network.NoURLAvailableError:
            internal_url = Undefined

        STEP_USER_DATA_SCHEMA = vol.Schema(
            {
                vol.Required("name", default="My Lock"): str,
                vol.Required("ip", default="LOQED_..."): str,
                vol.Required("api-key"): str,
                vol.Required("key-id"): int,
                vol.Required("bkey"): str,
                vol.Required("internal_url", default=internal_url): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            print("IN CONFIG 1")
            info = await validate_input(self.hass, user_input)
            print("IN CONFIG 2, input validated")
            await self.async_set_unique_id(info["ID"])
            print("IN CONFIG 3, Unique ID set, info:" + str(info))
            return self.async_create_entry(
                title="LOQED Touch Smart Lock", data=user_input
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    # @staticmethod
    # @callback
    # def async_get_options_flow(config_entry):
    #     """Get the options flow for this handler."""
    #     return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
