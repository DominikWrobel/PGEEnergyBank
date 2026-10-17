"""UI configuration for PGE energy credit banks."""
from __future__ import annotations
from datetime import date
from uuid import uuid4
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from .const import (
    DOMAIN, CONF_IMPORT, CONF_EXPORT, CONF_INITIAL, CONF_VINTAGE,
    CONF_CORRECTION, CONF_CORRECTION_DATE, CONF_CORRECTION_TOKEN,
)


def date_valid(value: str) -> str:
    date.fromisoformat(value)
    return value


class PgeEnergyBankConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input[CONF_IMPORT] == user_input[CONF_EXPORT]:
                errors['base'] = 'same_entity'
            else:
                await self.async_set_unique_id(f"{user_input[CONF_IMPORT]}|{user_input[CONF_EXPORT]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input['name'], data=user_input)
        schema = vol.Schema({
            vol.Required('name', default='PGE Góra'): selector.TextSelector(),
            vol.Required(CONF_IMPORT): selector.EntitySelector(selector.EntitySelectorConfig(domain='sensor')),
            vol.Required(CONF_EXPORT): selector.EntitySelector(selector.EntitySelectorConfig(domain='sensor')),
            vol.Required(CONF_INITIAL, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=0, max=10000000)),
            vol.Required(CONF_VINTAGE, default=date.today().isoformat()): selector.DateSelector(),
        })
        return self.async_show_form(step_id='user', data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PgeEnergyBankOptionsFlow(config_entry)


class PgeEnergyBankOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Each submission is an explicit correction, not just a configuration edit.
            return self.async_create_entry(data={
                CONF_CORRECTION: float(user_input[CONF_CORRECTION]),
                CONF_CORRECTION_DATE: user_input[CONF_CORRECTION_DATE],
                CONF_CORRECTION_TOKEN: uuid4().hex,
            })
        runtime = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id)
        balance = round(runtime.balance, 3) if runtime else float(self._entry.data[CONF_INITIAL])
        schema = vol.Schema({
            vol.Required(CONF_CORRECTION, default=balance): vol.All(vol.Coerce(float), vol.Range(min=0, max=10000000)),
            vol.Required(CONF_CORRECTION_DATE, default=date.today().isoformat()): selector.DateSelector(),
        })
        return self.async_show_form(step_id='init', data_schema=schema)
