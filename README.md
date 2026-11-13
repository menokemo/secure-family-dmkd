<img src="brands/custom_integrations/secure_family/logo.png" alt="Secure Family" width="110" />

# Secure Family — Home Assistant integration

Central configuration store for the **Secure Family** app. The one technical
family member configures everything **once** in the app and publishes it; every
other family member just installs the app and signs in — no per-device setup.

Everything runs **locally** on your network between the phones and your Home
Assistant server. No cloud, no internet required.

## How it works

- The admin configures the app, then taps **"Publish as family config."**
- The app calls the `secure_family.set_config` service (admins only).
- The config is stored persistently in Home Assistant's `.storage` (survives
  restarts) and exposed on the entity `sensor.secure_family_config`.
- Every family member's app reads that entity over the local connection it
  already uses, applies the settings on login, and caches them for offline use.
  Changes the admin publishes are pushed to everyone instantly.

## Installation

### Via HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/menokemo/secure-family-dmkd`, category **Integration**.
3. Install **Secure Family**, then restart Home Assistant.

### Manual

Copy `custom_components/secure_family` into your Home Assistant
`config/custom_components/` folder and restart.

### Set up

Settings → Devices & Services → **Add Integration** → **Secure Family**.

## Entities

| Entity | Purpose |
| --- | --- |
| `sensor.secure_family_config` | Carries the family configuration (in its `config` attribute) and the current version number. |
| `sensor.secure_family_version` | Current configuration version (diagnostic). |
| `sensor.secure_family_last_published` | When the config was last published (diagnostic). |
| `binary_sensor.secure_family_configured` | On once a configuration has been published. |

## Services

| Service | Description |
| --- | --- |
| `secure_family.set_config` | Publish the full family configuration (admins only). |
| `secure_family.rollback` | Restore a previous version (admins only). |
| `secure_family.clear_config` | Clear the configuration (admins only). |
| `secure_family.cleanup_stale_trackers` | Remove **duplicate** (same device name — keeps the newest) and **stale** Secure Family `mobile_app` registrations, and purge their long-term statistics (so no "entity has no state" warnings pile up). Only ever touches **our** app (`app_id: secure_family`) — never the official Home Assistant Companion app. Fields: `max_age_days` (default 7), `dry_run` (default false). **Also runs automatically** every few hours and ~2 min after start, so re-registration/reinstall leftovers clean themselves. |
| `secure_family.request_live_location` | Ask a member's device (`entity_id`) to send its location fast for a short while — powers the live view. Available to any family member. |

## Entities

`sensor.secure_family_devices` lists the phones running **our** app (filtered by
`app_id: secure_family`, so the official Home Assistant Companion app is never
included). Its state is the device count; the `devices` attribute holds each
phone's name, battery, location state, last update, and all of its sensors. The
app registers every phone with a configurable friendly name you set in
**Settings → App info → Device name**.

## Logo

The integration's logo for the Home Assistant UI lives in
`brands/custom_integrations/secure_family/`. To make Home Assistant show it on
the Devices & Services page, submit those files to the
[home-assistant/brands](https://github.com/home-assistant/brands) repository
under `custom_integrations/secure_family/` (`icon.png` 256×256, `icon@2x.png`
512×512, and the matching `logo.png` / `logo@2x.png`). See
`brands/README.md`.

Writes are restricted to Home Assistant administrators and validated before they
are stored. No secrets (tokens or passwords) are ever kept in the central config.

## License

MIT — see [LICENSE](LICENSE).
