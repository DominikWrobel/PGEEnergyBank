"""Pure-Python FIFO energy ledger, independent of Home Assistant."""
from __future__ import annotations
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

EPSILON = 1e-7


def expiry_for(created: datetime) -> datetime:
    """An energy tranche expires 12 calendar months after deposit."""
    return created.replace(day=1, hour=0, minute=0, second=0, microsecond=0) + relativedelta(months=13)


class EnergyLedger:
    def __init__(self, batches: list[dict] | None = None) -> None:
        self.batches = list(batches or [])

    @property
    def balance(self) -> float:
        return round(sum(b['amount'] for b in self.batches), 6)

    def expire(self, now: datetime) -> bool:
        before = len(self.batches)
        self.batches = [b for b in self.batches if expiry_for(datetime.fromisoformat(b['at'])) > now and b['amount'] > EPSILON]
        return before != len(self.batches)

    def deposit(self, energy_kwh: float, when: datetime) -> None:
        if energy_kwh > EPSILON:
            self.batches.append({'at': when.isoformat(), 'amount': round(energy_kwh, 6)})
            self.batches.sort(key=lambda b: b['at'])

    def consume(self, energy_kwh: float) -> None:
        remaining = max(0.0, energy_kwh)
        for batch in self.batches:
            if remaining <= EPSILON:
                break
            taken = min(remaining, batch['amount'])
            batch['amount'] = round(batch['amount'] - taken, 6)
            remaining -= taken
        self.batches = [b for b in self.batches if b['amount'] > EPSILON]

    def process(self, import_delta: float, export_delta: float, now: datetime, factor: float = 0.8) -> None:
        self.expire(now)
        # One finished metering interval is settled as a unit. Export increases
        # stored credit and consumption spends oldest credit first.
        self.deposit(max(0.0, export_delta) * factor, now)
        self.consume(max(0.0, import_delta))

    def correct(self, balance: float, vintage: datetime, now: datetime) -> None:
        if balance < 0:
            raise ValueError('Balance cannot be negative')
        self.batches = []
        if expiry_for(vintage) > now:
            self.deposit(balance, vintage)
