from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_MOISTURE_ENTITY,
    CONF_MODE,
    MODE_DELTA,
    MODE_THRESHOLD,
    CONF_MIN_DELTA,
    CONF_DRY_THRESHOLD,
    CONF_WET_THRESHOLD,
    CONF_COOLDOWN_MINUTES,
    CONF_CONFIRM_MINUTES,
)

STORAGE_VERSION = 1


@dataclass
class WateringState:
    last_watering: datetime | None = None


class PlantWateringCoordinator:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry

        self.state = WateringState()
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")

        self._unsub = None
        self._listeners: list[Callable[[], None]] = []

    def _merged(self) -> dict[str, Any]:
        d = dict(self.entry.data)
        d.update(self.entry.options)
        return d

    @property
    def name(self) -> str:
        return self._merged().get(CONF_NAME, "Plant")

    @property
    def moisture_entity(self) -> str:
        return self._merged()[CONF_MOISTURE_ENTITY]

    @property
    def mode(self) -> str:
        return self._merged().get(CONF_MODE, MODE_DELTA)

    @property
    def min_delta(self) -> float:
        return float(self._merged().get(CONF_MIN_DELTA, 0.0))

    @property
    def dry_threshold(self) -> float:
        return float(self._merged().get(CONF_DRY_THRESHOLD, 0.0))

    @property
    def wet_threshold(self) -> float:
        return float(self._merged().get(CONF_WET_THRESHOLD, 0.0))

    @property
    def cooldown(self) -> timedelta:
        return timedelta(minutes=int(self._merged().get(CONF_COOLDOWN_MINUTES, 0)))

    @property
    def confirm_minutes(self) -> int:
        return int(self._merged().get(CONF_CONFIRM_MINUTES, 0))

    def add_listener(self, cb: Callable[[], None]) -> None:
        self._listeners.append(cb)

    def _notify(self) -> None:
        for cb in self._listeners:
            cb()

    async def async_load(self) -> None:
        data = await self.store.async_load() or {}
        ts = data.get("last_watering")
        if ts:
            self.state.last_watering = datetime.fromisoformat(ts)

    async def async_save(self) -> None:
        await self.store.async_save(
            {"last_watering": self.state.last_watering.isoformat() if self.state.last_watering else None}
        )

    @callback
    def async_start(self) -> None:
        if self._unsub:
            return
        self._unsub = async_track_state_change_event(
            self.hass,
            [self.moisture_entity],
            self._handle_state_change,
        )

    @callback
    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    @callback
    def _handle_state_change(self, event) -> None:
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if old is None or new is None:
            return

        # Evita falsos positivos típicos (unknown/unavailable)
        if old.state in ("unknown", "unavailable") or new.state in ("unknown", "unavailable"):
            return

        try:
            from_v = float(old.state)
            to_v = float(new.state)
        except ValueError:
            return

        now = datetime.now(timezone.utc)

        # Cooldown
        if self.state.last_watering and (now - self.state.last_watering) < self.cooldown:
            return

        should_trigger = False

        if self.mode == MODE_DELTA:
            delta = to_v - from_v
            if delta >= self.min_delta:
                should_trigger = True

        elif self.mode == MODE_THRESHOLD:
            if from_v < self.dry_threshold and to_v >= self.wet_threshold:
                should_trigger = True

        if not should_trigger:
            return

        if self.confirm_minutes > 0:
            self.hass.async_create_task(self._confirm_and_set(now))
        else:
            self.hass.async_create_task(self._set_last_watering(now))

    async def _confirm_and_set(self, candidate: datetime) -> None:
        await asyncio.sleep(self.confirm_minutes * 60)

        # Solo en modo threshold exigimos mantenerse "húmedo".
        if self.mode == MODE_THRESHOLD and self.wet_threshold:
            st = self.hass.states.get(self.moisture_entity)
            if not st or st.state in ("unknown", "unavailable"):
                return
            try:
                cur = float(st.state)
            except ValueError:
                return
            if cur < self.wet_threshold:
                return

        await self._set_last_watering(candidate)

    async def _set_last_watering(self, dt: datetime) -> None:
        self.state.last_watering = dt
        await self.async_save()
        self._notify()
