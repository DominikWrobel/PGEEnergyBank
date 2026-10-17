"""PGE FIFO energy bank using Balance Neto cumulative sensors."""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, time, timezone
from dateutil.relativedelta import relativedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval, async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from datetime import timedelta

from .const import (
    DOMAIN, CONF_IMPORT, CONF_EXPORT, CONF_INITIAL, CONF_VINTAGE,
    CONF_CORRECTION, CONF_CORRECTION_DATE, CONF_CORRECTION_TOKEN,
    STORAGE_VERSION, DEBOUNCE_SECONDS,
)
from .ledger import EnergyLedger

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ['sensor']


def reading(hass: HomeAssistant, entity_id: str) -> float | None:
    state = hass.states.get(entity_id)
    if state is None or state.state in ('unknown', 'unavailable'):
        return None
    try:
        result = float(state.state)
        if not 0 <= result < 1e12:
            return None
        unit = state.attributes.get('unit_of_measurement', 'kWh')
        if unit == 'Wh':
            result /= 1000.0
        elif unit != 'kWh':
            return None
        return result
    except (ValueError, TypeError):
        return None


def local_midnight(hass, iso_date: str) -> datetime:
    """User-specified vintage is at midnight in Home Assistant's local time."""
    day = datetime.fromisoformat(iso_date).date()
    zone = dt_util.get_time_zone(hass.config.time_zone)
    return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc)


class Bank:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.store = Store(hass, STORAGE_VERSION, f'{DOMAIN}.{entry.entry_id}')
        self.ledger = EnergyLedger()
        self.previous_import = None
        self.previous_export = None
        self.correction_token = None
        self.blocked = False
        self._unsubs = []
        self._delayed = None
        self._lock = asyncio.Lock()
        self._callbacks = []

    @property
    def balance(self):
        return self.ledger.balance

    def subscribe(self, listener):
        self._callbacks.append(listener)

    @callback
    def broadcast(self):
        for listener in self._callbacks:
            listener()

    async def initialize(self):
        saved = await self.store.async_load()
        now = dt_util.utcnow()
        if saved is not None:
            self.ledger = EnergyLedger(saved.get('batches', []))
            self.previous_import = saved.get('previous_import')
            self.previous_export = saved.get('previous_export')
            self.correction_token = saved.get('correction_token')
            self.blocked = saved.get('blocked', False)
        else:
            self.ledger.correct(
                float(self.entry.data[CONF_INITIAL]),
                local_midnight(self.hass, self.entry.data[CONF_VINTAGE]), now,
            )
        self.ledger.expire(now)
        options = self.entry.options
        if options.get(CONF_CORRECTION_TOKEN) and options[CONF_CORRECTION_TOKEN] != self.correction_token:
            self.ledger.correct(
                float(options[CONF_CORRECTION]),
                local_midnight(self.hass, options[CONF_CORRECTION_DATE]), now,
            )
            self.previous_import = reading(self.hass, self.entry.data[CONF_IMPORT])
            self.previous_export = reading(self.hass, self.entry.data[CONF_EXPORT])
            self.correction_token = options[CONF_CORRECTION_TOKEN]
            self.blocked = False
        await self._persist()
        @callback
        def changed(event):
            if self._delayed:
                self._delayed()
            self._delayed = async_call_later(self.hass, DEBOUNCE_SECONDS, self._debounce)
        self._unsubs.append(async_track_state_change_event(
            self.hass, [self.entry.data[CONF_IMPORT], self.entry.data[CONF_EXPORT]], changed))
        self._unsubs.append(async_track_time_interval(self.hass, self._hourly, timedelta(hours=1)))
        self._unsubs.append(async_call_later(self.hass, DEBOUNCE_SECONDS, self._debounce))

    async def _debounce(self, _now):
        self._delayed = None
        await self.update()

    async def _hourly(self, _now):
        await self.update()

    async def update(self):
        async with self._lock:
            now = dt_util.utcnow()
            changed = self.ledger.expire(now)
            imp = reading(self.hass, self.entry.data[CONF_IMPORT])
            exp = reading(self.hass, self.entry.data[CONF_EXPORT])
            if imp is not None and exp is not None:
                if self.previous_import is None or self.previous_export is None:
                    self.previous_import, self.previous_export = imp, exp
                    changed = True
                elif imp + 1e-6 < self.previous_import or exp + 1e-6 < self.previous_export:
                    if not self.blocked:
                        _LOGGER.warning('PGE bank %s: cumulative source decreased; waiting for correction', self.entry.title)
                    self.blocked = True
                elif not self.blocked:
                    di = max(0, imp - self.previous_import)
                    de = max(0, exp - self.previous_export)
                    if di > 1e-7 or de > 1e-7:
                        self.ledger.process(di, de, dt_util.as_local(now))
                        self.previous_import, self.previous_export = imp, exp
                        changed = True
            if changed:
                await self._persist()
                self.broadcast()

    async def _persist(self):
        await self.store.async_save({
            'batches': self.ledger.batches,
            'previous_import': self.previous_import,
            'previous_export': self.previous_export,
            'correction_token': self.correction_token,
            'blocked': self.blocked,
        })

    async def close(self):
        if self._delayed:
            self._delayed()
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        async with self._lock:
            await self._persist()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    bank = Bank(hass, entry)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = bank
    await bank.initialize()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        bank = hass.data[DOMAIN].pop(entry.entry_id)
        await bank.close()
    return ok
