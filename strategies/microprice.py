from models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class MicropriceStrategy(Strategy):
    """
    Microprice / VAMP-style top-of-book signal

    microprice = (P_bid * Q_ask + P_ask * Q_bid) / (Q_bid + Q_ask)

    pressure = microprice - mid

    Long:
        pressure >= long_epsilon
        spread <= max_spread

    Short:
        pressure <= -short_epsilon
        spread <= max_spread
    """

    def __init__(
        self,
        quantity: int = 1,
        max_spread: float = 0.50,
        long_epsilon: float = 0.01,
        short_epsilon: float = 0.01,
        exit_epsilon: float = 0.002,
        max_holding_time_ns: int | None = None,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.max_spread = max_spread
        self.long_epsilon = long_epsilon
        self.short_epsilon = short_epsilon
        self.exit_epsilon = exit_epsilon
        self.max_holding_time_ns = max_holding_time_ns
        self.debug = debug

    def _log(self, payload):
        if self.debug:
            print("MICROPRICE_DEBUG", payload)

    def _holding_time_expired(self, snapshot: BookSnapshot, position: PositionState) -> bool:
        if (
            self.max_holding_time_ns is None
            or position.entry_timestamp_ns is None
            or position.is_flat
        ):
            return False
        return (snapshot.timestamp_ns - position.entry_timestamp_ns) >= self.max_holding_time_ns

    def _microprice(self, snapshot: BookSnapshot) -> float | None:
        if snapshot.best_bid is None or snapshot.best_ask is None:
            return None

        q_bid = snapshot.best_bid_size
        q_ask = snapshot.best_ask_size
        total = q_bid + q_ask

        if total <= 0:
            return None

        return ((snapshot.best_bid * q_ask) + (snapshot.best_ask * q_bid)) / total

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        if snapshot.best_bid is None or snapshot.best_ask is None or snapshot.mid_price is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        if snapshot.spread is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "missing_features", price=snapshot.mid_price)

        if snapshot.spread > self.max_spread:
            if position.side == 1:
                return Signal(snapshot.timestamp_ns, "EXIT_LONG", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            if position.side == -1:
                return Signal(snapshot.timestamp_ns, "EXIT_SHORT", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            return Signal(snapshot.timestamp_ns, "HOLD", "spread_too_wide", price=snapshot.mid_price)

        microprice = self._microprice(snapshot)
        if microprice is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "missing_microprice", price=snapshot.mid_price)

        pressure = microprice - snapshot.mid_price

        self._log(
            {
                "timestamp_ns": snapshot.timestamp_ns,
                "microprice": microprice,
                "mid_price": snapshot.mid_price,
                "pressure": pressure,
                "spread": snapshot.spread,
            }
        )

        if position.is_flat:
            if pressure >= self.long_epsilon:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="microprice_long",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"microprice": microprice, "pressure": pressure},
                )

            if pressure <= -self.short_epsilon:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="microprice_short",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"microprice": microprice, "pressure": pressure},
                )

            return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=snapshot.mid_price)

        if position.side == 1:
            if pressure <= self.exit_epsilon or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="microprice_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        if position.side == -1:
            if pressure >= -self.exit_epsilon or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="microprice_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "hold_position", price=snapshot.mid_price)