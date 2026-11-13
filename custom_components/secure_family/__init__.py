"""The Secure Family integration.

مخزن إعداد مركزي للعيلة داخل Home Assistant: الأدمن ينشر الإعداد من التطبيق،
وباقي الأجهزة تقراه فورًا (local push) وتطبّقه عند الدخول. كله محلي على الشبكة،
والكتابة للأدمن بس.
"""

from __future__ import annotations

from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    APP_ID,
    APP_NAME,
    DEFAULT_STALE_DAYS,
    DOMAIN,
    EVENT_LIVE_REQUEST,
    EVENT_UPDATED,
    SERVICE_CLEANUP_TRACKERS,
    SERVICE_CLEAR,
    SERVICE_REQUEST_LIVE,
    SERVICE_ROLLBACK,
    SERVICE_SET_CONFIG,
    SIGNAL_UPDATE,
)
from .store import ConfigStore

PLATFORMS = ["sensor", "binary_sensor"]

SET_CONFIG_SCHEMA = vol.Schema({vol.Required("config"): dict})
ROLLBACK_SCHEMA = vol.Schema({vol.Optional("version"): int})
CLEAR_SCHEMA = vol.Schema({})
CLEANUP_SCHEMA = vol.Schema(
    {vol.Optional("max_age_days", default=DEFAULT_STALE_DAYS): vol.All(int, vol.Range(min=1))}
)
REQUEST_LIVE_SCHEMA = vol.Schema({vol.Required("entity_id"): cv.string})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Secure Family from a config entry."""
    store = ConfigStore(hass)
    await store.async_load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = store

    async def _user_name(call: ServiceCall) -> str | None:
        """يتأكد إن المنفّذ أدمن ويرجّع اسمه. بيرفض غير الأدمن."""
        user_id = call.context.user_id
        if user_id is None:
            # نداء داخلي موثوق (أتمتة/سكربت على السيرفر).
            return None
        user = await hass.auth.async_get_user(user_id)
        if user is None or not user.is_admin:
            raise HomeAssistantError(
                "Only Home Assistant administrators can change the family configuration."
            )
        return user.name

    def _notify() -> None:
        async_dispatcher_send(hass, SIGNAL_UPDATE)
        hass.bus.async_fire(EVENT_UPDATED, {"version": store.version})

    async def handle_set(call: ServiceCall) -> None:
        name = await _user_name(call)
        await store.async_set(dict(call.data["config"]), name)
        _notify()

    async def handle_rollback(call: ServiceCall) -> None:
        name = await _user_name(call)
        await store.async_rollback(call.data.get("version"), name)
        _notify()

    async def handle_clear(call: ServiceCall) -> None:
        name = await _user_name(call)
        await store.async_clear(name)
        _notify()

    async def handle_cleanup(call: ServiceCall) -> dict[str, int]:
        """يمسح تسجيلات mobile_app القديمة بتاعة التطبيق (المكررة). أدمن بس."""
        await _user_name(call)
        cutoff = dt_util.utcnow() - timedelta(days=call.data["max_age_days"])
        ent_reg = er.async_get(hass)
        removed = 0
        for cfg in list(hass.config_entries.async_entries("mobile_app")):
            data = cfg.data or {}
            if data.get("app_id") != APP_ID and data.get("app_name") != APP_NAME:
                continue
            trackers = [
                e.entity_id
                for e in er.async_entries_for_config_entry(ent_reg, cfg.entry_id)
                if e.domain == "device_tracker"
            ]
            newest = None
            for entity_id in trackers:
                state = hass.states.get(entity_id)
                if state and (newest is None or state.last_updated > newest):
                    newest = state.last_updated
            # بنمسح بس لو عنده تحديث قديم فعلاً — مابنلمسش جهاز لسه بيحدّث
            # ولا جهاز لسه اتسجّل ومابعتش موقع (newest = None).
            if newest is None or newest >= cutoff:
                continue
            await hass.config_entries.async_remove(cfg.entry_id)
            removed += 1
        hass.bus.async_fire(f"{DOMAIN}_trackers_cleaned", {"removed": removed})
        return {"removed": removed}

    async def handle_request_live(call: ServiceCall) -> None:
        """يطلق حدث طلب موقع لايف لفرد. متاح لأي فرد مصرّح له (مش أدمن بس)."""
        hass.bus.async_fire(EVENT_LIVE_REQUEST, {"entity_id": call.data["entity_id"]})

    if not hass.services.has_service(DOMAIN, SERVICE_SET_CONFIG):
        hass.services.async_register(
            DOMAIN, SERVICE_SET_CONFIG, handle_set, schema=SET_CONFIG_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_ROLLBACK, handle_rollback, schema=ROLLBACK_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, SERVICE_CLEAR, handle_clear, schema=CLEAR_SCHEMA
        )
        hass.services.async_register(
            DOMAIN,
            SERVICE_CLEANUP_TRACKERS,
            handle_cleanup,
            schema=CLEANUP_SCHEMA,
            supports_response=SupportsResponse.OPTIONAL,
        )
        hass.services.async_register(
            DOMAIN, SERVICE_REQUEST_LIVE, handle_request_live, schema=REQUEST_LIVE_SCHEMA
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            for service in (
                SERVICE_SET_CONFIG,
                SERVICE_ROLLBACK,
                SERVICE_CLEAR,
                SERVICE_CLEANUP_TRACKERS,
                SERVICE_REQUEST_LIVE,
            ):
                hass.services.async_remove(DOMAIN, service)
    return unloaded
