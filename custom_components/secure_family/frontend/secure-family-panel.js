// صفحة Secure Family في Home Assistant: قسمين —
//  (1) فحص المتطلبات (checklist بالناقص + أزرار إضافة).
//  (2) محرّر إعدادات العيلة (نفس اللي الأدمن بيظبّطها من التطبيق) — عرض وتعديل.
// web component خام (من غير مكتبات) عشان يتحمّل مباشرة من غير أي بناء/تحزيم.
// القراية عبر أوامر websocket، والكتابة عبر خدمة secure_family.set_config (أدمن).

// تعريف الحقول القابلة للتعديل. النوع بيحدّد شكل عنصر التحكّم:
//  entity = قائمة كيان واحد · entities = اختيار متعدد · toggle · number · select
//  · text · modes = أوضاع الإنذار (كائن مود→تشغيل).
const FIELDS = [
  { key: "mapEngine", type: "select", options: ["native", "web"], label: { en: "Map engine", nl: "Kaartengine", ar: "محرّك الخريطة" } },
  { key: "alarmEntityId", type: "entity", domains: ["alarm_control_panel"], label: { en: "Alarm panel", nl: "Alarmpaneel", ar: "لوحة الإنذار" } },
  { key: "visibleAlarmModes", type: "modes", label: { en: "Visible alarm modes", nl: "Zichtbare alarmmodi", ar: "أوضاع الإنذار الظاهرة" } },
  { key: "selectedSensorIds", type: "entities", domains: ["binary_sensor"], label: { en: "Alarm sensors", nl: "Alarmsensoren", ar: "حسّاسات الإنذار" } },
  { key: "directStatusChange", type: "toggle", label: { en: "Direct status change", nl: "Directe statuswijziging", ar: "تغيير الحالة المباشر" } },
  { key: "showStatusBadge", type: "toggle", label: { en: "Show status badge", nl: "Statusbadge tonen", ar: "إظهار شارة الحالة" } },
  { key: "selectedCameraIds", type: "entities", domains: ["camera"], label: { en: "Cameras shown", nl: "Getoonde camera's", ar: "الكاميرات الظاهرة" } },
  { key: "snapshotRefreshSeconds", type: "number", label: { en: "Snapshot refresh (s)", nl: "Snapshotverversing (s)", ar: "تحديث اللقطة (ث)" } },
  { key: "cameraColumns", type: "select", options: ["1", "2"], coerce: "number", label: { en: "Camera columns", nl: "Cameramkolommen", ar: "أعمدة الكاميرات" } },
  { key: "doorbellEntity", type: "entity", domains: ["binary_sensor", "event"], label: { en: "Doorbell sensor", nl: "Deurbel-sensor", ar: "حسّاس الجرس" } },
  { key: "doorbellCamera", type: "entity", domains: ["camera"], label: { en: "Doorbell camera", nl: "Deurbelcamera", ar: "كاميرا الجرس" } },
  { key: "hazardRadiusKm", type: "number", label: { en: "Hazard radius (km)", nl: "Gevarenradius (km)", ar: "نطاق المخاطر (كم)" } },
  { key: "disasterRadiusKm", type: "number", label: { en: "Disaster radius (km)", nl: "Rampstraal (km)", ar: "نطاق الكوارث (كم)" } },
  { key: "zoneWatchPersonIds", type: "entities", domains: ["person"], label: { en: "Zone notifications for", nl: "Zonemeldingen voor", ar: "تنبيهات المناطق لـ" } },
  { key: "selectedDashboardPath", type: "text", label: { en: "Dashboard path", nl: "Dashboardpad", ar: "مسار اللوحة" } },
  { key: "selectedCalendarIds", type: "entities", domains: ["calendar"], label: { en: "Calendars", nl: "Agenda's", ar: "التقاويم" } },
  { key: "selectedTodoIds", type: "entities", domains: ["todo"], label: { en: "To-do lists", nl: "Takenlijsten", ar: "قوائم المهام" } },
  { key: "backgroundMonitoringEnabled", type: "toggle", label: { en: "Background monitoring", nl: "Achtergrondbewaking", ar: "المراقبة في الخلفية" } },
];

