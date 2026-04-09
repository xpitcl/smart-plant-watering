from __future__ import annotations

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


def _schema(defaults: dict) -> vol.Schema:
    schema = {
        vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
        vol.Required(
            CONF_MOISTURE_ENTITY, default=defaults.get(CONF_MOISTURE_ENTITY, "")
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Required(CONF_MODE, default=defaults.get(CONF_MODE, DEFAULT_MODE)): vol.In(
            [MODE_DELTA, MODE_THRESHOLD]
        ),
        vol.Optional(
            CONF_MIN_DELTA,
            default=float(defaults.get(CONF_MIN_DELTA, DEFAULT_MIN_DELTA)),
        ): vol.Coerce(float),
        vol.Optional(
            CONF_COOLDOWN_MINUTES,
            default=int(defaults.get(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES)),
        ): vol.Coerce(int),
        vol.Optional(
            CONF_CONFIRM_MINUTES,
            default=int(defaults.get(CONF_CONFIRM_MINUTES, DEFAULT_CONFIRM_MINUTES)),
        ): vol.Coerce(int),
    }

    dry_default = defaults.get(CONF_DRY_THRESHOLD, "")
    if dry_default in ("", None):
        schema[vol.Optional(CONF_DRY_THRESHOLD)] = vol.Coerce(float)
    else:
        schema[vol.Optional(CONF_DRY_THRESHOLD, default=float(dry_default))] = vol.Coerce(float)

    wet_default = defaults.get(CONF_WET_THRESHOLD, "")
    if wet_default in ("", None):
        schema[vol.Optional(CONF_WET_THRESHOLD)] = vol.Coerce(float)
    else:
        schema[vol.Optional(CONF_WET_THRESHOLD, default=float(wet_default))] = vol.Coerce(float)

    return vol.Schema(schema)


def _normalize_user_input(user_input: dict) -> dict:
    normalized = dict(user_input)

    for key in (CONF_MIN_DELTA, CONF_DRY_THRESHOLD, CONF_WET_THRESHOLD):
        value = normalized.get(key)
        if value in ("", None):
            normalized[key] = 0.0
        else:
            normalized[key] = float(value)

    normalized[CONF_COOLDOWN_MINUTES] = int(normalized.get(CONF_COOLDOWN_MINUTES, DEFAULT_COOLDOWN_MINUTES))
    normalized[CONF_CONFIRM_MINUTES] = int(normalized.get(CONF_CONFIRM_MINUTES, DEFAULT_CONFIRM_MINUTES))
    return normalized


def _validate_input(hass, user_input: dict) -> dict:
    errors = {}

    st = hass.states.get(user_input[CONF_MOISTURE_ENTITY])
    if st and st.state not in ("unknown", "unavailable"):
        try:
            float(st.state)
        except ValueError:
            errors["base"] = "not_numeric"

    if (
        errors.get("base") is None
        and (
            int(user_input[CONF_COOLDOWN_MINUTES]) < 0
            or int(user_input[CONF_CONFIRM_MINUTES]) < 0
        )
    ):
        errors["base"] = "invalid_minutes"

    if (
        errors.get("base") is None
        and user_input[CONF_MODE] == MODE_THRESHOLD
        and float(user_input[CONF_WET_THRESHOLD]) <= float(user_input[CONF_DRY_THRESHOLD])
    ):
        errors["base"] = "invalid_thresholds"

    return errors


class SmartPlantWateringFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            normalized = _normalize_user_input(user_input)
            await self.async_set_unique_id(normalized[CONF_MOISTURE_ENTITY])
            self._abort_if_unique_id_configured()
            errors = _validate_input(self.hass, normalized)

            if not errors:
                return self.async_create_entry(title=normalized[CONF_NAME], data=normalized)

        defaults = {
            CONF_NAME: "",
            CONF_MODE: DEFAULT_MODE,
            CONF_MIN_DELTA: DEFAULT_MIN_DELTA,
            CONF_DRY_THRESHOLD: "",
            CONF_WET_THRESHOLD: "",
            CONF_COOLDOWN_MINUTES: DEFAULT_COOLDOWN_MINUTES,
            CONF_CONFIRM_MINUTES: DEFAULT_CONFIRM_MINUTES,
        }
        return self.async_show_form(step_id="user", data_schema=_schema(defaults), errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SmartPlantWateringOptionsFlow(config_entry)


class SmartPlantWateringOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input=None):
        errors = {}

        defaults = dict(self.entry.data)
        defaults.update(self.entry.options)

        if user_input is not None:
            normalized = _normalize_user_input(user_input)
            errors = _validate_input(self.hass, normalized)

            if not errors:
                return self.async_create_entry(title="", data=normalized)

        defaults.setdefault(CONF_DRY_THRESHOLD, "")
        defaults.setdefault(CONF_WET_THRESHOLD, "")

        return self.async_show_form(step_id="init", data_schema=_schema(defaults), errors=errors)
