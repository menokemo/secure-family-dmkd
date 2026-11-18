// صفحة Secure Family في Home Assistant — ٣ أقسام:
//  (1) فحص المتطلبات (checklist بالناقص + أزرار إضافة).
//  (2) الإضافات الاختيارية (عالمية للكل + الخاصة بدولتك).
//  (3) إعدادات العيلة، مجمّعة في أقسام قابلة للطيّ زي أدمن التطبيق.
// web component خام (من غير بناء). القراية عبر websocket، والكتابة عبر خدمة
// secure_family.set_config (أدمن بس). كل النصوص بتتترجم هنا حسب لغة واجهتك،
// مش لغة السيرفر — عشان الصفحة تبقى بلغة واحدة متّسقة (عربي/هولندي/إنجليزي).

// ===== مجموعات الإعدادات (زي أكورديون الأدمن في التطبيق) =====
const GROUPS = [
  { key: "general", icon: "mdi:tune" },
  { key: "alarm", icon: "mdi:shield-lock", open: true },
  { key: "cameras", icon: "mdi:cctv" },
  { key: "doorbell", icon: "mdi:bell-ring" },
  { key: "location", icon: "mdi:map-marker-radius" },
  { key: "dashboard", icon: "mdi:view-dashboard" },
  { key: "family", icon: "mdi:calendar-account" },
  { key: "background", icon: "mdi:motion-sensor" },
];

// الحقول القابلة للتعديل. group = القسم · type = شكل عنصر التحكّم.
const FIELDS = [
  { key: "mapEngine", group: "general", type: "select", options: ["native", "web"], label: { en: "Map engine", nl: "Kaartengine", ar: "محرّك الخريطة" } },
  { key: "alarmEntityId", group: "alarm", type: "entity", domains: ["alarm_control_panel"], label: { en: "Alarm panel", nl: "Alarmpaneel", ar: "لوحة الإنذار" } },
  { key: "visibleAlarmModes", group: "alarm", type: "modes", label: { en: "Visible alarm modes", nl: "Zichtbare alarmmodi", ar: "أوضاع الإنذار الظاهرة" } },
  { key: "selectedSensorIds", group: "alarm", type: "entities", domains: ["binary_sensor"], alarmSensors: true, label: { en: "Manual alarm sensors", nl: "Handmatige alarmsensoren", ar: "حسّاسات الإنذار (يدوي)" } },
  { key: "directStatusChange", group: "alarm", type: "toggle", label: { en: "Direct status change", nl: "Directe statuswijziging", ar: "تغيير الحالة المباشر" } },
  { key: "showStatusBadge", group: "alarm", type: "toggle", label: { en: "Show status badge", nl: "Statusbadge tonen", ar: "إظهار شارة الحالة" } },
  { key: "selectedCameraIds", group: "cameras", type: "entities", domains: ["camera"], label: { en: "Cameras shown", nl: "Getoonde camera's", ar: "الكاميرات الظاهرة" } },
  { key: "snapshotRefreshSeconds", group: "cameras", type: "number", label: { en: "Snapshot refresh (s)", nl: "Snapshotverversing (s)", ar: "تحديث اللقطة (ث)" } },
  { key: "cameraColumns", group: "cameras", type: "select", options: ["1", "2"], coerce: "number", label: { en: "Camera columns", nl: "Cameramkolommen", ar: "أعمدة الكاميرات" } },
  { key: "doorbellEntity", group: "doorbell", type: "entity", domains: ["binary_sensor", "event"], label: { en: "Doorbell sensor", nl: "Deurbel-sensor", ar: "حسّاس الجرس" } },
  { key: "doorbellCamera", group: "doorbell", type: "entity", domains: ["camera"], label: { en: "Doorbell camera", nl: "Deurbelcamera", ar: "كاميرا الجرس" } },
  { key: "zoneWatchPersonIds", group: "location", type: "entities", domains: ["person"], label: { en: "Zone notifications for", nl: "Zonemeldingen voor", ar: "تنبيهات المناطق لـ" } },
  { key: "hazardRadiusKm", group: "location", type: "number", label: { en: "Hazard radius (km)", nl: "Gevarenradius (km)", ar: "نطاق المخاطر (كم)" } },
  { key: "disasterRadiusKm", group: "location", type: "number", label: { en: "Disaster radius (km)", nl: "Rampstraal (km)", ar: "نطاق الكوارث (كم)" } },
  { key: "selectedDashboardPath", group: "dashboard", type: "text", label: { en: "Dashboard path", nl: "Dashboardpad", ar: "مسار اللوحة" } },
  { key: "profiles", group: "family", type: "profiles", label: { en: "Family profiles", nl: "Gezinsprofielen", ar: "بروفايلات العيلة" } },
  { key: "selectedCalendarIds", group: "family", type: "entities", domains: ["calendar"], label: { en: "Calendars", nl: "Agenda's", ar: "التقاويم" } },
  { key: "selectedTodoIds", group: "family", type: "entities", domains: ["todo"], label: { en: "To-do lists", nl: "Takenlijsten", ar: "قوائم المهام" } },
  { key: "backgroundMonitoringEnabled", group: "background", type: "toggle", label: { en: "Background monitoring", nl: "Achtergrondbewaking", ar: "المراقبة في الخلفية" } },
];

