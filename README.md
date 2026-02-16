# Smart Plant Watering (Home Assistant)

Detects watering events from a soil moisture sensor and creates entities per plant:

- **Text sensor**: `Ult. riego hace 2 días` / `Last watered 2 days ago`
- **Timestamp sensor** (device_class: timestamp)
- **Days since watering** (numeric, in days)

Each plant is configured as a separate entry (add the integration multiple times).

## Installation (HACS - Custom Repository)

1. Open **HACS** → **⋮** (top-right) → **Custom repositories**
2. Add this repository URL (GitHub) and select **Integration**
3. Install **Smart Plant Watering**
4. Restart Home Assistant
5. Go to **Settings → Devices & Services → Add Integration → Smart Plant Watering**

## Configuration

You will choose:

- Plant name
- Moisture sensor entity
- Detection mode:
  - **Delta**: triggers when moisture jumps by `min_delta`
  - **Threshold**: triggers when crossing from dry to wet
- Cooldown: prevents multiple triggers (e.g. 6 hours)
- Confirmation: requires humidity stays high for X minutes (optional)

### Recommended settings

**Delta mode**
- `min_delta`: 8–15 depending on your sensor
- Optional: `dry_threshold` and `wet_threshold` to reduce false positives

**Threshold mode**
- `dry_threshold`: e.g. 40
- `wet_threshold`: e.g. 50

## Notes

- The integration ignores transitions from `unknown`/`unavailable` to prevent common false positives.
- Each plant is a separate config entry; you can add as many plants as you want.

## Bubble Card example

Point your Bubble Card `entity:` to the text sensor created by this integration (one per plant).

---

Repository: https://github.com/xpitcl/smart-plant-watering
Issues: https://github.com/xpitcl/smart-plant-watering/issues
