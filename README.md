# A Better Routeplanner — Home Assistant custom integration

A custom-component build of the [A Better Routeplanner (ABRP)](https://abetterrouteplanner.com)
integration for Home Assistant, for **testing outside of Home Assistant core**.

It pulls your ABRP garage and streams live vehicle telemetry (state of charge,
range, power, odometer, location, …) into Home Assistant as devices and entities.

Authentication uses ABRP's public OIDC client with PKCE — there is **no API key or
Application Credentials setup required**. You just log in with your ABRP account.

## Requirements

- Home Assistant 2024.1.0 or newer.
- An A Better Routeplanner account with at least one vehicle in your garage.

## Installation

### Option A — HACS (custom repository)

1. In Home Assistant, open **HACS → Integrations**.
2. Click the **⋮** menu (top right) → **Custom repositories**.
3. Add this repository's URL, set category to **Integration**, and click **Add**.
4. Find **A Better Routeplanner** in the list, install it, then **restart Home Assistant**.

> This integration is intentionally distributed as a custom repository only — it is
> not published to the HACS default store.

### Option B — Manual

1. Copy the `custom_components/abetterrouteplanner/` folder from this repo into your
   Home Assistant configuration directory, so you end up with:
   ```
   <config>/custom_components/abetterrouteplanner/
   ```
2. **Restart Home Assistant.**

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **A Better Routeplanner**.
3. Complete the login flow in the ABRP browser window.
4. Pick which vehicles from your garage you want to track.

Each selected vehicle is added as a device. You can change the tracked vehicles
later via the integration's **Reconfigure** option.

## Notes

- This is a packaging of the integration as a custom component for testing; it is a
  separate effort from any upstream Home Assistant core submission.
- Logs are written under the `custom_components.abetterrouteplanner` logger.
