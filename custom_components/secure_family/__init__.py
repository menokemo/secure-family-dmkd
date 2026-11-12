"""The Secure Family integration.

مخزن إعداد مركزي للعيلة داخل Home Assistant: الأدمن ينشر الإعداد من التطبيق،
وباقي الأجهزة تقراه فورًا (local push) وتطبّقه عند الدخول. كله محلي على الشبكة،
والكتابة للأدمن بس.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    EVENT_UPDATED,
    SERVICE_CLEAR,
    SERVICE_ROLLBACK,
    SERVICE_SET_CONFIG,
    SIGNAL_UPDATE,
)
from .store import ConfigStore

PLATFORMS = ["sensor", "binary_sensor"]

SET_CONFIG_SCHEMA = vol.Schema({vol.Required("config"): dict})
ROLLBACK_SCHEMA = vol.Schema({vol.Optional("version"): int})
CLEAR_SCHEMA = vol.Schema({})


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            for service in (SERVICE_SET_CONFIG, SERVICE_ROLLBACK, SERVICE_CLEAR):
                hass.services.async_remove(DOMAIN, service)
    return unloaded