const ALARM_MODES = ["home", "away", "night", "vacation", "custom"];

const UI = {
  en: { setup: "Setup check", settings: "Family settings", settingsSub: "The admin settings published to the family. Members don't see these.", save: "Save & publish", saved: "Published to the family", saveErr: "Could not save", none: "— none —", ready: "Ready", missing: "Missing", add: "Add" },
  nl: { setup: "Installatiecontrole", settings: "Gezinsinstellingen", settingsSub: "De beheerdersinstellingen die naar het gezin worden gepubliceerd. Leden zien deze niet.", save: "Opslaan & publiceren", saved: "Gepubliceerd naar het gezin", saveErr: "Opslaan mislukt", none: "— geen —", ready: "Gereed", missing: "Ontbreekt", add: "Toevoegen" },
  ar: { setup: "فحص الإعداد", settings: "إعدادات العيلة", settingsSub: "إعدادات الأدمن اللي بتتنشر للعيلة. الأفراد مابيشوفوهاش.", save: "حفظ ونشر", saved: "اتنشر للعيلة", saveErr: "ماقدرش يحفظ", none: "— مفيش —", ready: "جاهز", missing: "ناقص", add: "أضف" },
};

class SecureFamilyPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._loaded = false;
    this._edited = {}; // تعديلات المستخدم قبل الحفظ
  }

  set hass(hass) {
    this._hass = hass; // بنحدّثه دايمًا عشان callService/callWS يفضلوا حاليين
    if (!this._loaded) {
      this._loaded = true;
      this._lang = (hass.language || "en").slice(0, 2);
      if (!UI[this._lang]) this._lang = "en";
      this._render();
      this._load();
    }
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

  // كل الكيانات في domain معيّن، مرتّبة بالاسم.
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

  // القيمة الحالية لحقل (التعديل غير المحفوظ له الأولوية).
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
    const t = UI[this._lang];
    const config = { ...this._config, ...this._edited };
    // نشيل المفاتيح الفاضية (كيان مختار اتلغى) عشان مانكتبش قيم فاضية.
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
      const opts = ['<option value="">' + UI[this._lang].none + "</option>"]
        .concat(f.options.map((o) => `<option value="${o}" ${String(v) === o ? "selected" : ""}>${o}</option>`))
        .join("");
      return `<select data-key="${f.key}" data-type="select" data-coerce="${f.coerce || ""}">${opts}</select>`;
    }
    if (f.type === "entity") {
      const opts = ['<option value="">' + UI[this._lang].none + "</option>"]
        .concat(this._entities(f.domains).map((e) => `<option value="${e.id}" ${v === e.id ? "selected" : ""}>${esc(e.name)}</option>`))
        .join("");
      return `<select data-key="${f.key}" data-type="entity">${opts}</select>`;
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
    return "";
  }

  _collect() {
    // بنقرا كل عناصر التحكّم ونحدّث this._edited.
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
      }
    });
  }

  _render() {
    const t = UI[this._lang] || UI.en;
    const d = this._status;

    const checklist = d
      ? d.items
          .map((it) => {
            const color = it.ok ? "var(--success-color, #2e9e5b)" : "var(--error-color, #e53935)";
            const badge = it.ok ? (d.labels.ok || t.ready) : (d.labels.missing || t.missing);
            const action = !it.ok && it.add ? `<button class="add" data-domain="${it.add}">+ ${t.add}</button>` : "";
            return `<div class="row"><span class="dot" style="background:${color}"></span><div class="rowtext"><div class="label">${it.label}</div><div class="hint">${it.hint}</div></div><div class="rowend"><span class="badge" style="color:${color}">${badge}</span>${action}</div></div>`;
          })
          .join("")
      : "";
    const recommend =
      d && d.recommended_sources && d.recommended_sources.length
        ? `<div class="note"><b>${d.labels.recommend}${d.country ? " (" + d.country + ")" : ""}:</b> ${d.recommended_sources.join(", ")} · ${d.labels.disaster_km}: ${d.disaster_km} km</div>`
        : "";

    const settings = this._config
      ? FIELDS.map((f) => `<div class="frow"><div class="flabel">${(f.label && f.label[this._lang]) || f.label.en}</div><div class="fctrl">${this._control(f)}</div></div>`).join("")
      : "";

    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;padding:16px;color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif);}
        .card{max-width:760px;margin:0 auto 18px;background:var(--card-background-color,#fff);border-radius:16px;box-shadow:var(--ha-card-box-shadow,0 2px 6px rgba(0,0,0,.12));overflow:hidden;}
        .head{padding:16px 18px 6px;}
        .title{font-size:19px;font-weight:800;margin:0;}
        .sub{color:var(--secondary-text-color);font-size:12.5px;margin-top:4px;}
        .row{display:flex;align-items:flex-start;gap:12px;padding:13px 18px;border-top:1px solid var(--divider-color,#e0e0e0);}
        .dot{width:12px;height:12px;border-radius:6px;margin-top:4px;flex:none;}
        .rowtext{flex:1;min-width:0;}.label{font-weight:700;font-size:15px;}.hint{color:var(--secondary-text-color);font-size:12px;margin-top:2px;}
        .rowend{display:flex;align-items:center;gap:10px;flex:none;}.badge{font-size:12px;font-weight:800;}
        button.add{background:var(--primary-color,#2f6bff);color:var(--text-primary-color,#fff);border:none;border-radius:10px;padding:6px 11px;font-weight:700;cursor:pointer;}
        .note{padding:13px 18px;color:var(--secondary-text-color);font-size:13px;border-top:1px solid var(--divider-color,#e0e0e0);}
        .frow{display:flex;align-items:flex-start;gap:14px;padding:11px 18px;border-top:1px solid var(--divider-color,#e0e0e0);}
        .flabel{flex:1;font-weight:600;font-size:14px;padding-top:6px;}
        .fctrl{flex:1;min-width:0;}
        .fctrl select,.fctrl input[type=number],.fctrl input[type=text]{width:100%;box-sizing:border-box;padding:8px;border:1px solid var(--divider-color,#ccc);border-radius:8px;background:var(--secondary-background-color,#f5f5f5);color:var(--primary-text-color);}
        .checks{display:flex;flex-direction:column;gap:4px;max-height:180px;overflow:auto;border:1px solid var(--divider-color,#ccc);border-radius:8px;padding:8px;}
        .chk{font-size:13px;display:flex;gap:7px;align-items:center;}
        .foot{padding:16px 18px;border-top:1px solid var(--divider-color,#e0e0e0);display:flex;justify-content:flex-end;}
        button.save{background:var(--primary-color,#2f6bff);color:var(--text-primary-color,#fff);border:none;border-radius:12px;padding:11px 20px;font-weight:800;font-size:15px;cursor:pointer;}
        #toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);color:#fff;padding:12px 18px;border-radius:12px;opacity:0;transition:opacity .25s;font-weight:700;}
        .err{padding:16px 18px;color:var(--error-color,#e53935);}
        .loading{padding:24px 18px;color:var(--secondary-text-color);}
      </style>
      <div class="card">
        <div class="head"><p class="title">Secure Family — ${t.setup}</p></div>
        ${this._error ? `<div class="err">${this._error}</div>` : d ? checklist + recommend : `<div class="loading">Loading…</div>`}
      </div>
      <div class="card">
        <div class="head"><p class="title">${t.settings}</p><p class="sub">${t.settingsSub}</p></div>
        ${this._config ? settings + `<div class="foot"><button class="save" id="save">${t.save}</button></div>` : `<div class="loading">Loading…</div>`}
      </div>
      <div id="toast"></div>`;

    this.shadowRoot.querySelectorAll("button.add").forEach((btn) => {
      btn.addEventListener("click", () => this._addIntegration(btn.getAttribute("data-domain")));
    });
    const save = this.shadowRoot.getElementById("save");
    if (save) save.addEventListener("click", () => { this._collect(); this._save(); });
  }
}

customElements.define("secure-family-panel", SecureFamilyPanel);
