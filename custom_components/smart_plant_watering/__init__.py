from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import PlantWateringCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coord = PlantWateringCoordinator(hass, entry)
    await coord.async_load()
    coord.async_start()

    hass.data[DOMAIN][entry.entry_id] = coord

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coord: PlantWateringCoordinator | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if coord:
        coord.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
