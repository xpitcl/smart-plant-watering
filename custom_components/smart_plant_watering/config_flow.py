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
    return vol.Schema(
        {
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
                CONF_DRY_THRESHOLD,
                default=float(defaults.get(CONF_DRY_THRESHOLD, DEFAULT_DRY_THRESHOLD)),
            ): vol.Coerce(float),
            vol.Optional(
                CONF_WET_THRESHOLD,
                default=float(defaults.get(CONF_WET_THRESHOLD, DEFAULT_WET_THRESHOLD)),
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
    )


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
            await self.async_set_unique_id(user_input[CONF_MOISTURE_ENTITY])
            self._abort_if_unique_id_configured()
            errors = _validate_input(self.hass, user_input)

            if not errors:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        defaults = {
            CONF_NAME: "",
            CONF_MODE: DEFAULT_MODE,
            CONF_MIN_DELTA: DEFAULT_MIN_DELTA,
            CONF_DRY_THRESHOLD: DEFAULT_DRY_THRESHOLD,
            CONF_WET_THRESHOLD: DEFAULT_WET_THRESHOLD,
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
            errors = _validate_input(self.hass, user_input)

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=_schema(defaults), errors=errors)
