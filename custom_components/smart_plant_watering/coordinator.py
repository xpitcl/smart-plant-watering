from __future__ import annotations

import asyncio
import logging
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
HISTORY_LOOKBACK_DAYS = 30
_LOGGER = logging.getLogger(__name__)


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
        _LOGGER.debug(
            "[%s] Loading coordinator (entity=%s, mode=%s)",
            self.entry.entry_id,
            self.moisture_entity,
            self.mode,
        )
        data = await self.store.async_load() or {}
        ts = data.get("last_watering")
        if ts:
            self.state.last_watering = datetime.fromisoformat(ts)
            _LOGGER.debug(
                "[%s] Loaded stored last_watering=%s",
                self.entry.entry_id,
                self.state.last_watering.isoformat(),
            )
        else:
            _LOGGER.debug("[%s] No stored last_watering, bootstrapping from history", self.entry.entry_id)
            await self._async_bootstrap_from_history()

    async def async_save(self) -> None:
        await self.store.async_save(
            {"last_watering": self.state.last_watering.isoformat() if self.state.last_watering else None}
        )

    @callback
    def async_start(self) -> None:
        if self._unsub:
            return
        _LOGGER.debug("[%s] Starting state tracking for %s", self.entry.entry_id, self.moisture_entity)
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
            _LOGGER.debug("[%s] Stopped state tracking", self.entry.entry_id)

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
            _LOGGER.debug(
                "[%s] Ignoring non-numeric state change old=%s new=%s",
                self.entry.entry_id,
                old.state,
                new.state,
            )
            return

        now = datetime.now(timezone.utc)
        _LOGGER.debug(
            "[%s] State change %s -> %s at %s",
            self.entry.entry_id,
            from_v,
            to_v,
            now.isoformat(),
        )

        # Cooldown
        if self.state.last_watering and (now - self.state.last_watering) < self.cooldown:
            _LOGGER.debug(
                "[%s] Ignored by cooldown (last=%s cooldown=%s)",
                self.entry.entry_id,
                self.state.last_watering.isoformat(),
                self.cooldown,
            )
            return

        should_trigger = False

        if self.mode == MODE_DELTA:
            delta = to_v - from_v
            if delta >= self.min_delta:
                should_trigger = True
            _LOGGER.debug(
                "[%s] Delta eval: delta=%.3f min_delta=%.3f trigger=%s",
                self.entry.entry_id,
                delta,
                self.min_delta,
                should_trigger,
            )

        elif self.mode == MODE_THRESHOLD:
            if from_v < self.dry_threshold and to_v >= self.wet_threshold:
                should_trigger = True
            _LOGGER.debug(
                "[%s] Threshold eval: from=%.3f to=%.3f dry=%.3f wet=%.3f trigger=%s",
                self.entry.entry_id,
                from_v,
                to_v,
                self.dry_threshold,
                self.wet_threshold,
                should_trigger,
            )

        if not should_trigger:
            return

        if self.confirm_minutes > 0:
            _LOGGER.debug(
                "[%s] Triggered; waiting confirmation for %s minutes",
                self.entry.entry_id,
                self.confirm_minutes,
            )
            self.hass.async_create_task(self._confirm_and_set(now))
        else:
            _LOGGER.debug("[%s] Triggered; setting last_watering immediately", self.entry.entry_id)
            self.hass.async_create_task(self._set_last_watering(now))

    async def _confirm_and_set(self, candidate: datetime) -> None:
        _LOGGER.debug("[%s] Confirmation started for candidate=%s", self.entry.entry_id, candidate.isoformat())
        await asyncio.sleep(self.confirm_minutes * 60)

        # Solo en modo threshold exigimos mantenerse "húmedo".
        if self.mode == MODE_THRESHOLD and self.wet_threshold:
            st = self.hass.states.get(self.moisture_entity)
            if not st or st.state in ("unknown", "unavailable"):
                _LOGGER.debug("[%s] Confirmation failed: current state unavailable", self.entry.entry_id)
                return
            try:
                cur = float(st.state)
            except ValueError:
                _LOGGER.debug("[%s] Confirmation failed: current state not numeric (%s)", self.entry.entry_id, st.state)
                return
            if cur < self.wet_threshold:
                _LOGGER.debug(
                    "[%s] Confirmation failed: current=%.3f below wet_threshold=%.3f",
                    self.entry.entry_id,
                    cur,
                    self.wet_threshold,
                )
                return

        _LOGGER.debug("[%s] Confirmation passed; setting last_watering", self.entry.entry_id)
        await self._set_last_watering(candidate)

    async def _set_last_watering(self, dt: datetime) -> None:
        self.state.last_watering = dt
        await self.async_save()
        self._notify()
        _LOGGER.debug("[%s] last_watering set to %s", self.entry.entry_id, dt.isoformat())

    async def _async_bootstrap_from_history(self) -> None:
        """Try to infer last watering from recorder history (last 30 days)."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=HISTORY_LOOKBACK_DAYS)
        _LOGGER.debug(
            "[%s] Bootstrapping from history for %s in range %s -> %s",
            self.entry.entry_id,
            self.moisture_entity,
            start.isoformat(),
            end.isoformat(),
        )
        states = await self._async_get_history_states(start, end)
        if len(states) < 2:
            _LOGGER.debug("[%s] Not enough history states found (%d)", self.entry.entry_id, len(states))
            return
        _LOGGER.debug("[%s] Retrieved %d history states", self.entry.entry_id, len(states))

        last_detected: datetime | None = None
        for old, new in zip(states, states[1:]):
            if old.state in ("unknown", "unavailable") or new.state in ("unknown", "unavailable"):
                continue

            try:
                from_v = float(old.state)
                to_v = float(new.state)
            except ValueError:
                continue

            should_trigger = False
            if self.mode == MODE_DELTA:
                should_trigger = (to_v - from_v) >= self.min_delta
            elif self.mode == MODE_THRESHOLD:
                should_trigger = from_v < self.dry_threshold and to_v >= self.wet_threshold

            if not should_trigger:
                continue

            event_time = self._as_utc(getattr(new, "last_changed", None) or getattr(new, "last_updated", None))
            if event_time is None:
                continue

            if last_detected and (event_time - last_detected) < self.cooldown:
                _LOGGER.debug(
                    "[%s] Skipping historical candidate %s due cooldown",
                    self.entry.entry_id,
                    event_time.isoformat(),
                )
                continue
            last_detected = event_time
            _LOGGER.debug(
                "[%s] Historical watering candidate detected at %s",
                self.entry.entry_id,
                event_time.isoformat(),
            )

        if last_detected is None:
            _LOGGER.debug("[%s] No historical watering candidate detected", self.entry.entry_id)
            return

        self.state.last_watering = last_detected
        await self.async_save()
        self._notify()
        _LOGGER.debug(
            "Bootstrapped last watering for %s from history: %s",
            self.moisture_entity,
            last_detected.isoformat(),
        )

    async def _async_get_history_states(self, start: datetime, end: datetime) -> list[Any]:
        """Fetch recorder states for this moisture entity within a time window."""
        try:
            from homeassistant.components.recorder import history as recorder_history
        except ImportError:
            try:
                # Older HA versions may expose helpers here.
                from homeassistant.components import history as recorder_history
            except ImportError:
                _LOGGER.debug("Recorder history API not available; skipping bootstrap")
                return []

        def _fetch() -> dict[str, list[Any]]:
            get_changes = getattr(recorder_history, "get_state_changes_during_period", None)
            if callable(get_changes):
                try:
                    return get_changes(
                        self.hass,
                        start,
                        end,
                        self.moisture_entity,
                        include_start_time_state=True,
                        no_attributes=True,
                    )
                except TypeError:
                    # Signature varies between HA versions.
                    return get_changes(
                        self.hass,
                        start,
                        end,
                        self.moisture_entity,
                        True,
                        True,
                    )

            get_significant = getattr(recorder_history, "get_significant_states", None)
            if callable(get_significant):
                try:
                    return get_significant(
                        self.hass,
                        start,
                        end,
                        [self.moisture_entity],
                        include_start_time_state=True,
                        significant_changes_only=False,
                        minimal_response=False,
                        no_attributes=True,
                    )
                except TypeError:
                    return get_significant(
                        self.hass,
                        start,
                        end,
                        [self.moisture_entity],
                        True,
                        False,
                        False,
                        True,
                    )

            raise RuntimeError("No compatible recorder history helper found")

        try:
            history = await self.hass.async_add_executor_job(_fetch)
        except Exception as err:  # pragma: no cover - defensive for recorder variations
            _LOGGER.warning("Failed to read history for %s: %s", self.moisture_entity, err)
            return []

        states = history.get(self.moisture_entity, [])
        _LOGGER.debug("[%s] History fetch returned %d states", self.entry.entry_id, len(states))
        return states

    @staticmethod
    def _as_utc(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
