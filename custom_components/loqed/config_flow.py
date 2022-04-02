"""Config flow for loqed integration."""
from __future__ import annotations

import logging
from typing import Any
import re
import aiohttp
import voluptuous as vol
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


async def validate_input(hass, data):
    """Validate the user input allows us to connect.
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # check local HA URL
    if len(data["internal_url"]) > 5:
        if re.match(urlRegex, data["internal_url"]) is None:
            _LOGGER.error("Local HA URL is incorrect %s", data["internal_url"])
            raise ValueError("Local HA URL is incorrect")

    newdata = data
    vals = data["config"].split("|")
    newdata["ip"] = vals[0]
    newdata["host"] = vals[1]
    newdata["api-key"] = vals[2]
    newdata["key-id"] = vals[3]
    newdata["bkey"] = vals[4]

    # 1. Checking loqed-connection
    try:
        async with aiohttp.ClientSession() as session:
            apiclient = loqed.APIClient(session, "http://" + newdata["ip"])
            api = loqed.LoqedAPI(apiclient)
            lock = await api.async_get_lock(
                newdata["api-key"], newdata["bkey"], newdata["key-id"], newdata["name"]
            )
            _LOGGER.debug("Lock details retrieved: %s", newdata["ip"])
            newdata["id"] = lock.id
            # checking getWebooks to check the bridgeKey
            await lock.getWebhooks()
    except (aiohttp.ClientError):
        _LOGGER.error("HTTP Connection error to loqed lock: %s:%s", lock.name, lock.id)
        raise CannotConnect from aiohttp.ClientError
    except Exception:
        _LOGGER.error("HTTP Connection error to loqed lock: %s:%s", lock.name, lock.id)
        raise CannotConnect from aiohttp.ClientError

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return newdata


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for loqed."""

    VERSION = 1

    def __init__(self) -> None:
        self.host = "LOQED.."

    async def async_step_zeroconf(self, discovery_info) -> FlowResult:
        """Handle zeroconf discovery."""
        # Hostname is format: LOQED-
        # self.host = discovery_info.hostname.rstrip(".")
        _LOGGER.debug("HOST: %s", discovery_info.hostname)
        _LOGGER.info("HOST: %s", discovery_info.hostname)

        host = discovery_info.hostname.rstrip(".")
        async with aiohttp.ClientSession() as session:
            apiclient = loqed.APIClient(session, "http://" + host)
            api = loqed.LoqedAPI(apiclient)
            lock_data = await api.async_get_lock_details()

        # Check if already exists
        await self.async_set_unique_id(
            lock_data["bridge_mac_wifi"], raise_on_progress=False
        )
        self._abort_if_unique_id_configured()

        # try:
        #     self.brother = Brother(self.host, snmp_engine=snmp_engine, model=model)
        #     await self.brother.async_update()
        # except UnsupportedModel:
        #     return self.async_abort(reason="unsupported_model")
        # except (ConnectionError, SnmpError):
        #     return self.async_abort(reason="cannot_connect")

        # Check if already configured
        # await self.async_set_unique_id(self.brother.serial.lower())
        # self._abort_if_unique_id_configured()

        # self.context.update(
        #     {
        #         "title_placeholders": {
        #             "serial_number": self.brother.serial,
        #             "model": self.brother.model,
        #         }
        #     }
        # )
        self.host = host
        return await self.async_step_user()

    # async def async_step_zeroconf(self, discovery_info: dict):
    #     print("DISCOVERED:")
    #     print(discovery_info)
    #     # await self.async_set_unique_id(int(discovery_info.get(HOSTNAME)[12:], 16))
    #     # self._abort_if_unique_id_configured()
    #     return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        try:
            internal_url = network.get_url(
                self.hass, allow_internal=True, allow_external=False, allow_ip=True
            )
            if internal_url.startswith("172"):
                internal_url = "http://<IP>:8123"
        except network.NoURLAvailableError:
            internal_url = "http://<IP>:8123"

        # STEP_USER_DATA_SCHEMA = vol.Schema(
        #     {
        #         vol.Required("name", default="My Lock"): str,
        #         vol.Required("ip", default=self.host): str,
        #         vol.Required("api-key"): str,
        #         vol.Required("key-id", default=None): int,
        #         vol.Required("bkey"): str,
        #         vol.Required("internal_url", default=internal_url): str,
        #     }
        # )

        STEP_USER_DATA_SCHEMA = vol.Schema(
            {
                vol.Required("name", default="My Lock"): str,
                vol.Required("internal_url", default=internal_url): str,
                vol.Required(
                    "config",
                ): str,
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
            await self.async_set_unique_id(info["id"], raise_on_progress=False)
            self._abort_if_unique_id_configured()
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
