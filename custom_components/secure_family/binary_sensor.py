"""Binary sensor: whether a family configuration has been published."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SecureFamilyEntity
from .store import ConfigStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ConfigStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SecureFamilyConfiguredBinarySensor(entry, store)])


class SecureFamilyConfiguredBinarySensor(SecureFamilyEntity, BinarySensorEntity):
    """On لو الأدمن نشر إعداد عائلي (version > 0)."""

    entity_description = BinarySensorEntityDescription(
        key="configured",
        translation_key="configured",
        icon="mdi:check-decagram",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(self, entry: ConfigEntry, store: ConfigStore) -> None:
        super().__init__(entry, store)
        self._attr_unique_id = f"{entry.entry_id}_configured"

    @property
    def is_on(self) -> bool:
        return self._store.version > 0
