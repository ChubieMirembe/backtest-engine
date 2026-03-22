from dataclasses import dataclass
from typing import Optional

from models import PositionState, Signal, BookSnapshot


@dataclass
class RiskConfig:
    allow_shorts: bool
    max_position_size: int
    max_notional: float
    max_trades: int
    cooldown_ns: int


class RiskManager:
    def __init__(self, config: RiskConfig):
        self.config = config
        self.last_fill_timestamp_ns: Optional[int] = None

    def approve(
        self,
        signal: Signal,
        snapshot: BookSnapshot,
        position: PositionState,
        entries_so_far: int,
    ) -> Signal:
        if signal.action == "HOLD":
            return signal

        if entries_so_far >= self.config.max_trades and signal.action in ("BUY", "SELL"):
            return Signal(signal.timestamp_ns, "HOLD", "risk_max_trades", metadata=signal.metadata)

        if (
            self.last_fill_timestamp_ns is not None
            and self.config.cooldown_ns > 0
            and signal.timestamp_ns - self.last_fill_timestamp_ns < self.config.cooldown_ns
        ):
            return Signal(signal.timestamp_ns, "HOLD", "risk_cooldown", metadata=signal.metadata)

        if signal.action == "SELL" and not self.config.allow_shorts and position.is_flat:
            return Signal(signal.timestamp_ns, "HOLD", "risk_shorts_disabled", metadata=signal.metadata)

        if signal.action in ("BUY", "SELL") and signal.quantity is not None:
            if signal.quantity > self.config.max_position_size:
                return Signal(signal.timestamp_ns, "HOLD", "risk_max_position", metadata=signal.metadata)

        if signal.action in ("BUY", "SELL") and signal.price is not None:
            qty = signal.quantity if signal.quantity is not None else self.config.max_position_size
            notional = signal.price * qty
            if notional > self.config.max_notional:
                return Signal(signal.timestamp_ns, "HOLD", "risk_max_notional", metadata=signal.metadata)

        return signal

    def notify_fill(self, timestamp_ns: int):
        self.last_fill_timestamp_ns = timestamp_ns