"""إدارة أجهزة التطبيق: جهاز نشط واحد لكل مستخدم + موافقة الأدمن بكود.

المنطق كله هنا (منفصل عن __init__.py عشان الملفات تفضل صغيرة ومنظمة للصيانة).
الأمان: الكود سرّي ومابيتبعتش في أي حدث/إشعار مبثوث — بيتخزّن هنا وبييجي للأدمن
بس عبر خدمة محصورة على الأدمن. الاستبدال بيمسح الجهاز القديم ويسجّل خروجه فورًا.

mkdd — Secure Family
"""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from .const import (
    APPROVAL_CODE_TTL_MIN,
    APPROVAL_MAX_ATTEMPTS,
    EVENT_APPROVAL_REQUEST,
    EVENT_DEVICE_APPROVED,
    EVENT_FORCE_LOGOUT,
    NOTIFY_PREFIX,
)
from .device_store import DeviceStore

_LOGGER = logging.getLogger(__name__)


class DeviceManager:
    """بيدير تسجيل أجهزة التطبيق وموافقات الاستبدال."""

    def __init__(self, hass: HomeAssistant, store: DeviceStore) -> None:
        self._hass = hass
        self._store = store

    # ---------- مساعدات ----------

    def _find_entry_by_webhook(self, webhook_id: str | None) -> ConfigEntry | None:
        """يلاقي config entry بتاع mobile_app بالـ webhook_id بتاعه."""
        if not webhook_id:
            return None
        for entry in self._hass.config_entries.async_entries("mobile_app"):
            if (entry.data or {}).get("webhook_id") == webhook_id:
                return entry
        return None

    @staticmethod
    def _new_code() -> str:
        """كود 6 أرقام قوي عشوائيًا (crypto)."""
        return f"{secrets.randbelow(1_000_000):06d}"

    def _rename_device(self, webhook_id: str | None, name: str) -> None:
        """يسمّي جهاز mobile_app (بالـ webhook) باسم المستخدم/المخصّص — بيحط
        name_by_user زي ما HA بيعمل عند إعادة التسمية اليدوية (موثوق)."""
        if not webhook_id or not name:
            return
        entry = self._find_entry_by_webhook(webhook_id)
        if entry is None:
            return
        dev_reg = dr.async_get(self._hass)
        for device in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
            if device.name_by_user != name:
                dev_reg.async_update_device(device.id, name_by_user=name)

    async def check(
        self, user_id: str, user_name: str, device_id: str, name: str
    ) -> dict:
        """قبل أي تسجيل: لو نفس الموبايل عنده تسجيل شغّال (الجهاز لسه موجود في
        HA) → بنعيد استخدام نفس الـ webhook (صفر جهاز جديد، صفر تشويش) ونسمّيه.
        غير كده → register (التطبيق يكمّل التسجيل العادي)."""
        self._prune_expired()
        active = self._store.active.get(user_id)
        effective = (name or "").strip() or user_name
        if (
            active is not None
            and active.get("device_id") == device_id
            and self._find_entry_by_webhook(active.get("webhook_id")) is not None
        ):
            self._rename_device(active.get("webhook_id"), effective)
            if active.get("name") != effective:
                active["name"] = effective
                await self._store.async_save()
            return {"action": "reuse", "webhook_id": active["webhook_id"]}
        return {"action": "register"}

    def _prune_expired(self) -> bool:
        """يشيل الطلبات المنتهية ويلغي إشعاراتها. بيرجّع True لو اتغيّر حاجة."""
        now = dt_util.utcnow()
        expired = [
            rid
            for rid, p in self._store.pending.items()
            if dt_util.parse_datetime(p["expires_at"]) is not None
            and dt_util.parse_datetime(p["expires_at"]) < now
        ]
        for rid in expired:
            self._store.pending.pop(rid, None)
            self._clear_notification(rid)
        return bool(expired)

    def _clear_notification(self, request_id: str) -> None:
        self._hass.async_create_task(
            self._hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": NOTIFY_PREFIX + request_id},
                blocking=False,
            )
        )

    async def _notify_admins(self, request_id: str, pending: dict) -> None:
        """تنبيه بدون كود: حدث لتطبيقات الأدمن + إشعار ثابت في HA."""
        self._hass.bus.async_fire(
            EVENT_APPROVAL_REQUEST,
            {
                "request_id": request_id,
                "user_id": pending["user_id"],
                "user_name": pending["user_name"],
                "new_device_name": pending["name"],
                "old_device_name": pending["old_name"],
            },
        )
        await self._hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "notification_id": NOTIFY_PREFIX + request_id,
                "title": "Secure Family — طلب جهاز جديد",
                "message": (
                    f"جهاز جديد «{pending['name']}» عايز يدخل بحساب "
                    f"«{pending['user_name']}» بدل «{pending['old_name']}».\n"
                    "افتح Secure Family كأدمن للموافقة أو الرفض."
                ),
            },
            blocking=False,
        )

    # ---------- العمليات ----------

    async def request(
        self,
        user_id: str,
        user_name: str,
        device_id: str,
        webhook_id: str,
        name: str,
    ) -> dict:
        """طلب تسجيل جهاز. بيرجّع approved فورًا لو أول جهاز أو نفس الجهاز،
        وإلا pending مع تنبيه الأدمن (من غير كود للجهاز الجديد)."""
        self._prune_expired()
        active = self._store.active.get(user_id)
        now = dt_util.utcnow().isoformat()

        if active is None or active.get("device_id") == device_id:
            # أول جهاز أو نفس الجهاز بيعيد التسجيل — موافقة مباشرة، صفر تكرار.
            effective = (name or "").strip() or user_name
            # لو نفس الموبايل سجّل بـ webhook جديد — امسح جهازه القديم في HA
            # عشان مايتراكمش تكرار (ده بيحصل لو الـ webhook القديم اتفقد).
            old_webhook = active.get("webhook_id") if active else None
            if old_webhook and old_webhook != webhook_id:
                old_entry = self._find_entry_by_webhook(old_webhook)
                if old_entry is not None:
                    await self._hass.config_entries.async_remove(old_entry.entry_id)
            self._store.active[user_id] = {
                "device_id": device_id,
                "webhook_id": webhook_id,
                "name": effective,
                "registered_at": now,
            }
            # نسمّي الجهاز باسم المستخدم (أو الاسم المخصّص) تلقائيًا من أول مرة.
            self._rename_device(webhook_id, effective)
            # أي طلبات معلّقة لنفس المستخدم بقت ملهاش لازمة.
            for rid in [
                r for r, p in self._store.pending.items() if p["user_id"] == user_id
            ]:
                self._store.pending.pop(rid, None)
                self._clear_notification(rid)
            await self._store.async_save()
            return {"status": "approved"}

        # جهاز مختلف والحساب نشط — محتاج موافقة أدمن.
        request_id = secrets.token_hex(4)
        self._store.pending[request_id] = {
            "user_id": user_id,
            "user_name": user_name,
            "device_id": device_id,
            "webhook_id": webhook_id,
            "name": name,
            "old_device_id": active["device_id"],
            "old_webhook_id": active.get("webhook_id"),
            "old_name": active.get("name", ""),
            "code": self._new_code(),
            "expires_at": (
                dt_util.utcnow() + timedelta(minutes=APPROVAL_CODE_TTL_MIN)
            ).isoformat(),
            "attempts": 0,
        }
        await self._store.async_save()
        await self._notify_admins(request_id, self._store.pending[request_id])
        _LOGGER.info(
            "Secure Family: pending device approval %s for user %s",
            request_id,
            user_name,
        )
        return {
            "status": "pending",
            "request_id": request_id,
            "old_device_name": active.get("name", ""),
        }

    async def _activate(self, request_id: str, pending: dict) -> dict:
        """ينفّذ الاستبدال: يمسح الجهاز القديم، يبعت خروج فوري، يفعّل الجديد."""
        old_entry = self._find_entry_by_webhook(pending.get("old_webhook_id"))
        if old_entry is not None:
            await self._hass.config_entries.async_remove(old_entry.entry_id)
        self._hass.bus.async_fire(
            EVENT_FORCE_LOGOUT,
            {
                "device_id": pending["old_device_id"],
                "webhook_id": pending.get("old_webhook_id"),
            },
        )
        # الجهاز الجديد بيسمع ده (بمطابقة device_id) فيعرف إنه اتفعّل.
        self._hass.bus.async_fire(
            EVENT_DEVICE_APPROVED, {"device_id": pending["device_id"]}
        )
        self._store.active[pending["user_id"]] = {
            "device_id": pending["device_id"],
            "webhook_id": pending["webhook_id"],
            "name": pending["name"],
            "registered_at": dt_util.utcnow().isoformat(),
        }
        self._store.pending.pop(request_id, None)
        self._clear_notification(request_id)
        await self._store.async_save()
        _LOGGER.info(
            "Secure Family: approved device %s for user %s (old signed out)",
            pending["name"],
            pending["user_name"],
        )
        return {"status": "approved"}

    async def approve(
        self, request_id: str | None, code: str | None, is_admin: bool
    ) -> dict:
        """موافقة إما بـ request_id من أدمن، أو بالكود من الجهاز الجديد.
        الكود نفسه إثبات موافقة الأدمن (وصل للأدمن بس)."""
        self._prune_expired()

        if request_id and is_admin:
            pending = self._store.pending.get(request_id)
            if pending is None:
                raise HomeAssistantError("Approval request not found or expired.")
            return await self._activate(request_id, pending)

        if code:
            for rid, pending in list(self._store.pending.items()):
                if pending["code"] == code:
                    return await self._activate(rid, pending)
            # كود غلط — نزوّد العداد على كل الطلبات المعلّقة ونقفل اللي وصلت الحد.
            changed = False
            for rid, pending in list(self._store.pending.items()):
                pending["attempts"] += 1
                if pending["attempts"] >= APPROVAL_MAX_ATTEMPTS:
                    self._store.pending.pop(rid, None)
                    self._clear_notification(rid)
                changed = True
            if changed:
                await self._store.async_save()
            raise HomeAssistantError("Invalid or expired approval code.")

        raise HomeAssistantError("Provide an admin request_id or an approval code.")

    async def deny(self, request_id: str) -> dict:
        """رفض طلب (أدمن): يمسح تسجيل الجهاز الجديد المعلّق ويلغي الطلب."""
        self._prune_expired()
        pending = self._store.pending.pop(request_id, None)
        if pending is None:
            raise HomeAssistantError("Approval request not found or expired.")
        self._clear_notification(request_id)
        new_entry = self._find_entry_by_webhook(pending.get("webhook_id"))
        if new_entry is not None:
            await self._hass.config_entries.async_remove(new_entry.entry_id)
        await self._store.async_save()
        return {"status": "denied"}

    def list_pending(self) -> list[dict]:
        """قائمة الطلبات المعلّقة بالأكواد — للأدمن بس (الاستدعاء بيتحقق)."""
        self._prune_expired()
        return [
            {
                "request_id": rid,
                "user_name": p["user_name"],
                "new_device_name": p["name"],
                "old_device_name": p["old_name"],
                "code": p["code"],
                "expires_at": p["expires_at"],
            }
            for rid, p in self._store.pending.items()
        ]
