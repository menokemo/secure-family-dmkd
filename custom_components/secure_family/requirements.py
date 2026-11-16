"""فحص متطلبات Secure Family + كتالوج الإضافات — داخل Home Assistant.

بيبصّ على HA (قراية فقط) ويرجّع **بيانات منظّمة بس** من غير أي نص مترجم:
إيه المتوفّر وإيه الناقص من اللي التطبيق بيعتمد عليه (منطقة البيت، الإنذار،
كاميرات، أشخاص، mobile_app، مصادر المخاطر geo_location)، وكمان إيه الإضافات
الاختيارية اللي ينفع تتضاف (عالمية للكل + خاصة بالدولة).

كل الترجمة بتحصل في الواجهة (JS) حسب لغة **واجهة المستخدم** مش لغة السيرفر،
عشان الصفحة تبقى بلغة واحدة متّسقة. هنا بنرجّع مفاتيح (keys) بس.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

# مصادر geo_location للمخاطر المعروفة — بنكتشف المتركّب منها.
HAZARD_SOURCE_DOMAINS = (
    "gdacs",
    "usgs_earthquakes_feed",
    "nsw_rural_fire_service_feed",
    "geonetnz_quakes",
    "geonetnz_volcano",
)

# نطاق الكوارث المقترح (كم) والمصادر الموصى بيها حسب الدولة.
COUNTRY_DEFAULTS: dict[str, dict] = {
    "NL": {"sources": ["gdacs", "usgs_earthquakes_feed"], "disaster_km": 150},
    "BE": {"sources": ["gdacs", "usgs_earthquakes_feed"], "disaster_km": 150},
    "DE": {"sources": ["gdacs", "usgs_earthquakes_feed"], "disaster_km": 200},
    "US": {"sources": ["usgs_earthquakes_feed", "gdacs"], "disaster_km": 300},
    "AU": {"sources": ["nsw_rural_fire_service_feed", "gdacs"], "disaster_km": 400},
    "NZ": {"sources": ["geonetnz_quakes", "gdacs"], "disaster_km": 300},
}
DEFAULT_DISASTER_KM = 150
DEFAULT_SOURCES = ["gdacs", "usgs_earthquakes_feed"]

# ===== كتالوج الإضافات الاختيارية =====
# كل إضافة: key (للترجمة في الواجهة) · domain (تكامل HA للكشف وزرار الإضافة)
#   · add_url (بديل: لينك توثيق لو مفيش تكامل أساسي يتضاف من اللوحة).
# العالمية بتظهر لكل الدول؛ الخاصة بالدولة بتظهر لدولتها بس.
GLOBAL_ADDONS = [
    {"key": "gdacs", "domain": "gdacs"},
    {"key": "usgs_quakes", "domain": "usgs_earthquakes_feed"},
]
COUNTRY_ADDONS: dict[str, list[dict]] = {
    "NL": [{"key": "p2000", "domain": None, "add_url": "https://github.com/klaasnicolaas/home-assistant-p2000"}],
    "BE": [],
    "DE": [{"key": "dwd", "domain": "dwd_weather_warnings"}],
    "US": [{"key": "nws", "domain": "nws"}],
    "AU": [{"key": "nsw_fire", "domain": "nsw_rural_fire_service_feed"}],
    "NZ": [
        {"key": "geonet_quakes", "domain": "geonetnz_quakes"},
        {"key": "geonet_volcano", "domain": "geonetnz_volcano"},
    ],
}


def _has_domain_entities(hass: HomeAssistant, domain: str) -> bool:
    return bool(hass.states.async_entity_ids(domain))


def _has_config_entry(hass: HomeAssistant, domain: str) -> bool:
    return bool(hass.config_entries.async_entries(domain))


def _addon_entry(hass: HomeAssistant, spec: dict, scope: str) -> dict:
    """يحوّل تعريف إضافة لعنصر جاهز للواجهة (مع حالة التركيب)."""
    domain = spec.get("domain")
    installed = bool(domain) and (
        _has_config_entry(hass, domain) or _has_domain_entities(hass, domain)
    )
    return {
        "key": spec["key"],
        "scope": scope,
        "domain": domain,
        "add_url": spec.get("add_url"),
        "installed": installed,
    }


@callback
def build_addons(hass: HomeAssistant, country: str | None) -> list[dict]:
    """قائمة الإضافات الموصى بيها: عالمية للكل + الخاصة بالدولة."""
    out = [_addon_entry(hass, s, "global") for s in GLOBAL_ADDONS]
    for s in COUNTRY_ADDONS.get((country or "").upper(), []):
        out.append(_addon_entry(hass, s, "country"))
    return out


@callback
def build_status(hass: HomeAssistant) -> dict:
    """حالة كل متطلب + توصيات الدولة + الإضافات. بيانات بس (من غير ترجمة)."""
    country = hass.config.country

    has_home = "zone.home" in hass.states.async_entity_ids("zone")
    installed_sources = [d for d in HAZARD_SOURCE_DOMAINS if _has_config_entry(hass, d)]
    has_hazards = _has_domain_entities(hass, "geo_location") or bool(installed_sources)

    defaults = COUNTRY_DEFAULTS.get((country or "").upper(), {})
    recommended = defaults.get("sources", DEFAULT_SOURCES)
    disaster_km = defaults.get("disaster_km", DEFAULT_DISASTER_KM)

    items = [
        {"key": "home_zone", "ok": has_home, "add": None, "add_path": "/config/zone/dashboard"},
        {"key": "alarm", "ok": _has_domain_entities(hass, "alarm_control_panel"), "add": "alarmo"},
        {"key": "camera", "ok": _has_domain_entities(hass, "camera"), "add": None},
        {"key": "person", "ok": _has_domain_entities(hass, "person"), "add": "person", "add_path": "/config/person"},
        {
            "key": "mobile_app",
            "ok": _has_config_entry(hass, "mobile_app") or _has_domain_entities(hass, "device_tracker"),
            "add": "mobile_app",
        },
        {
            "key": "hazards",
            "ok": has_hazards,
            "add": next((s for s in recommended if not _has_config_entry(hass, s)), recommended[0]),
        },
    ]

    return {
        "country": country,
        "language": (hass.config.language or "en")[:2],  # للعلم فقط — الواجهة بتترجم بلغتها
        "items": items,
        "installed_sources": installed_sources,
        "recommended_sources": recommended,
        "disaster_km": disaster_km,
        "addons": build_addons(hass, country),
    }
