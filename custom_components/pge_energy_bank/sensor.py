"""Single long-term-statistics entity per PGE virtual energy bank."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    bank = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BankBalanceSensor(bank)])


class BankBalanceSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = 'Stan magazynu'
    _attr_icon = 'mdi:battery-clock'
    _attr_native_unit_of_measurement = 'kWh'
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_should_poll = False
    _attr_suggested_display_precision = 2

    def __init__(self, bank):
        self.bank = bank
        self._attr_unique_id = f'{bank.entry.entry_id}_balance'
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, bank.entry.entry_id)}, name=bank.entry.title)

    @property
    def native_value(self):
        return self.bank.balance

    async def async_added_to_hass(self):
        self.bank.subscribe(self._changed)

    @callback
    def _changed(self):
        self.async_write_ha_state()
