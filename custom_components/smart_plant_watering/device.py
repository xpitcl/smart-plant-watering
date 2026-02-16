from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


@dataclass(frozen=True)
class PlantDevice:
    entry_id: str
    name: str

    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry_id)},
            name=self.name,
            manufacturer="Smart Plant Watering",
            model="Virtual Plant Device",
        )
