<img src="brands/custom_integrations/secure_family/logo.png" alt="Secure Family" width="96" />

# Secure Family

Central configuration store for the **Secure Family** app. The technical family
member configures everything once in the app and publishes it; everyone else
just installs the app and signs in. Fully local — no cloud, no internet needed.

After installing, go to **Settings → Devices & Services → Add Integration →
Secure Family**. Then publish the configuration from the app.

A **Secure Family** page is added to the sidebar (admins only). It follows your
Home Assistant **interface language** (English / Dutch / Arabic, RTL included) and
has three parts:

- A **setup checklist** — what the app needs in Home Assistant (home zone, alarm,
  cameras, people, mobile app, and hazard sources), with buttons to add anything
  missing.
- **Optional add-ons** — recommended hazard integrations, split into *global*
  (GDACS, USGS) shown to everyone and *country-specific* ones (e.g. P2000 for the
  Netherlands, NWS for the US, GeoNet for New Zealand), each with an add button.
- A **family settings editor** — the same admin settings the app publishes,
  **grouped into collapsible sections** like the app's admin (Alarm, Cameras,
  Doorbell, Map & location, Dashboard, Calendar & to-do, Background). Alarm
  sensors are filtered to door/window/motion types (with a *show all* toggle)
  instead of listing every binary_sensor, and the live `geo_location` hazard
  sources are shown separately under Map & location. These never show to regular
  family members.

## Family calendars

The integration creates three local, family-owned calendars automatically, with
stable entity ids so the app's Family tab always finds them:

- `calendar.secure_family_birthdays`
- `calendar.secure_family_events`
- `calendar.secure_family_appointments`

They are fully local, support recurring events (yearly birthdays, etc.), and are
created **once** — a fixed unique id means Home Assistant restores the same
calendars after every restart instead of making duplicates, and their events are
stored in `.storage` so nothing is lost or recreated.