const ALARM_MODES = ["home", "away", "night", "vacation", "custom"];

// device_class للحسّاسات المرشّحة للإنذار — عشان مانرميش كل binary_sensor.
const ALARM_SENSOR_CLASSES = new Set([
  "door", "window", "garage_door", "opening", "motion", "moving", "occupancy",
  "presence", "smoke", "gas", "carbon_monoxide", "moisture", "safety", "tamper",
  "vibration", "sound", "lock", "problem",
]);

// ===== الترجمة (حسب لغة الواجهة) =====
const T = {
  en: {
    dir: "ltr",
    setup: "Setup check", addons: "Optional add-ons", addonsSub: "Suggested for your country. Global sources show for everyone.",
    settings: "Family settings", settingsSub: "The admin settings published to the family. Members don't see these.",
    save: "Save & publish", saved: "Published to the family", saveErr: "Could not save",
    none: "— none —", ready: "Ready", missing: "Missing", add: "Add", installed: "Installed",
    birthday: "Birthday", role: "Role", roleNone: "— none —", roleManager: "Manager", roleAdult: "Adult", roleChild: "Child", color: "Color",
    profilesNoPersons: "No people found. Add person entities in Home Assistant first.",
    profilesHint: "Birthdays here are added to the Annual calendar automatically and repeat every year.",
    scopeGlobal: "Global", scopeCountry: "Your country", loading: "Loading…",
    showAll: "Show all sensors", alarmSensorsHint: "Only used if Alarmo doesn't manage its own sensors. Showing door / window / motion type sensors.",
    geoTitle: "Hazard sources (geo_location)", geoHint: "These feed road, weather and disaster alerts on the map.", geoNone: "No geo_location source yet — add one from the setup check above.",
    groups: { general: "General", alarm: "Alarm", cameras: "Cameras", doorbell: "Doorbell", location: "Map & location", dashboard: "Dashboard", family: "Calendar & to-do", background: "Background" },
    items: {
      home_zone: ["Home zone", "A 'Home' zone is required for presence and hazard distance."],
      alarm: ["Alarm panel", "Install Alarmo (or any alarm_control_panel) for the Alarm tab."],
      camera: ["Cameras", "Add at least one camera for the Cameras tab and the doorbell."],
      person: ["People", "Person entities are needed to show family on the map."],
      mobile_app: ["Mobile App integration", "The Companion / mobile_app integration tracks location."],
      hazards: ["Hazard sources", "Add a geo_location source so road, weather and disaster alerts appear."],
    },
    addonsCat: {
      gdacs: ["GDACS — natural disasters", "Floods, earthquakes, storms, wildfires worldwide."],
      usgs_quakes: ["USGS — earthquakes", "Worldwide seismic events feed."],
      p2000: ["P2000 — NL emergency", "Dutch ambulance, fire and police dispatches."],
      dwd: ["DWD — weather warnings", "German weather service alerts."],
      nws: ["NWS — US weather alerts", "US National Weather Service warnings."],
      nsw_fire: ["NSW Rural Fire", "Australian bushfire incident feed."],
      geonet_quakes: ["GeoNet — earthquakes", "New Zealand seismic feed."],
      geonet_volcano: ["GeoNet — volcano", "New Zealand volcanic alert levels."],
    },
  },
  nl: {
    dir: "ltr",
    setup: "Installatiecontrole", addons: "Optionele uitbreidingen", addonsSub: "Aanbevolen voor jouw land. Wereldwijde bronnen gelden voor iedereen.",
    settings: "Gezinsinstellingen", settingsSub: "De beheerdersinstellingen die naar het gezin worden gepubliceerd. Leden zien deze niet.",
    save: "Opslaan & publiceren", saved: "Gepubliceerd naar het gezin", saveErr: "Opslaan mislukt",
    none: "— geen —", ready: "Gereed", missing: "Ontbreekt", add: "Toevoegen", installed: "Geïnstalleerd",
    birthday: "Verjaardag", role: "Rol", roleNone: "— geen —", roleManager: "Beheerder", roleAdult: "Volwassene", roleChild: "Kind", color: "Kleur",
    profilesNoPersons: "Geen personen gevonden. Voeg eerst person-entiteiten toe in Home Assistant.",
    profilesHint: "Verjaardagen hier komen automatisch in de Jaarlijkse agenda en herhalen elk jaar.",
    scopeGlobal: "Wereldwijd", scopeCountry: "Jouw land", loading: "Laden…",
    showAll: "Alle sensoren tonen", alarmSensorsHint: "Alleen gebruikt als Alarmo zijn eigen sensoren niet beheert. Toont deur- / raam- / bewegingssensoren.",
    geoTitle: "Gevarenbronnen (geo_location)", geoHint: "Deze voeden verkeers-, weer- en rampmeldingen op de kaart.", geoNone: "Nog geen geo_location-bron — voeg er een toe via de controle hierboven.",
    groups: { general: "Algemeen", alarm: "Alarm", cameras: "Camera's", doorbell: "Deurbel", location: "Kaart & locatie", dashboard: "Dashboard", family: "Agenda & taken", background: "Achtergrond" },
    items: {
      home_zone: ["Thuiszone", "Een 'Home'-zone is nodig voor aanwezigheid en gevarenafstand."],
      alarm: ["Alarmpaneel", "Installeer Alarmo (of een alarm_control_panel) voor het Alarm-tabblad."],
      camera: ["Camera's", "Voeg minstens één camera toe voor Camera's en de deurbel."],
      person: ["Personen", "Person-entiteiten zijn nodig om het gezin op de kaart te tonen."],
      mobile_app: ["Mobiele app-integratie", "De Companion / mobile_app-integratie houdt de locatie bij."],
      hazards: ["Gevarenbronnen", "Voeg een geo_location-bron toe voor verkeer, weer en rampen."],
    },
    addonsCat: {
      gdacs: ["GDACS — natuurrampen", "Overstromingen, aardbevingen, stormen, natuurbranden wereldwijd."],
      usgs_quakes: ["USGS — aardbevingen", "Wereldwijde seismische feed."],
      p2000: ["P2000 — NL hulpdiensten", "Nederlandse ambulance-, brandweer- en politiemeldingen."],
      dwd: ["DWD — weerwaarschuwingen", "Waarschuwingen van de Duitse weerdienst."],
      nws: ["NWS — VS weeralarmen", "Waarschuwingen van de Amerikaanse weerdienst."],
      nsw_fire: ["NSW Rural Fire", "Australische bosbrand-feed."],
      geonet_quakes: ["GeoNet — aardbevingen", "Nieuw-Zeelandse seismische feed."],
      geonet_volcano: ["GeoNet — vulkaan", "Nieuw-Zeelandse vulkanische alertniveaus."],
    },
  },
  ar: {
    dir: "rtl",
    setup: "فحص الإعداد", addons: "إضافات اختيارية", addonsSub: "موصى بيها لدولتك. المصادر العالمية بتظهر للكل.",
    settings: "إعدادات العيلة", settingsSub: "إعدادات الأدمن اللي بتتنشر للعيلة. الأفراد مابيشوفوهاش.",
    save: "حفظ ونشر", saved: "اتنشر للعيلة", saveErr: "ماقدرش يحفظ",
    none: "— مفيش —", ready: "جاهز", missing: "ناقص", add: "أضف", installed: "متركّب",
    birthday: "تاريخ الميلاد", role: "الدور", roleNone: "— بدون —", roleManager: "مدير", roleAdult: "بالغ", roleChild: "طفل", color: "اللون",
    profilesNoPersons: "مفيش أفراد. ضيف كيانات person في Home Assistant الأول.",
    profilesHint: "أعياد الميلاد هنا بتتضاف تلقائيًا لتقويم المناسبات السنوية وبتتكرر كل سنة.",
    scopeGlobal: "عالمي", scopeCountry: "دولتك", loading: "جار التحميل…",
    showAll: "عرض كل الحسّاسات", alarmSensorsHint: "بيُستعمل بس لو Alarmo مش بيدير حسّاساته بنفسه. بيعرض حسّاسات الأبواب / الشبابيك / الحركة.",
    geoTitle: "مصادر المخاطر (geo_location)", geoHint: "دي اللي بتغذّي بلاغات الطرق والطقس والكوارث على الخريطة.", geoNone: "مفيش مصدر geo_location لسه — أضف واحد من فحص الإعداد فوق.",
    groups: { general: "عام", alarm: "الإنذار", cameras: "الكاميرات", doorbell: "الجرس", location: "الخريطة والموقع", dashboard: "اللوحة", family: "التقويم والمهام", background: "الخلفية" },
    items: {
      home_zone: ["منطقة البيت", "منطقة «Home» لازمة للحضور وحساب مسافة المخاطر."],
      alarm: ["لوحة الإنذار", "ثبّت Alarmo (أو أي alarm_control_panel) عشان تبويب الإنذار."],
      camera: ["الكاميرات", "أضف كاميرا واحدة على الأقل لتبويب الكاميرات وجرس الباب."],
      person: ["الأشخاص", "كيانات person لازمة عشان تظهر العيلة على الخريطة."],
      mobile_app: ["تكامل mobile_app", "تكامل الموبايل (Companion) بيتتبّع الموقع."],
      hazards: ["مصادر المخاطر", "أضف مصدر geo_location عشان تظهر بلاغات الطرق والطقس والكوارث."],
    },
    addonsCat: {
      gdacs: ["GDACS — الكوارث الطبيعية", "فيضانات وزلازل وعواصف وحرائق حول العالم."],
      usgs_quakes: ["USGS — الزلازل", "تغذية زلازل عالمية."],
      p2000: ["P2000 — طوارئ هولندا", "بلاغات الإسعاف والإطفاء والشرطة الهولندية."],
      dwd: ["DWD — تحذيرات الطقس", "تنبيهات هيئة الأرصاد الألمانية."],
      nws: ["NWS — تنبيهات أمريكا", "تحذيرات هيئة الطقس الأمريكية."],
      nsw_fire: ["NSW Rural Fire", "تغذية حرائق الغابات الأسترالية."],
      geonet_quakes: ["GeoNet — الزلازل", "تغذية زلازل نيوزيلندا."],
      geonet_volcano: ["GeoNet — البراكين", "مستويات التنبيه البركاني بنيوزيلندا."],
    },
  },
};

class SecureFamilyPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._loaded = false;
    this._edited = {};
    this._showAllSensors = false;
  }

  set hass(hass) {
    this._hass = hass;
    const lang = this._pickLang(hass);
    if (!this._loaded) {
      this._loaded = true;
      this._lang = lang;
      this._render();
      this._load();
    } else if (lang !== this._lang) {
      // اللغة اتغيّرت من إعدادات المستخدم — نعيد الرسم باللغة الجديدة
      // (مع الحفاظ على أي تعديل غير محفوظ).
      this._collect();
      this._lang = lang;
      this._render();
    }
  }

  _pickLang(hass) {
    const raw = (hass && ((hass.locale && hass.locale.language) || hass.language)) || "en";
    const l = String(raw).slice(0, 2);
    return T[l] ? l : "en";
  }

  async _load() {
    try {
      const [status, cfg] = await Promise.all([
        this._hass.callWS({ type: "secure_family/requirements" }),
        this._hass.callWS({ type: "secure_family/get_config" }),
      ]);
      this._status = status;
      this._config = (cfg && cfg.config) || {};
      this._version = (cfg && cfg.version) || 0;
      this._edited = {};
      this._render();
    } catch (err) {
      this._error = (err && err.message) || String(err);
      this._render();
    }
  }

  _entities(domains) {
    const out = [];
    const states = this._hass.states || {};
    for (const id of Object.keys(states)) {
      if (domains.includes(id.split(".")[0])) {
        out.push({ id, name: (states[id].attributes && states[id].attributes.friendly_name) || id });
      }
    }
    return out.sort((a, b) => a.name.localeCompare(b.name));
  }

  _isAlarmCandidate(id) {
    const st = (this._hass.states || {})[id];
    const dc = st && st.attributes && st.attributes.device_class;
    return !!dc && ALARM_SENSOR_CLASSES.has(dc);
  }

  // مصادر geo_location الحيّة، مجمّعة حسب مصدرها (attribute source).
  _geoSources() {
    const states = this._hass.states || {};
    const counts = {};
    for (const id of Object.keys(states)) {
      if (id.split(".")[0] !== "geo_location") continue;
      const src = (states[id].attributes && states[id].attributes.source) || id.split(".")[1].split("_")[0];
      counts[src] = (counts[src] || 0) + 1;
    }
    return Object.keys(counts).sort().map((s) => ({ source: s, count: counts[s] }));
  }

  _value(key) {
    return key in this._edited ? this._edited[key] : this._config[key];
  }

  _setEdited(key, value) {
    this._edited[key] = value;
  }

  _addIntegration(domain) {
    window.location.assign(`/config/integrations/dashboard/add?domain=${encodeURIComponent(domain)}`);
  }

  async _save() {
    const t = T[this._lang];
    const config = { ...this._config, ...this._edited };
    for (const k of Object.keys(config)) {
      if (config[k] === "" || config[k] === undefined) delete config[k];
    }
    const btn = this.shadowRoot.getElementById("save");
    if (btn) { btn.disabled = true; btn.textContent = "…"; }
    try {
      await this._hass.callService("secure_family", "set_config", { config });
      this._toast(t.saved);
      await this._load();
    } catch (err) {
      this._toast(t.saveErr + ": " + ((err && err.message) || err), true);
      if (btn) { btn.disabled = false; btn.textContent = t.save; }
    }
  }

  _toast(text, isError) {
    const el = this.shadowRoot.getElementById("toast");
    if (!el) return;
    el.textContent = text;
    el.style.background = isError ? "var(--error-color, #e53935)" : "var(--success-color, #2e9e5b)";
    el.style.opacity = "1";
    setTimeout(() => { el.style.opacity = "0"; }, 3000);
  }

  // ===== عناصر التحكّم =====
  _control(f) {
    const t = T[this._lang];
    const v = this._value(f.key);
    const esc = (s) => String(s).replace(/"/g, "&quot;");
    if (f.type === "toggle") {
      return `<input type="checkbox" data-key="${f.key}" data-type="toggle" ${v ? "checked" : ""}/>`;
    }
    if (f.type === "number") {
      return `<input type="number" data-key="${f.key}" data-type="number" value="${v != null ? esc(v) : ""}"/>`;
    }
    if (f.type === "text") {
      return `<input type="text" data-key="${f.key}" data-type="text" value="${v != null ? esc(v) : ""}"/>`;
    }
    if (f.type === "select") {
      const opts = ['<option value="">' + t.none + "</option>"]
        .concat(f.options.map((o) => `<option value="${o}" ${String(v) === o ? "selected" : ""}>${o}</option>`))
        .join("");
      return `<select data-key="${f.key}" data-type="select" data-coerce="${f.coerce || ""}">${opts}</select>`;
    }
    if (f.type === "entity") {
      const opts = ['<option value="">' + t.none + "</option>"]
        .concat(this._entities(f.domains).map((e) => `<option value="${e.id}" ${v === e.id ? "selected" : ""}>${esc(e.name)}</option>`))
        .join("");
      return `<select data-key="${f.key}" data-type="entity">${opts}</select>`;
    }
    if (f.type === "entities" && f.alarmSensors) {
      const sel = Array.isArray(v) ? v : [];
      const all = this._entities(["binary_sensor"]);
      const list = this._showAllSensors ? all : all.filter((e) => sel.includes(e.id) || this._isAlarmCandidate(e.id));
      const rows = list
        .map((e) => `<label class="chk"><input type="checkbox" value="${e.id}" ${sel.includes(e.id) ? "checked" : ""}/> ${esc(e.name)}</label>`)
        .join("");
      return `<label class="chk small"><input type="checkbox" id="showall" ${this._showAllSensors ? "checked" : ""}/> ${t.showAll}</label>
        <div class="checks" data-key="${f.key}" data-type="entities">${rows}</div>
        <div class="fhint">${t.alarmSensorsHint}</div>`;
    }
    if (f.type === "entities") {
      const sel = Array.isArray(v) ? v : [];
      return `<div class="checks" data-key="${f.key}" data-type="entities">${this._entities(f.domains)
        .map((e) => `<label class="chk"><input type="checkbox" value="${e.id}" ${sel.includes(e.id) ? "checked" : ""}/> ${esc(e.name)}</label>`)
        .join("")}</div>`;
    }
    if (f.type === "modes") {
      const obj = v && typeof v === "object" ? v : {};
      const keys = Object.keys(obj).length ? Object.keys(obj) : ALARM_MODES;
      return `<div class="checks" data-key="${f.key}" data-type="modes">${keys
        .map((m) => `<label class="chk"><input type="checkbox" value="${m}" ${obj[m] !== false ? "checked" : ""}/> ${m}</label>`)
        .join("")}</div>`;
    }
    if (f.type === "profiles") {
      // بروفايل لكل فرد (person): تاريخ ميلاد + صفة + لون اختياري. المكوّن
      // بيولّد من تاريخ الميلاد حدث سنوي تلقائيًا في تقويم المناسبات.
      const pv = v && typeof v === "object" ? v : {};
      const persons = this._entities(["person"]);
      if (!persons.length) return `<div class="fhint">${t.profilesNoPersons}</div>`;
      const rows = persons
        .map((p) => {
          const pr = pv[p.id] || {};
          return `<div class="profile" data-pid="${p.id}" style="border:1px solid var(--divider-color,#e0e0e0);border-radius:10px;padding:10px;margin-bottom:8px;">
            <div style="font-weight:600;margin-bottom:8px;">${esc(p.name)}</div>
            <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;">
              <label style="display:flex;flex-direction:column;gap:3px;font-size:12px;opacity:.8;">${t.birthday}
                <input type="date" data-pf="birthday" value="${pr.birthday ? esc(pr.birthday) : ""}"/></label>
              <label style="display:flex;flex-direction:column;gap:3px;font-size:12px;opacity:.8;">${t.role}
                <select data-pf="role">
                  <option value="" ${!pr.role ? "selected" : ""}>${t.roleNone}</option>
                  <option value="manager" ${pr.role === "manager" ? "selected" : ""}>${t.roleManager}</option>
                  <option value="adult" ${pr.role === "adult" ? "selected" : ""}>${t.roleAdult}</option>
                  <option value="child" ${pr.role === "child" ? "selected" : ""}>${t.roleChild}</option>
                </select></label>
              <label style="display:flex;align-items:center;gap:6px;font-size:12px;opacity:.8;">
                <input type="checkbox" data-pf="colorOn" ${pr.color ? "checked" : ""}/> ${t.color}
                <input type="color" data-pf="color" value="${pr.color ? esc(pr.color) : "#378ADD"}"/></label>
            </div>
          </div>`;
        })
        .join("");
      return `<div data-key="profiles" data-type="profiles" style="width:100%;">${rows}<div class="fhint">${t.profilesHint}</div></div>`;
    }
    return "";
  }

  _collect() {
    if (!this.shadowRoot) return;
    this.shadowRoot.querySelectorAll("[data-key]").forEach((el) => {
      const key = el.getAttribute("data-key");
      const type = el.getAttribute("data-type");
      if (type === "toggle") this._setEdited(key, el.checked);
      else if (type === "number") this._setEdited(key, el.value === "" ? undefined : Number(el.value));
      else if (type === "select") this._setEdited(key, el.getAttribute("data-coerce") === "number" ? (el.value === "" ? undefined : Number(el.value)) : el.value);
      else if (type === "text") this._setEdited(key, el.value);
      else if (type === "entity") this._setEdited(key, el.value);
      else if (type === "entities") {
        const ids = [...el.querySelectorAll("input:checked")].map((i) => i.value);
        this._setEdited(key, ids);
      } else if (type === "modes") {
        const obj = {};
        el.querySelectorAll("input").forEach((i) => { obj[i.value] = i.checked; });
        this._setEdited(key, obj);
      } else if (type === "profiles") {
        const obj = {};
        el.querySelectorAll(".profile").forEach((row) => {
          const pid = row.getAttribute("data-pid");
          const entry = {};
          const b = row.querySelector('[data-pf="birthday"]');
          if (b && b.value) entry.birthday = b.value;
          const r = row.querySelector('[data-pf="role"]');
          if (r && r.value.trim()) entry.role = r.value.trim();
          const con = row.querySelector('[data-pf="colorOn"]');
          const col = row.querySelector('[data-pf="color"]');
          if (con && con.checked && col && col.value) entry.color = col.value;
          if (Object.keys(entry).length) obj[pid] = entry;
        });
        this._setEdited(key, obj);
      }
    });
  }

  // ===== بناء الأقسام =====
  _checklist(t, d) {
    return d.items
      .map((it) => {
        const color = it.ok ? "var(--success-color, #2e9e5b)" : "var(--error-color, #e53935)";
        const badge = it.ok ? t.ready : t.missing;
        const txt = t.items[it.key] || [it.key, ""];
        const action = !it.ok && it.add ? `<button class="add" data-domain="${it.add}">+ ${t.add}</button>` : "";
        return `<div class="row"><span class="dot" style="background:${color}"></span><div class="rowtext"><div class="label">${txt[0]}</div><div class="hint">${txt[1]}</div></div><div class="rowend"><span class="badge" style="color:${color}">${badge}</span>${action}</div></div>`;
      })
      .join("");
  }

  _addonsList(t, d) {
    const addons = (d && d.addons) || [];
    if (!addons.length) return "";
    return addons
      .map((a) => {
        const cat = t.addonsCat[a.key] || [a.key, ""];
        const scope = a.scope === "global" ? t.scopeGlobal : t.scopeCountry;
        const right = a.installed
          ? `<span class="badge" style="color:var(--success-color,#2e9e5b)">${t.installed}</span>`
          : a.domain
            ? `<button class="add" data-domain="${a.domain}">+ ${t.add}</button>`
            : a.add_url
              ? `<button class="add" data-url="${a.add_url}">+ ${t.add}</button>`
              : "";
        return `<div class="row"><ha-icon icon="mdi:puzzle-outline" class="rico"></ha-icon><div class="rowtext"><div class="label">${cat[0]} <span class="scope">${scope}</span></div><div class="hint">${cat[1]}</div></div><div class="rowend">${right}</div></div>`;
      })
      .join("");
  }

  _geoBlock(t) {
    const sources = this._geoSources();
    if (!sources.length) return `<div class="fhint geo">${t.geoNone}</div>`;
    const chips = sources.map((s) => `<span class="chip">${s.source} · ${s.count}</span>`).join("");
    return `<div class="geo"><div class="geo-title">${t.geoTitle}</div><div class="chips">${chips}</div><div class="fhint">${t.geoHint}</div></div>`;
  }

  _group(t, g) {
    const fields = FIELDS.filter((f) => f.group === g.key);
    const rows = fields
      .map((f) => `<div class="frow"><div class="flabel">${(f.label && f.label[this._lang]) || f.label.en}</div><div class="fctrl">${this._control(f)}</div></div>`)
      .join("");
    const extra = g.key === "location" ? this._geoBlock(t) : "";
    return `<details class="group" ${g.open ? "open" : ""}>
      <summary><ha-icon icon="${g.icon}"></ha-icon><span>${t.groups[g.key]}</span></summary>
      <div class="gbody">${rows}${extra}</div>
    </details>`;
  }

  _render() {
    const t = T[this._lang] || T.en;
    const d = this._status;

    const checklist = d ? this._checklist(t, d) : "";
    const addons = d ? this._addonsList(t, d) : "";
    const groups = this._config ? GROUPS.map((g) => this._group(t, g)).join("") : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;padding:16px;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif);}
        .wrap{max-width:780px;margin:0 auto;}
        .card{margin:0 0 16px;background:var(--card-background-color,#fff);border-radius:16px;box-shadow:var(--ha-card-box-shadow,0 2px 6px rgba(0,0,0,.1));overflow:hidden;}
        .head{padding:16px 18px 8px;}
        .title{font-size:18px;font-weight:700;margin:0;display:flex;align-items:center;gap:9px;}
        .title ha-icon{color:var(--primary-color,#2f6bff);}
        .sub{color:var(--secondary-text-color);font-size:12.5px;margin:4px 0 0;}
        .row{display:flex;align-items:flex-start;gap:12px;padding:13px 18px;border-top:1px solid var(--divider-color,#e9e9e9);}
        .rico{color:var(--secondary-text-color);flex:none;margin-top:2px;}
        .dot{width:11px;height:11px;border-radius:6px;margin-top:5px;flex:none;}
        .rowtext{flex:1;min-width:0;}
        .label{font-weight:600;font-size:14.5px;}
        .scope{font-size:11px;font-weight:600;color:var(--secondary-text-color);background:var(--secondary-background-color,#f0f0f0);border-radius:6px;padding:1px 7px;margin-inline-start:6px;}
        .hint{color:var(--secondary-text-color);font-size:12px;margin-top:2px;}
        .rowend{display:flex;align-items:center;gap:10px;flex:none;}
        .badge{font-size:12px;font-weight:700;}
        button.add{background:var(--primary-color,#2f6bff);color:var(--text-primary-color,#fff);border:none;border-radius:9px;padding:6px 11px;font-weight:600;cursor:pointer;font-size:13px;}
        details.group{border-top:1px solid var(--divider-color,#e9e9e9);}
        details.group>summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:10px;padding:14px 18px;font-weight:600;font-size:15px;user-select:none;}
        details.group>summary::-webkit-details-marker{display:none;}
        details.group>summary ha-icon{color:var(--primary-color,#2f6bff);}
        details.group>summary::after{content:"";margin-inline-start:auto;width:8px;height:8px;border-right:2px solid var(--secondary-text-color);border-bottom:2px solid var(--secondary-text-color);transform:rotate(45deg);transition:transform .2s;}
        details.group[open]>summary::after{transform:rotate(225deg);}
        .gbody{padding-bottom:6px;}
        .frow{display:flex;align-items:flex-start;gap:14px;padding:10px 18px;}
        .flabel{flex:1;font-weight:500;font-size:14px;padding-top:6px;color:var(--secondary-text-color);}
        .fctrl{flex:1.2;min-width:0;}
        .fctrl select,.fctrl input[type=number],.fctrl input[type=text]{width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--divider-color,#ccc);border-radius:8px;background:var(--secondary-background-color,#f6f6f6);color:var(--primary-text-color);}
        .checks{display:flex;flex-direction:column;gap:4px;max-height:200px;overflow:auto;border:1px solid var(--divider-color,#ccc);border-radius:8px;padding:8px;}
        .chk{font-size:13px;display:flex;gap:7px;align-items:center;}
        .chk.small{margin-bottom:6px;font-weight:600;color:var(--secondary-text-color);}
        .fhint{color:var(--secondary-text-color);font-size:11.5px;margin-top:5px;line-height:1.5;}
        .geo{padding:10px 18px 4px;}
        .geo-title{font-weight:600;font-size:13.5px;margin-bottom:7px;}
        .chips{display:flex;flex-wrap:wrap;gap:6px;}
        .chip{font-size:12px;font-weight:600;background:var(--secondary-background-color,#f0f0f0);border-radius:7px;padding:3px 9px;}
        .foot{padding:16px 18px;border-top:1px solid var(--divider-color,#e9e9e9);display:flex;justify-content:flex-end;}
        button.save{background:var(--primary-color,#2f6bff);color:var(--text-primary-color,#fff);border:none;border-radius:12px;padding:11px 22px;font-weight:700;font-size:15px;cursor:pointer;}
        #toast{position:fixed;inset-inline-start:50%;bottom:24px;transform:translateX(-50%);color:#fff;padding:12px 18px;border-radius:12px;opacity:0;transition:opacity .25s;font-weight:600;}
        .err{padding:16px 18px;color:var(--error-color,#e53935);}
        .loading{padding:22px 18px;color:var(--secondary-text-color);}
      </style>
      <div class="wrap" dir="${t.dir}">
        <div class="card">
          <div class="head"><p class="title"><ha-icon icon="mdi:shield-home"></ha-icon>Secure Family — ${t.setup}</p></div>
          ${this._error ? `<div class="err">${this._error}</div>` : d ? checklist : `<div class="loading">${t.loading}</div>`}
        </div>
        ${d && addons ? `<div class="card"><div class="head"><p class="title"><ha-icon icon="mdi:puzzle"></ha-icon>${t.addons}</p><p class="sub">${t.addonsSub}</p></div>${addons}</div>` : ""}
        <div class="card">
          <div class="head"><p class="title"><ha-icon icon="mdi:cog"></ha-icon>${t.settings}</p><p class="sub">${t.settingsSub}</p></div>
          ${this._config ? groups + `<div class="foot"><button class="save" id="save">${t.save}</button></div>` : `<div class="loading">${t.loading}</div>`}
        </div>
      </div>
      <div id="toast"></div>`;

    this.shadowRoot.querySelectorAll("button.add").forEach((btn) => {
      btn.addEventListener("click", () => {
        const url = btn.getAttribute("data-url");
        if (url) window.open(url, "_blank", "noopener");
        else this._addIntegration(btn.getAttribute("data-domain"));
      });
    });
    const showall = this.shadowRoot.getElementById("showall");
    if (showall) showall.addEventListener("change", () => { this._collect(); this._showAllSensors = showall.checked; this._render(); });
    const save = this.shadowRoot.getElementById("save");
    if (save) save.addEventListener("click", () => { this._collect(); this._save(); });
  }
}

customElements.define("secure-family-panel", SecureFamilyPanel);
