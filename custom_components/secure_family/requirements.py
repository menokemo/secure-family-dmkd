"""فحص متطلبات Secure Family داخل Home Assistant.

بيبصّ على HA ويقول إيه المتوفّر وإيه الناقص من اللي التطبيق بيعتمد عليه:
منطقة البيت، الإنذار، كاميرات، أشخاص، تكامل mobile_app، ومصادر المخاطر
(geo_location). واعي بالدولة: يرشّح المصادر المناسبة ونطاق كوارث افتراضي.

كله قراية فقط (read-only) — مابيغيّرش أي حاجة في HA، بس بيرشد الأدمن.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

# مصادر geo_location للمخاطر المعروفة (محايد: دي توصيات، التطبيق بيعرض أي مصدر).
#  - gdacs / usgs_earthquakes_feed تكاملات أساسية في HA.
#  - 112hier مصدر هولندي شائع (تكامل مخصّص) — بنكتشفه بوجود كيانات geo_location.
HAZARD_SOURCE_DOMAINS = ("gdacs", "usgs_earthquakes_feed", "nsw_rural_fire_service_feed", "geonetnz_quakes")

# توصية المصادر ونطاق الكوارث (كم) حسب الدولة. الباقي بياخد الافتراضي.
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

# ترجمة النصوص (نفس لغات التطبيق). بنختار حسب hass.config.language.
_STR = {
    "en": {
        "home_zone": "Home zone",
        "home_zone_hint": "A 'Home' zone is required for presence and hazard distance.",
        "alarm": "Alarm panel",
        "alarm_hint": "Install Alarmo (or any alarm_control_panel) for the Alarm tab.",
        "camera": "Cameras",
        "camera_hint": "Add at least one camera for the Cameras tab and the doorbell.",
        "person": "People",
        "person_hint": "Person entities are needed to show family on the map.",
        "mobile_app": "Mobile App integration",
        "mobile_app_hint": "The Home Assistant Companion/mobile_app integration tracks location.",
        "hazards": "Hazard sources",
        "hazards_hint": "Add a geo_location source so road, weather and disaster alerts appear.",
        "ok": "Ready",
        "missing": "Missing",
        "recommend": "Recommended for your country",
        "disaster_km": "Suggested disaster radius",
    },
    "nl": {
        "home_zone": "Thuiszone",
        "home_zone_hint": "Een 'Home'-zone is nodig voor aanwezigheid en gevarenafstand.",
        "alarm": "Alarmpaneel",
        "alarm_hint": "Installeer Alarmo (of een alarm_control_panel) voor het Alarm-tabblad.",
        "camera": "Camera's",
        "camera_hint": "Voeg minstens één camera toe voor Camera's en de deurbel.",
        "person": "Personen",
        "person_hint": "Person-entiteiten zijn nodig om het gezin op de kaart te tonen.",
        "mobile_app": "Mobiele app-integratie",
        "mobile_app_hint": "De Companion/mobile_app-integratie houdt de locatie bij.",
        "hazards": "Gevarenbronnen",
        "hazards_hint": "Voeg een geo_location-bron toe voor verkeer, weer en rampen.",
        "ok": "Gereed",
        "missing": "Ontbreekt",
        "recommend": "Aanbevolen voor jouw land",
        "disaster_km": "Voorgestelde rampstraal",
    },
    "ar": {
        "home_zone": "منطقة البيت",
        "home_zone_hint": "منطقة «Home» لازمة للحضور وحساب مسافة المخاطر.",
        "alarm": "لوحة الإنذار",
        "alarm_hint": "ثبّت Alarmo (أو أي alarm_control_panel) عشان تبويب الإنذار.",
        "camera": "الكاميرات",
        "camera_hint": "أضف كاميرا واحدة على الأقل لتبويب الكاميرات وجرس الباب.",
        "person": "الأشخاص",
        "person_hint": "كيانات person لازمة عشان تظهر العيلة على الخريطة.",
        "mobile_app": "تكامل mobile_app",
        "mobile_app_hint": "تكامل الموبايل (Companion) بيتتبّع الموقع.",
        "hazards": "مصادر المخاطر",
        "hazards_hint": "أضف مصدر geo_location عشان تظهر بلاغات الطرق والطقس والكوارث.",
        "ok": "جاهز",
        "missing": "ناقص",
        "recommend": "موصى بيه لدولتك",
        "disaster_km": "نطاق الكوارث المقترح",
    },
}


def _t(lang: str) -> dict:
    return _STR.get(lang, _STR["en"])


def _has_domain_entities(hass: HomeAssistant, domain: str) -> bool:
    return bool(hass.states.async_entity_ids(domain))


def _has_config_entry(hass: HomeAssistant, domain: str) -> bool:
    return bool(hass.config_entries.async_entries(domain))


@callback
def build_status(hass: HomeAssistant) -> dict:
    """يرجّع حالة كل متطلب + توصيات الدولة. قراية فقط."""
    lang = (hass.config.language or "en")[:2]
    tr = _t(lang)
    country = hass.config.country

    # زون البيت: كيان zone.home موجود.
    has_home = "zone.home" in hass.states.async_entity_ids("zone")

    # مصادر المخاطر: أي كيان geo_location، أو أي تكامل مخاطر معروف متركّب.
    has_geo_entities = _has_domain_entities(hass, "geo_location")
    installed_sources = [d for d in HAZARD_SOURCE_DOMAINS if _has_config_entry(hass, d)]
    has_hazards = has_geo_entities or bool(installed_sources)

    defaults = COUNTRY_DEFAULTS.get((country or "").upper(), {})
    recommended = defaults.get("sources", DEFAULT_SOURCES)
    disaster_km = defaults.get("disaster_km", DEFAULT_DISASTER_KM)

    items = [
        {
            "key": "home_zone",
            "ok": has_home,
            "label": tr["home_zone"],
            "hint": tr["home_zone_hint"],
            "add": None,  # الزون بتتعمل من Settings → Areas & Zones
            "add_path": "/config/zone/dashboard",
        },
        {
            "key": "alarm",
            "ok": _has_domain_entities(hass, "alarm_control_panel"),
            "label": tr["alarm"],
            "hint": tr["alarm_hint"],
            "add": "alarmo",
        },
        {
            "key": "camera",
            "ok": _has_domain_entities(hass, "camera"),
            "label": tr["camera"],
            "hint": tr["camera_hint"],
            "add": None,
        },
        {
            "key": "person",
            "ok": _has_domain_entities(hass, "person"),
            "label": tr["person"],
            "hint": tr["person_hint"],
            "add": "person",
            "add_path": "/config/person",
        },
        {
            "key": "mobile_app",
            "ok": _has_config_entry(hass, "mobile_app") or _has_domain_entities(hass, "device_tracker"),
            "label": tr["mobile_app"],
            "hint": tr["mobile_app_hint"],
            "add": "mobile_app",
        },
        {
            "key": "hazards",
            "ok": has_hazards,
            "label": tr["hazards"],
            "hint": tr["hazards_hint"],
            # زرار الإضافة بيوديه لأول مصدر موصى بيه مش متركّب.
            "add": next((s for s in recommended if not _has_config_entry(hass, s)), recommended[0]),
        },
    ]

    return {
        "country": country,
        "language": lang,
        "items": items,
        "installed_sources": installed_sources,
        "recommended_sources": recommended,
        "disaster_km": disaster_km,
        "labels": {
            "ok": tr["ok"],
            "missing": tr["missing"],
            "recommend": tr["recommend"],
            "disaster_km": tr["disaster_km"],
        },
    }
