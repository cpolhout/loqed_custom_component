"""API for loqed bound to Home Assistant OAuth. (Next version)"""
from __future__ import annotations

from datetime import timedelta
import logging
import json
import string
import random
from voluptuous.schema_builder import Undefined

from homeassistant.components.lock import SUPPORT_OPEN, LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_JAMMED,
    STATE_LOCKED,
    STATE_LOCKING,
    STATE_UNLOCKED,
    STATE_UNLOCKING,
)
from homeassistant.core import HomeAssistant
from homeassistant.components import webhook
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from loqedAPI import loqed

from .const import DOMAIN, LOQED_URL, WEBHOOK_PREFIX

WEBHOOK_API_ENDPOINT = "/api/loqed/webhook"
SCAN_INTERVAL = timedelta(seconds=3600)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the Loqed lock platform."""
    # for key in hass.data:
    #     print("Key:" + key)
    #     print("Val:" + str(hass.data[key]))
    # print(hass.data["loqed"])
    data = hass.data[DOMAIN][entry.entry_id]
    websession = async_get_clientsession(hass)
    apiclient = loqed.APIClient(websession, LOQED_URL, data["api_key"])
    api = loqed.LoqedAPI(apiclient)
    loqed_locks = await api.async_get_locks()
    print(f"The lock name: {loqed_locks[0].name}")
    print(f"The lock ID: {loqed_locks[0].id}")
    if not loqed_locks:
        # No locks found; abort setup routine.
        _LOGGER.info("No Loqed locks found in your account")
        return
    # trigger webhook setup
    for lock in loqed_locks:
        await check_webhook(hass, lock, data["hass_url"])

    async_add_entities([LoqedLock(lock) for lock in loqed_locks])


def get_random_string(length):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    return result_str


async def check_webhook(hass, lock, hass_url):
    # During initiation of Lock (startup or after config of HA) check if the external url is available
    # and if a webhook is configured for HA with the integration ID prefix (const).
    print("ON READY CALLED")
    if len(hass_url) > 5:
        print("HASSURL" + hass_url)
        webhooks = await lock.getWebhooks()
        wh_id = Undefined
        # Check if hook already registered @loqed
        for hook in webhooks:
            if hook["url"].startswith(hass_url + "/webhook/" + WEBHOOK_PREFIX):
                url = hook["url"]
                wh_id = WEBHOOK_PREFIX + url[-12:]
                print("GOT WH ID FROM URL:" + url)
                break
        if wh_id == Undefined:
            wh_id = WEBHOOK_PREFIX + get_random_string(12)
            # Registering webhook in Loqed
            url = hass_url + "/webhook/" + wh_id
            await lock.registerWebhook(url)
        # Registering webhook in HASS, when exists same will be used
        print("Registering webhook id: " + str(url))
        webhook.async_register(
            hass=hass,
            domain=DOMAIN,
            name="loqed",
            webhook_id=wh_id,
            handler=async_handle_webhook,
        )
        return url
    return ""


async def async_handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    body = await request.text()
    print("RECEIVED:" + body)
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        _LOGGER.error(
            "Received invalid data from IFTTT. Data needs to be formatted as JSON: %s",
            body,
        )
        return

    if not isinstance(data, dict):
        _LOGGER.error(
            "Received invalid data from IFTTT. Data needs to be a dictionary: %s", data
        )
        return

    # data["webhook_id"] = webhook_id
    # hass.bus.async_fire(EVENT_RECEIVED, data)


class LoqedLock(LockEntity):
    """Representation of a loqed lock."""

    # SUPPORT_OPEN

    def __init__(self, lock) -> None:
        """Initialize the lock."""
        self._lock = lock
        # self._hass_url = hass_url
        # self._attr_unique_id = self._lock.id
        self._attr_unique_id = self._lock.id
        self._attr_name = self._lock.name
        self._bolt_state = self._lock.bolt_state
        self._attr_supported_features = SUPPORT_OPEN
        if self._bolt_state == "night_lock":
            self._state = STATE_LOCKED
        else:
            self._state = STATE_UNLOCKED

    # async def async_added_to_hass(self, hass):
    #     self.check_webhook()

    @property
    def is_locking(self):
        """Return true if lock is locking."""
        return self._state == STATE_LOCKING

    @property
    def is_unlocking(self):
        """Return true if lock is unlocking."""
        return self._state == STATE_UNLOCKING

    @property
    def is_jammed(self):
        """Return true if lock is jammed."""
        return self._state == STATE_JAMMED

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self._state == STATE_LOCKED

    # @property
    # def state(self):
    #     if self._bolt_state == "night_lock":
    #         return STATE_LOCKED
    #     else:
    #         return STATE_UNLOCKED

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN

    @property
    def extra_state_attributes(self):
        state_attr = {
            "id": self._lock.id,
            "battery_percentage": self._lock.battery_percentage,
            "battery_type": self._lock.battery_type,
            "bolt_state": self._lock.bolt_state,
            "party_mode": self._lock.party_mode,
            "guest_access_mode": self._lock.guest_access_mode,
            "twist_assist": self._lock.twist_assist,
            "touch_to_connect": self._lock.touch_to_connect,
            "lock_direction": self._lock.lock_direction,
            "mortise_lock_type": self._lock.mortise_lock_type,
        }
        return state_attr

    async def async_lock(self, **kwargs):
        self._state = STATE_LOCKING
        await self._lock.lock()
        self._state = STATE_LOCKED
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        self._state = STATE_UNLOCKING
        await self._lock.unlock()
        self._state = STATE_UNLOCKED
        self.async_write_ha_state()

    async def async_open(self, **kwargs):
        await self._lock.open()
        self._state = STATE_UNLOCKED
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the internal state of the device."""
        await self._lock.update()
        self._attr_unique_id = self._lock.id
        self._attr_name = self._lock.name
        self._bolt_state = self._lock.bolt_state
        if self._bolt_state == "night_lock":
            self._state = STATE_LOCKED
        else:
            self._state = STATE_UNLOCKED
        # locks = await api.async_get_locks()
        # # self._nickname = self._sesame.nickname
        # self._device_id = str(self._sesame.id)
        # self._serial = self._sesame.serial
        # self._battery = status["battery"]
        # self._state = self._lock.bolt_state
        # self._battery = self._lock.battery_percentage
        # self._attr_name = self._lock.name


