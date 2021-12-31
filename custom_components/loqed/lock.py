"""API for loqed bound to Home Assistant OAuth. (Next version)"""
from __future__ import annotations

from datetime import timedelta
import logging

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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from loqedAPI import loqed

from .const import DOMAIN, LOQED_URL

SCAN_INTERVAL = timedelta(seconds=10)

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
    for lock in loqed_locks:
        print("Lock:" + str(lock))
        # for attribute in dir(lock):
        #     print(attribute)
    # entities = []

    # for device in loqed_locks(generic_type=CONST.TYPE_LOCK):
    #     entities.append(AbodeLock(data, device))

    # async_add_entities(entities)
    async_add_entities([LoqedLock(lock) for lock in loqed_locks])
    # TESTING MULTIPLE!
    # async_add_entities([LoqedLock(lock, "Lock2") for lock in loqed_locks])
    # async_add_entities(
    #     [LoqedLock("Sanne", STATE_UNLOCKED), LoqedLock("Casper", STATE_UNLOCKED)]
    # )


class LoqedLock(LockEntity):
    """Representation of a loqed lock."""

    # SUPPORT_OPEN

    def __init__(self, lock) -> None:
        """Initialize the lock."""
        self._lock = lock
        # self._attr_unique_id = self._lock.id
        self._attr_unique_id = self._lock.id
        self._attr_name = self._lock.name
        self._bolt_state = self._lock.bolt_state
        self._attr_supported_features = SUPPORT_OPEN
        if self._bolt_state == "night_lock":
            self._state = STATE_LOCKED
        else:
            self._state = STATE_UNLOCKED
        # self._data = data
        # self._device = device
        # self._lock_status = None
        # self._attr_name = device.device_name

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
