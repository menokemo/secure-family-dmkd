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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import APP_ID, APP_NAME, DOMAIN
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
            SecureFamilyDevicesSensor(entry, store),
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


class SecureFamilyDevicesSensor(SecureFamilyEntity, SensorEntity):
    """لستة موبايلات تطبيقنا (app_id=secure_family) وسينسورز كل واحد.

    الـstate = عدد موبايلاتنا؛ التفاصيل في attribute `devices`: اسم كل جهاز،
    بطاريته، حالة موقعه، آخر تحديث، وكل سينسوراته. بيفلتر حصريًا على تطبيقنا،
    فمابيعرضش أجهزة تطبيق Home Assistant الأصلي.
    """

    _attr_translation_key = "devices"
    _attr_icon = "mdi:cellphone-link"
    _attr_should_poll = True
    _unrecorded_attributes = frozenset({"devices"})

    def __init__(self, entry: ConfigEntry, store: ConfigStore) -> None:
        super().__init__(entry, store)
        self._attr_unique_id = f"{entry.entry_id}_devices"
        self._devices: list[dict] = []

    def _collect(self) -> list[dict]:
        hass = self.hass
        ent_reg = er.async_get(hass)
        out: list[dict] = []
        for cfg in hass.config_entries.async_entries("mobile_app"):
            data = cfg.data or {}
            if data.get("app_id") != APP_ID and data.get("app_name") != APP_NAME:
                continue
            entities = er.async_entries_for_config_entry(ent_reg, cfg.entry_id)
            tracker = next(
                (e.entity_id for e in entities if e.domain == "device_tracker"), None
            )
            battery = None
            sensors: dict[str, str] = {}
            for ent in entities:
                if ent.domain not in ("sensor", "binary_sensor"):
                    continue
                st = hass.states.get(ent.entity_id)
                if st is None:
                    continue
                sensors[ent.entity_id] = st.state
                if battery is None and "battery_level" in ent.entity_id:
                    try:
                        battery = int(float(st.state))
                    except (ValueError, TypeError):
                        pass
            tstate = hass.states.get(tracker) if tracker else None
            out.append(
                {
                    "name": cfg.title,
                    "device_name": data.get("device_name"),
                    "location": tstate.state if tstate else None,
                    "last_updated": tstate.last_updated.isoformat() if tstate else None,
                    "battery": battery,
                    "tracker": tracker,
                    "sensors": sensors,
                }
            )
        return out

    async def async_update(self) -> None:
        self._devices = self._collect()

    @property
    def native_value(self) -> int:
        return len(self._devices)

    @property
    def extra_state_attributes(self) -> dict:
        return {"devices": self._devices}