async def async_setup_intents(hass):
    """
    Do intents setup.

    Right now this module does not expose any, but the intent component breaks
    without it.
    """
    pass  # pylint: disable=unnecessary-pass


# class LoqedWebhookView(http.HomeAssistantView):
#     """Handle loqed webhook requests."""

#     url = WEBHOOK_API_ENDPOINT
#     name = "api:loqed:webhook"

#     async def post(self, request):
#         """Handle POST request"""
#         hass = request.app["hass"]
#         message = await request.json()
#         print("MESSAGE:" + message)
#         _LOGGER.debug("Received LOQED request: %s", message)

# try:
#     response = await async_handle_message(hass, message)
#     return b"" if response is None else self.json(response)
# except UnknownRequest as err:
#     _LOGGER.warning(str(err))
#     return self.json(intent_error_response(hass, message, str(err)))

# except intent.UnknownIntent as err:
#     _LOGGER.warning(str(err))
#     return self.json(
#         intent_error_response(
#             hass,
#             message,
#             "This intent is not yet configured within Home Assistant.",
#         )
#     )

# except intent.InvalidSlotInfo as err:
#     _LOGGER.error("Received invalid slot data from Alexa: %s", err)
#     return self.json(
#         intent_error_response(
#             hass, message, "Invalid slot information received for this intent."
#         )
#     )

# except intent.IntentError as err:
#     _LOGGER.exception(str(err))
#     return self.json(
#         intent_error_response(hass, message, "Error handling intent.")
#     )
