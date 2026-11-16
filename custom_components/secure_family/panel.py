"""صفحة Secure Family في الشريط الجانبي + أمر websocket للفحص.

الأدمن بيفتح الصفحة من القائمة الجانبية فيلاقي checklist بالناقص وأزرار إضافة.
كله جوّه المكوّن — التطبيق مايتزحمش بأي إعداد تقني.
"""

from __future__ import annotations

import json
import logging
import os

import voluptuous as vol

from homeassistant.components import panel_custom, websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .requirements import build_status
from .store import ConfigStore

_LOGGER = logging.getLogger(__name__)


def _version() -> str:
    """رقم إصدار المكوّن من manifest — نستعمله لكسر كاش المتصفح."""
    try:
        path = os.path.join(os.path.dirname(__file__), "manifest.json")
        with open(path, encoding="utf-8") as fh:
            return str(json.load(fh).get("version", "0"))
    except Exception:  # noqa: BLE001 — لو فشل القراية نرجّع 0 (مش مشكلة حرجة)
        return "0"


PANEL_URL_PATH = "secure-family"  # مسار الصفحة في الشريط الجانبي
PANEL_JS_PATH = "/secure_family_static/secure-family-panel.js"  # المسار الثابت للملف
# الرابط اللي بيتحمّل منه الـweb component — بزيادة ?v=الإصدار عشان المتصفح يجيب
# النسخة الجديدة بعد كل تحديث بدل الكاش القديم (مشكلة كاش لوحات HA المعروفة).
PANEL_JS_URL = f"{PANEL_JS_PATH}?v={_version()}"
PANEL_TITLE = "Secure Family"
PANEL_ICON = "mdi:shield-home"
WS_TYPE = "secure_family/requirements"
WS_GET_CONFIG = "secure_family/get_config"
_FLAG = "_panel_registered"


def _find_store(hass: HomeAssistant) -> ConfigStore | None:
    """بيلاقي مخزن الإعداد وسط بيانات المكوّن (مفتاحه هو entry_id)."""
    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, ConfigStore):
            return value
    return None


@websocket_api.websocket_command({vol.Required("type"): WS_TYPE})
@callback
def _ws_requirements(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """يرجّع حالة الفحص. للأدمن بس (نفس سياسة باقي المكوّن)."""
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admins only")
        return
    connection.send_result(msg["id"], build_status(hass))


@websocket_api.websocket_command({vol.Required("type"): WS_GET_CONFIG})
@callback
def _ws_get_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """يرجّع إعداد العيلة المنشور الحالي + نسخته. للأدمن بس.

    الكتابة بتتم عبر خدمة secure_family.set_config الموجودة (أدمن بس كمان).
    """
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admins only")
        return
    store = _find_store(hass)
    connection.send_result(
        msg["id"],
        {
            "config": store.config if store else {},
            "version": store.version if store else 0,
        },
    )


async def async_setup_panel(hass: HomeAssistant) -> None:
    """يسجّل الصفحة والـwebsocket مرة واحدة (حتى لو في أكتر من config entry).

    كل تسجيل متسامح مع إعادة التحميل (لو اتسجّل قبل كده مابيكسرش).
    """
    if hass.data.get(DOMAIN, {}).get(_FLAG):
        return

    # أوامر الـwebsocket اللي الصفحة بتقرا منها (الفحص + الإعداد الحالي).
    for command in (_ws_requirements, _ws_get_config):
        try:
            websocket_api.async_register_command(hass, command)
        except Exception:  # noqa: BLE001 — متسجّل قبل كده (reload)
            pass

    # نخدم ملف الواجهة (JS). الـAPI الحديث async_register_static_paths، ونرجع
    # للقديم لو core أقدم.
    js_path = os.path.join(os.path.dirname(__file__), "frontend", "secure-family-panel.js")
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(PANEL_JS_PATH, js_path, False)]
        )
    except (ImportError, AttributeError):
        try:
            hass.http.register_static_path(PANEL_JS_PATH, js_path, False)
        except Exception:  # noqa: BLE001
            pass
    except Exception:  # noqa: BLE001 — المسار متسجّل قبل كده
        pass

    # نسجّل الصفحة في الشريط الجانبي (أدمن فقط).
    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name="secure-family-panel",
            module_url=PANEL_JS_URL,
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            require_admin=True,
            config={},
            embed_iframe=False,
        )
    except ValueError:
        # متسجّلة قبل كده (مثلاً إعادة تحميل) — عادي.
        pass

    hass.data.setdefault(DOMAIN, {})[_FLAG] = True


@callback
def async_remove_panel(hass: HomeAssistant) -> None:
    """يشيل الصفحة من الشريط الجانبي عند إزالة آخر config entry."""
    if not hass.data.get(DOMAIN, {}).get(_FLAG):
        return
    try:
        from homeassistant.components import frontend

        frontend.async_remove_panel(hass, PANEL_URL_PATH)
    except (ImportError, Exception):  # noqa: BLE001 — إزالة أفضل جهد
        pass
    hass.data.get(DOMAIN, {}).pop(_FLAG, None)
