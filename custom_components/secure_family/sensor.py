"""Sensors for Secure Family: the config carrier + diagnostic sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .entity import SecureFamilyEntity
from .store import ConfigStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    store: ConfigStore = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SecureFamilyConfigSensor(entry, store),
            SecureFamilyVersionSensor(entry, store),
            SecureFamilyLastUpdateSensor(entry, store),
        ]
    )


class SecureFamilyConfigSensor(SecureFamilyEntity, SensorEntity):
    """الكيان اللي بيحمل إعداد العيلة — التطبيق بيقراه من attributes.

    الـstate = رقم النسخة. إعداد العيلة نفسه في attribute اسمه `config`،
    ومستبعد من الـrecorder عشان ما نخزّنش JSON كبير في قاعدة البيانات.
    """

    _attr_translation_key = "config"
    _attr_icon = "mdi:cog-sync"
    _unrecorded_attributes = frozenset({"config"})

    def __init__(self, entry: ConfigEntry, store: ConfigStore) -> None:
        super().__init__(entry, store)
        self._attr_unique_id = f"{entry.entry_id}_config"

    @property
    def native_value(self) -> int:
        return self._store.version

    @property
    def extra_state_attributes(self) -> dict:
        data = self._store.data
        return {
            "config": data.get("config", {}),
            "updated_at": data.get("updated_at"),
            "updated_by": data.get("updated_by"),
            "has_history": bool(data.get("history")),
        }


class SecureFamilyVersionSensor(SecureFamilyEntity, SensorEntity):
    """رقم نسخة الإعداد الحالي (تشخيصي)."""

    entity_description = SensorEntityDescription(
        key="version",
        translation_key="version",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(self, entry: ConfigEntry, store: ConfigStore) -> None:
        super().__init__(entry, store)
        self._attr_unique_id = f"{entry.entry_id}_version"

    @property
    def native_value(self) -> int:
        return self._store.version


class SecureFamilyLastUpdateSensor(SecureFamilyEntity, SensorEntity):
    """وقت آخر نشر للإعداد (تشخيصي)."""

    entity_description = SensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    )

    def __init__(self, entry: ConfigEntry, store: ConfigStore) -> None:
        super().__init__(entry, store)
        self._attr_unique_id = f"{entry.entry_id}_last_update"

    @property
    def native_value(self) -> datetime | None:
        updated_at = self._store.data.get("updated_at")
        if not updated_at:
            return None
        return dt_util.parse_datetime(updated_at)
