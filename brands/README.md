# Secure Family — brand images

These are the logo/icon files for the Home Assistant UI.

```
brands/custom_integrations/secure_family/
  icon.png       256×256   (square app icon)
  icon@2x.png    512×512
  logo.png       256×256
  logo@2x.png    512×512
```

Home Assistant does **not** read logos from inside a custom integration. To make
the icon appear on **Settings → Devices & Services**, submit these files to the
official brands repository:

1. Fork <https://github.com/home-assistant/brands>.
2. Copy this folder to `custom_integrations/secure_family/` in that fork
   (keep the file names exactly).
3. Open a pull request. Once merged, the logo is served from
   `https://brands.home-assistant.io/` and shows up automatically.

Until the PR is merged, Home Assistant shows a generic icon — this is expected
and does not affect the integration's behaviour.

Source: generated from the Secure Family app logo
(`assets/branding/secure-family-logo.png`), padded to a square and resized.
