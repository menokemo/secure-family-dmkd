"""Shared base entity for Secure Family."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_UPDATE
from .store import ConfigStore


class SecureFamilyEntity(Entity):
    """كيانات المكوّن كلها تحت جهاز واحد، وبتتحدّث مع كل تغيير."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, store: ConfigStore) -> None:
        self._entry = entry
        self._store = store
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Secure Family",
            manufacturer="Secure Family",
            model="Family configuration",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self.async_write_ha_state)
        )
