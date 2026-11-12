"""Persistent storage for the family configuration.

بيخزّن إعداد العيلة كـJSON في .storage الخاص بـHome Assistant، فبيفضل ثابت
بعد أي restart. بيحتفظ كمان بتاريخ النسخ السابقة عشان الـrollback.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import MAX_HISTORY, STORAGE_KEY, STORAGE_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty() -> dict[str, Any]:
    return {
        "config": {},
        "version": 0,
        "updated_at": None,
        "updated_by": None,
        "history": [],
    }


class ConfigStore:
    """يغلّف helpers.storage.Store ويدير النسخ والتاريخ."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = _empty()

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @property
    def config(self) -> dict[str, Any]:
        return self._data.get("config", {})

    @property
    def version(self) -> int:
        return int(self._data.get("version", 0))

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self._data = {**_empty(), **stored}

    async def async_set(
        self, config: dict[str, Any], user_name: str | None
    ) -> dict[str, Any]:
        """يحفظ إعداد جديد، ويدفع النسخة الحالية لأعلى التاريخ."""
        history = list(self._data.get("history", []))
        if self._data.get("version"):
            history.insert(
                0,
                {
                    "config": self._data.get("config", {}),
                    "version": self._data.get("version"),
                    "updated_at": self._data.get("updated_at"),
                    "updated_by": self._data.get("updated_by"),
                },
            )
            history = history[:MAX_HISTORY]
        self._data = {
            "config": config,
            "version": self.version + 1,
            "updated_at": _now(),
            "updated_by": user_name,
            "history": history,
        }
        await self._store.async_save(self._data)
        return self._data

    async def async_rollback(
        self, version: int | None, user_name: str | None
    ) -> dict[str, Any]:
        """يرجّع لإعداد سابق (أحدث نسخة في التاريخ لو مفيش version محدّد)."""
        history = self._data.get("history", [])
        if not history:
            return self._data
        target = (
            history[0]
            if version is None
            else next((h for h in history if h.get("version") == version), None)
        )
        if target is None:
            return self._data
        return await self.async_set(target.get("config", {}), user_name)

    async def async_clear(self, user_name: str | None) -> dict[str, Any]:
        return await self.async_set({}, user_name)
