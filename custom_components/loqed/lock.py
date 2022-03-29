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
from homeassistant.core import HomeAssistant, callback
from homeassistant.components import webhook
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from loqedAPI import loqed

from .const import DOMAIN, WEBHOOK_PREFIX, STATE_OPENING

LOCK_STATES = {
    "opening": STATE_OPENING,
    "unlocking": STATE_UNLOCKING,
    "locking": STATE_LOCKING,
    "latch": STATE_UNLOCKED,
    "night_lock": STATE_LOCKED,
    "open": STATE_UNLOCKED,
    "day_lock": STATE_UNLOCKED,
}

WEBHOOK_API_ENDPOINT = "/api/loqed/webhook"
SCAN_INTERVAL = timedelta(seconds=3600)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the Loqed lock platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    websession = async_get_clientsession(hass)
    apiclient = loqed.APIClient(websession, "http://" + data["ip"])
    api = loqed.LoqedAPI(apiclient)
    lock = await api.async_get_lock(
        data["api-key"], data["bkey"], data["key-id"], data["name"]
    )
    # lock2 = await loqed.Lock(
    #     data["api-key"], data["bkey"], data["key-id"], data["name"]
    # )
    print(f"The lock name: {lock.name}")
    print(f"The lock ID: {lock.id}")
    if not lock:
        # No locks found; abort setup routine.
        _LOGGER.info("No Loqed locks found in your account")
        return
    # trigger webhook setup
    await check_webhook(hass, lock, data["internal_url"])
    async_add_entities([LoqedLock(lock)])


def get_random_string(length):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    result_str = "".join(random.choice(letters) for i in range(length))
    return result_str


async def check_webhook(hass, lock, internal_url):
    # During initiation of Lock (startup or after config of HA) check if the external url is available
    # and if a webhook is configured for HA with the integration ID prefix (const).
    print("Check webhook called")
    webhooks = await lock.getWebhooks()
    wh_id = Undefined
    # Check if hook already registered @loqed
    for hook in webhooks:
        if hook["url"].startswith(internal_url + "/api/webhook/" + WEBHOOK_PREFIX):
            url = hook["url"]
            wh_id = WEBHOOK_PREFIX + url[-12:]
            print("GOT WH ID FROM URL:" + url)
            break
    if wh_id == Undefined:
        wh_id = WEBHOOK_PREFIX + get_random_string(12)
        # Registering webhook in Loqed
        url = internal_url + "/api/webhook/" + wh_id
        await lock.registerWebhook(url)
    # Registering webhook in HASS, when exists same will be used
    print("Registering webhook id: " + str(url))
    try:
        webhook.async_register(
            hass=hass,
            domain=DOMAIN,
            name="loqed",
            webhook_id=wh_id,
            handler=async_handle_webhook,
        )
    except ValueError:  # when already installed
        pass
    return url


@callback
async def async_handle_webhook(hass, webhook_id, request):
    """Handle webhook callback."""
    body = await request.text()
    _LOGGER.error("RECEIVED:" + body)
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        _LOGGER.error(
            "Received invalid data from LOQED. Data needs to be formatted as JSON: %s",
            body,
        )
        return

    if not isinstance(data, dict):
        _LOGGER.error(
            "Received invalid data from LOQED. Data needs to be a dictionary: %s", data
        )
        return

    hass.bus.fire("LOQED_status_change", data)


class LoqedLock(LockEntity):
    """Representation of a loqed lock."""

    # SUPPORT_OPEN

    def __init__(self, lock: LoqedLock) -> None:
        """Initialize the lock."""
        self._lock = lock
        # self._hass_url = hass_url
        # self._attr_unique_id = self._lock.id
        self._last_changed_key_owner = ""
        self._attr_unique_id = self._lock.id
        self._attr_name = self._lock.name
        # self._battery = self._lock.battery_percentage
        # self._bolt_state = self._lock.bolt_state
        self._last_event = self._lock.last_event
        self._attr_supported_features = SUPPORT_OPEN

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()
        print("Before listening to event ..")
        self.hass.bus.async_listen("LOQED_status_change", self.status_update_event)
        print("After listening to event ..")

    @callback
    async def status_update_event(self, event) -> None:
        data = event.data
        print("RECEIVED EVENT for lock: " + data["mac_wifi"])
        await self._lock.receiveWebhook(data)
        print("BOLT_STATE:" + self.bolt_state)
        self.async_schedule_update_ha_state()

    @property
    def changed_by(self):
        """Return true if lock is locking."""
        return self._last_changed_key_owner

    @property
    def bolt_state(self):
        """Return true if lock is locking."""
        return self._lock.bolt_state

    @property
    def is_locking(self):
        """Return true if lock is locking."""
        return LOCK_STATES[self.bolt_state] == STATE_LOCKING

    @property
    def is_unlocking(self):
        """Return true if lock is unlocking."""
        return LOCK_STATES[self.bolt_state] == STATE_UNLOCKING

    @property
    def is_jammed(self):
        """Return true if lock is jammed."""
        return LOCK_STATES[self.bolt_state] == STATE_JAMMED

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return LOCK_STATES[self.bolt_state] == STATE_LOCKED

    @property
    def battery(self):
        """Return true if lock is locked."""
        return self._lock.battery_percentage

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
            "bolt_state": self.bolt_state,
            "last_event": self._last_event,
            # "party_mode": self._lock.party_mode,
            # "guest_access_mode": self._lock.guest_access_mode,
            # "twist_assist": self._lock.twist_assist,
            # "touch_to_connect": self._lock.touch_to_connect,
            # "lock_direction": self._lock.lock_direction,
            # "mortise_lock_type": self._lock.mortise_lock_type,
            # "registered_webhooks": self._lock.webhooks,
            "last_changed_key_owner": self._last_changed_key_owner,
        }
        return state_attr

    async def async_lock(self, **kwargs):
        await self._lock.lock()
        # self._state = STATE_LOCKED
        # self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        await self._lock.unlock()
        # self._state = STATE_UNLOCKED
        # self.async_write_ha_state()

    async def async_open(self, **kwargs):
        await self._lock.open()
        # self._state = STATE_UNLOCKED
        # self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the internal state of the device."""
        # await self._lock.update()
        self._attr_unique_id = self._lock.id
        self._attr_name = self._lock.name
        print("AFTER UPDATE BOLT_STATE:" + self.bolt_state)
        # locks = await api.async_get_locks()
        # # self._nickname = self._sesame.nickname
        # self._device_id = str(self._sesame.id)
        # self._serial = self._sesame.serial
        # self._battery = status["battery"]
        # self._state = self._lock.bolt_state
        # self._attr_name = self._lock.name
        self.async_schedule_update_ha_state()


async def async_setup_intents(hass):
    """
    Do intents setup.

    Right now this module does not expose any, but the intent component breaks
    without it.
    """
    pass  # pylint: disable=unnecessary-pass
