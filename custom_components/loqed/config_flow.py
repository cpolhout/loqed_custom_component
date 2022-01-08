"""Config flow for loqed integration."""
from __future__ import annotations

import logging
from typing import Any
import re
import aiohttp
import voluptuous as vol
from voluptuous.schema_builder import Undefined

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import network
from homeassistant.helpers.typing import ConfigType

from loqedAPI import loqed

from .const import DOMAIN, LOQED_URL

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


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    async with aiohttp.ClientSession() as session:
        # apiclient = APIClient(session, "https://bc615891-1f7d-4237-8b72-f20e5719d50e.mock.pstmn.io/api", "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiI5NGRiMDgyOS00ZWY4LTQ4ODEtYjY4YS05NGZkOTY1NWY0MzgiLCJqdGkiOiI1NDI5MzI2OTRlMmMxYzgxODk3YzU1YzE1YzZlOTMyYmE4MDdhYWFmNWEyNTQ4ZjhiMWExMTBlNjRkMzY4MmVjYzdhNmU2NTBlMWM5Yzc5NyIsImlhdCI6MTYzNzAyMDcxNy42NjM5NTcsIm5iZiI6MTYzNzAyMDcxNy42NjQyNDcsImV4cCI6MTY1MjY1OTExNS4yOTA4MDYsInN1YiI6IjEwNjEiLCJzY29wZXMiOltdfQ.B7eZUgQjDT6wOfJ6I0LnRa4_2eTEiKkCqrQzXu9dB_eC-ak4yPdxf0YvNhniLNwiS0AxdZq2P2aRlpxlo8g7SwECIz06SqiYHjc26LHraRUwJeXL2y_2beMcm7Xbi9tN_AfNZ0lSh_Sdj1WDDRSTDnsDp7JP2jMrIxVJBMJzhI_traRnTcs_5O41Mlgrg8372HyLWd64QrUDaVQB34tDX6wKpRCSUHeSLJX_DmPM-LUenslGEy_pva0OSQljjqG9LcZY7uC2bcaz6R7ZSDPq1qlsaRTshDZvpRfZ-bB1S0yw6wpTZ4Y2bhNbXHtZmejRLfiRn2JjHTisCQwxWaKYM-1EfemMXP5AZPstwOGTdB0vUBqsTtYHPpEEHgm94oznVlPRtjLu0uWYUXT07PFmZtDlXp6GD6gM1ZP376-nXL0kjimfhAntcSsxKGiJg7yw4hQt6oID50o3kk2_nbeIiCEIYMmeiSgGe2XNMo11SR_gn60jHGWJT6YrukkB5Ywqpnw_xqi2TQwIEydhJMqoHjJyTju_0vTlKh8LCXC064DIyU6QhMG5QOPMJ3xKgGdsg1rTHVh3vd39Y42SDQ3yj_CQHuvQsmjP-fSgJ-BVepJk4Ae5VdFTb49w7qNPg91pPCr0EGbHA54kGIeTdemsTLnj7A1MEjO64Sj9jO8V6FE")
        apiclient = loqed.APIClient(session, LOQED_URL, data["api_key"])
        # eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJhdWQiOiI5NGRiMDgyOS00ZWY4LTQ4ODEtYjY4YS05NGZkOTY1NWY0MzgiLCJqdGkiOiI1NDI5MzI2OTRlMmMxYzgxODk3YzU1YzE1YzZlOTMyYmE4MDdhYWFmNWEyNTQ4ZjhiMWExMTBlNjRkMzY4MmVjYzdhNmU2NTBlMWM5Yzc5NyIsImlhdCI6MTYzNzAyMDcxNy42NjM5NTcsIm5iZiI6MTYzNzAyMDcxNy42NjQyNDcsImV4cCI6MTY1MjY1OTExNS4yOTA4MDYsInN1YiI6IjEwNjEiLCJzY29wZXMiOltdfQ.B7eZUgQjDT6wOfJ6I0LnRa4_2eTEiKkCqrQzXu9dB_eC-ak4yPdxf0YvNhniLNwiS0AxdZq2P2aRlpxlo8g7SwECIz06SqiYHjc26LHraRUwJeXL2y_2beMcm7Xbi9tN_AfNZ0lSh_Sdj1WDDRSTDnsDp7JP2jMrIxVJBMJzhI_traRnTcs_5O41Mlgrg8372HyLWd64QrUDaVQB34tDX6wKpRCSUHeSLJX_DmPM-LUenslGEy_pva0OSQljjqG9LcZY7uC2bcaz6R7ZSDPq1qlsaRTshDZvpRfZ-bB1S0yw6wpTZ4Y2bhNbXHtZmejRLfiRn2JjHTisCQwxWaKYM-1EfemMXP5AZPstwOGTdB0vUBqsTtYHPpEEHgm94oznVlPRtjLu0uWYUXT07PFmZtDlXp6GD6gM1ZP376-nXL0kjimfhAntcSsxKGiJg7yw4hQt6oID50o3kk2_nbeIiCEIYMmeiSgGe2XNMo11SR_gn60jHGWJT6YrukkB5Ywqpnw_xqi2TQwIEydhJMqoHjJyTju_0vTlKh8LCXC064DIyU6QhMG5QOPMJ3xKgGdsg1rTHVh3vd39Y42SDQ3yj_CQHuvQsmjP-fSgJ-BVepJk4Ae5VdFTb49w7qNPg91pPCr0EGbHA54kGIeTdemsTLnj7A1MEjO64Sj9jO8V6FE
        api = loqed.LoqedAPI(apiclient)

        locks = await api.async_get_locks()
        # print(f"The lock name: {locks[0].name}")
        # print(f"The lock ID: {locks[0].id}")
        # print("LOCKS:" + str(locks))

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
    return {
        "Name": locks[0].name,
        "ID": locks[0].id,
        "hass_url": data["hass_url"],
        "api_key": data["api_key"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for loqed."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        try:
            external_url = network.get_url(self.hass, prefer_external=True)
            print("external url from hass:" + external_url)
        except network.NoURLAvailableError:
            external_url = Undefined
            print("external url EXC:" + external_url)

        STEP_USER_DATA_SCHEMA = vol.Schema(
            {
                vol.Required("api_key"): str,
                vol.Optional("hass_url", default=external_url): str,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        print("CONFIG OPTIONS1:" + str(self.config_entry.data))
        hass_url = self.config_entry.data.hass_url
        print("HASSURL: " + hass_url)
        if len(hass_url) > 5:
            external_url = hass_url
        else:
            # Try to get the external URL:
            try:
                external_url = network.get_url(
                    self.hass,
                    allow_internal=True,
                    allow_ip=False,
                    require_ssl=False,
                    require_standard_port=True,
                )
            except network.NoURLAvailableError:
                external_url = ""

        print("EXTERNAL URL:" + external_url)

        STEP_USER_OPTIONS_SCHEMA = vol.Schema(
            {vol.Optional("hass_url", default=external_url): str}
        )
        return self.async_show_form(
            step_id="init", data_schema=STEP_USER_OPTIONS_SCHEMA, errors=errors
        )
