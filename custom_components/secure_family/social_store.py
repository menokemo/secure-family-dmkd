"""مخزن «شبكة العيلة» المحلي: الحائط (بوستات) + الشات (رسائل) + المهام
الموزّعة — كله نص بسيط في .storage الخاص بـHome Assistant، بحد أقصى فالحجم
يفضل ثابت ومايكبرش. مفيش سيرفر خارجي: الكتابة عبر سيرفسات المكوّن، والقراية
عبر كيانات sensor (attributes) اللي حتى غير الأدمن بيشوفها عبر state_changed.
"""

from __future__ import annotations

import time
import uuid
from datetime import date
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .chore_recurrence import REPEATS, next_due, parse_date
from .const import DOMAIN

SOCIAL_STORAGE_VERSION = 1
SOCIAL_STORAGE_KEY = f"{DOMAIN}_social"

# حدود عشان التخزين يفضل ثابت (نص خفيف أصلاً، بس نمنع النمو اللانهائي).
WALL_MAX = 200
CHAT_MAX = 300
CHORES_MAX = 300


def _now() -> float:
    return time.time()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


class SocialStore:
    """مخزن مشترك للحائط/الشات/المهام (ملف .storage واحد)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict] = Store(hass, SOCIAL_STORAGE_VERSION, SOCIAL_STORAGE_KEY)
        self.data: dict[str, list[dict[str, Any]]] = {"wall": [], "chat": [], "chores": []}

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            for key in ("wall", "chat", "chores"):
                self.data[key] = list(stored.get(key, []))

    async def _save(self) -> None:
        await self._store.async_save(self.data)

    # ===== الحائط =====
    async def add_post(self, person: str | None, name: str, text: str) -> dict:
        item = {"id": _new_id(), "ts": _now(), "person": person, "name": name, "text": text}
        self.data["wall"].append(item)
        self.data["wall"] = self.data["wall"][-WALL_MAX:]
        await self._save()
        return item

    # ===== الشات =====
    async def add_message(self, person: str | None, name: str, text: str) -> dict:
        item = {"id": _new_id(), "ts": _now(), "person": person, "name": name, "text": text}
        self.data["chat"].append(item)
        self.data["chat"] = self.data["chat"][-CHAT_MAX:]
        await self._save()
        return item

    # ===== المهام الموزّعة =====
    async def add_chore(
        self,
        assignee: str | None,
        assignee_name: str,
        title: str,
        category: str | None = None,
        due: str | None = None,
        repeat: str = "none",
        note: str | None = None,
    ) -> dict:
        if repeat not in REPEATS:
            repeat = "none"
        item = {
            "id": _new_id(),
            "ts": _now(),
            "person": assignee,      # الفرد المسنّدة له المهمة
            "name": assignee_name,
            "title": title,
            "done": False,
            "category": (category or "") or None,
            "due": (due or "") or None,
            "repeat": repeat,
            "note": (note or "") or None,
        }
        self.data["chores"].append(item)
        self.data["chores"] = self.data["chores"][-CHORES_MAX:]
        await self._save()
        return item

    async def set_chore(self, chore_id: str, done: bool) -> bool:
        changed = False
        for c in self.data["chores"]:
            if c.get("id") != chore_id:
                continue
            repeat = c.get("repeat") or "none"
            # مهمة متكرّرة اتعملت → تتنقل لميعادها الجاي وترجع غير متعمولة،
            # بدل ما تتسجّل خلصانة (القرار المتّفق عليه: عنصر واحد حيّ لكل مهمة).
            if done and repeat != "none":
                base = parse_date(c.get("due")) or date.today()
                nxt = next_due(base, repeat)
                if nxt is not None:
                    c["due"] = nxt.isoformat()
                    c["done"] = False
                    changed = True
                break
            if c.get("done") != done:
                c["done"] = done
                changed = True
            break
        if changed:
            await self._save()
        return changed

    async def delete(self, section: str, item_id: str) -> bool:
        if section not in self.data:
            return False
        before = len(self.data[section])
        self.data[section] = [i for i in self.data[section] if i.get("id") != item_id]
        if len(self.data[section]) != before:
            await self._save()
            return True
        return False
