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

Writes are restricted to Home Assistant administrators and validated before they
are stored. No secrets (tokens or passwords) are ever kept in the central config.

## License

MIT — see [LICENSE](LICENSE).
