"""تخزين دائم لأجهزة Secure Family: الجهاز النشط لكل مستخدم + طلبات الموافقة
المعلّقة. بيعيش في .storage فبيفضل بعد أي restart.

mkdd — Secure Family
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DEVICE_STORAGE_KEY, DEVICE_STORAGE_VERSION


class DeviceStore:
    """يحفظ ويقرأ الأجهزة النشطة والطلبات المعلّقة.

    الشكل:
      active:  { user_id: {device_id, webhook_id, name, registered_at} }
      pending: { request_id: {user_id, user_name, device_id, webhook_id, name,
                              old_device_id, old_webhook_id, old_name, code,
                              expires_at, attempts} }
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store(hass, DEVICE_STORAGE_VERSION, DEVICE_STORAGE_KEY)
        self._data: dict[str, dict] = {"active": {}, "pending": {}}

    async def async_load(self) -> dict:
        data = await self._store.async_load()
        if isinstance(data, dict):
            self._data = {
                "active": dict(data.get("active") or {}),
                "pending": dict(data.get("pending") or {}),
            }
        return self._data

    @property
    def active(self) -> dict[str, dict]:
        return self._data["active"]

    @property
    def pending(self) -> dict[str, dict]:
        return self._data["pending"]

    async def async_save(self) -> None:
        await self._store.async_save(self._data)
