from __future__ import annotations

from datetime import datetime, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .coordinator import PlantWateringCoordinator
from .device import PlantDevice


def _humanize_es(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days} día" + ("s" if days != 1 else "")
    if hours > 0:
        return f"{hours} hora" + ("s" if hours != 1 else "")
    return f"{minutes} minuto" + ("s" if minutes != 1 else "")


def _humanize_en(seconds: int) -> str:
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days > 0:
        return f"{days} day" + ("s" if days != 1 else "")
    if hours > 0:
        return f"{hours} hour" + ("s" if hours != 1 else "")
    return f"{minutes} minute" + ("s" if minutes != 1 else "")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coord: PlantWateringCoordinator = hass.data[DOMAIN][entry.entry_id]
    device = PlantDevice(entry.entry_id, coord.name)

    async_add_entities(
        [
            LastWateringTextSensor(hass, coord, device, entry),
            LastWateringTimestampSensor(coord, device, entry),
            DaysSinceWateringSensor(coord, device, entry),
        ],
        update_before_add=True,
    )


class BasePlantEntity(Entity):
    def __init__(self, coord: PlantWateringCoordinator, device: PlantDevice, entry: ConfigEntry) -> None:
        self.coord = coord
        self.entry = entry
        self._attr_device_info = device.device_info()
        self.coord.add_listener(self.async_write_ha_state)

    @property
    def available(self) -> bool:
        return True


class LastWateringTextSensor(BasePlantEntity):
    _attr_icon = "mdi:watering-can-outline"
    _attr_should_poll = True

    def __init__(self, hass: HomeAssistant, coord: PlantWateringCoordinator, device: PlantDevice, entry: ConfigEntry) -> None:
        super().__init__(coord, device, entry)
        self.hass = hass
        self._attr_name = f"{coord.name} last watering"
        self._attr_unique_id = f"{entry.entry_id}_last_watering_text"

    @property
    def extra_state_attributes(self):
        return {
            "moisture_entity": self.coord.moisture_entity,
            "mode": self.coord.mode,
            "min_delta": self.coord.min_delta,
            "dry_threshold": self.coord.dry_threshold,
            "wet_threshold": self.coord.wet_threshold,
            "cooldown_minutes": int(self.coord.cooldown.total_seconds() // 60),
            "confirm_minutes": self.coord.confirm_minutes,
        }

    @property
    def state(self):
        lang = (self.hass.config.language or "en").lower()
        is_es = lang.startswith("es")

        if not self.coord.state.last_watering:
            return "Sin riegos registrados" if is_es else "No waterings recorded"

        now = datetime.now(timezone.utc)
        diff = int((now - self.coord.state.last_watering).total_seconds())
        diff = max(diff, 0)

        span = _humanize_es(diff) if is_es else _humanize_en(diff)
        return f"Ult. riego hace {span}" if is_es else f"Last watered {span} ago"

    async def async_update(self):
        # The text changes with time; HA will call this periodically
        return


class LastWateringTimestampSensor(BasePlantEntity):
    _attr_device_class = "timestamp"
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coord: PlantWateringCoordinator, device: PlantDevice, entry: ConfigEntry) -> None:
        super().__init__(coord, device, entry)
        self._attr_name = f"{coord.name} last watering (timestamp)"
        self._attr_unique_id = f"{entry.entry_id}_last_watering_ts"

    @property
    def state(self):
        return self.coord.state.last_watering.isoformat() if self.coord.state.last_watering else None


class DaysSinceWateringSensor(BasePlantEntity):
    _attr_icon = "mdi:calendar-clock"
    _attr_should_poll = True
    _attr_native_unit_of_measurement = "d"
    _attr_suggested_display_precision = 2

    def __init__(self, coord: PlantWateringCoordinator, device: PlantDevice, entry: ConfigEntry) -> None:
        super().__init__(coord, device, entry)
        self._attr_name = f"{coord.name} days since watering"
        self._attr_unique_id = f"{entry.entry_id}_days_since_watering"

    @property
    def native_value(self):
        if not self.coord.state.last_watering:
            return None
        now = datetime.now(timezone.utc)
        diff = (now - self.coord.state.last_watering).total_seconds()
        diff = max(diff, 0)
        return round(diff / 86400.0, 4)

    async def async_update(self):
        return
