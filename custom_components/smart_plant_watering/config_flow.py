from __future__ import annotations

from typing import Any, Dict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

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
    DEFAULT_MODE,
    DEFAULT_MIN_DELTA,
    DEFAULT_DRY_THRESHOLD,
    DEFAULT_WET_THRESHOLD,
    DEFAULT_COOLDOWN_MINUTES,
    DEFAULT_CONFIRM_MINUTES,
)


def _schema(defaults: Dict[str, Any], mode: str) -> vol.Schema:
    schema: Dict[vol.Marker, Any] = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
        vol.Required(
            CONF_MOISTURE_ENTITY, default=defaults.get(CONF_MOISTURE_ENTITY, "")
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required(CONF_MODE, default=mode): vol.In([MODE_DELTA, MODE_THRESHOLD]),
        vol.Optional(
            CONF_COOLDOWN_MINUTES,
            default=int(defaults.get(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES)),
        ): vol.Coerce(int),
        vol.Optional(
            CONF_CONFIRM_MINUTES,
            default=int(defaults.get(CONF_CONFIRM_MINUTES, DEFAULT_CONFIRM_MINUTES)),
        ): vol.Coerce(int),
    }

    if mode == MODE_DELTA:
        schema[
            vol.Optional(
                CONF_MIN_DELTA,
                default=float(defaults.get(CONF_MIN_DELTA, DEFAULT_MIN_DELTA)),
            )
        ] = vol.Coerce(float)
    else:
        schema[
            vol.Required(
                CONF_DRY_THRESHOLD,
                default=float(defaults.get(CONF_DRY_THRESHOLD, DEFAULT_DRY_THRESHOLD)),
            )
        ] = vol.Coerce(float)
        schema[
            vol.Required(
                CONF_WET_THRESHOLD,
                default=float(defaults.get(CONF_WET_THRESHOLD, DEFAULT_WET_THRESHOLD)),
            )
        ] = vol.Coerce(float)

    return vol.Schema(schema)


def _entry_data_by_mode(data: Dict[str, Any]) -> Dict[str, Any]:
    mode = data.get(CONF_MODE, DEFAULT_MODE)
    cleaned = {
        CONF_NAME: data[CONF_NAME],
        CONF_MOISTURE_ENTITY: data[CONF_MOISTURE_ENTITY],
        CONF_MODE: mode,
        CONF_COOLDOWN_MINUTES: data.get(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES),
        CONF_CONFIRM_MINUTES: data.get(CONF_CONFIRM_MINUTES, DEFAULT_CONFIRM_MINUTES),
    }

    if mode == MODE_DELTA:
        cleaned[CONF_MIN_DELTA] = data.get(CONF_MIN_DELTA, DEFAULT_MIN_DELTA)
    else:
        cleaned[CONF_DRY_THRESHOLD] = data.get(CONF_DRY_THRESHOLD, DEFAULT_DRY_THRESHOLD)
        cleaned[CONF_WET_THRESHOLD] = data.get(CONF_WET_THRESHOLD, DEFAULT_WET_THRESHOLD)

    return cleaned


class SmartPlantWateringFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    _draft: Dict[str, Any]
    _current_mode: str

    def __init__(self) -> None:
        self._draft = {}
        self._current_mode = DEFAULT_MODE

    async def async_step_user(self, user_input=None):
        errors = {}

        defaults = {
            CONF_NAME: "",
            CONF_MODE: DEFAULT_MODE,
            CONF_MIN_DELTA: DEFAULT_MIN_DELTA,
            CONF_DRY_THRESHOLD: DEFAULT_DRY_THRESHOLD,
            CONF_WET_THRESHOLD: DEFAULT_WET_THRESHOLD,
            CONF_COOLDOWN_MINUTES: DEFAULT_COOLDOWN_MINUTES,
            CONF_CONFIRM_MINUTES: DEFAULT_CONFIRM_MINUTES,
        }
        defaults.update(self._draft)

        if user_input is not None:
            self._draft.update(user_input)
            selected_mode = self._draft.get(CONF_MODE, DEFAULT_MODE)

            if selected_mode != self._current_mode:
                self._current_mode = selected_mode
                return self.async_show_form(
                    step_id="user",
                    data_schema=_schema(self._draft, self._current_mode),
                    errors=errors,
                )

            cleaned = _entry_data_by_mode(self._draft)

            await self.async_set_unique_id(cleaned[CONF_MOISTURE_ENTITY])
            self._abort_if_unique_id_configured()

            st = self.hass.states.get(cleaned[CONF_MOISTURE_ENTITY])
            if st and st.state not in ("unknown", "unavailable"):
                try:
                    float(st.state)
                except ValueError:
                    errors["base"] = "not_numeric"

            if (
                cleaned[CONF_MODE] == MODE_THRESHOLD
                and float(cleaned[CONF_WET_THRESHOLD]) <= float(cleaned[CONF_DRY_THRESHOLD])
            ):
                errors["base"] = "invalid_thresholds"

            if not errors:
                return self.async_create_entry(title=cleaned[CONF_NAME], data=cleaned)

        selected_mode = defaults.get(CONF_MODE, DEFAULT_MODE)
        self._current_mode = selected_mode
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(defaults, selected_mode),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SmartPlantWateringOptionsFlow(config_entry)


class SmartPlantWateringOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry
        self._draft = dict(entry.data)
        self._draft.update(entry.options)
        self._current_mode = self._draft.get(CONF_MODE, DEFAULT_MODE)

    async def async_step_init(self, user_input=None):
        errors = {}

        defaults = dict(self._draft)

        if user_input is not None:
            self._draft.update(user_input)
            selected_mode = self._draft.get(CONF_MODE, DEFAULT_MODE)

            if selected_mode != self._current_mode:
                self._current_mode = selected_mode
                return self.async_show_form(
                    step_id="init",
                    data_schema=_schema(self._draft, self._current_mode),
                    errors=errors,
                )

            cleaned = _entry_data_by_mode(self._draft)

            st = self.hass.states.get(cleaned[CONF_MOISTURE_ENTITY])
            if st and st.state not in ("unknown", "unavailable"):
                try:
                    float(st.state)
                except ValueError:
                    errors["base"] = "not_numeric"

            if (
                cleaned[CONF_MODE] == MODE_THRESHOLD
                and float(cleaned[CONF_WET_THRESHOLD]) <= float(cleaned[CONF_DRY_THRESHOLD])
            ):
                errors["base"] = "invalid_thresholds"

            if not errors:
                return self.async_create_entry(title="", data=cleaned)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(defaults, self._current_mode),
            errors=errors,
        )
