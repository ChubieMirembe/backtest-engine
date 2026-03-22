from models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class ImbalanceStrategy(Strategy):
    def __init__(
        self,
        entry_threshold: float = 0.60,
        exit_threshold: float = 0.10,
        max_spread: float = 0.50,
        quantity: int = 1,
    ):
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.max_spread = max_spread
        self.quantity = quantity

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        if snapshot.best_bid is None or snapshot.best_ask is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        spread = snapshot.spread
        imbalance = snapshot.imbalance
        mid_price = snapshot.mid_price

        if spread is None or imbalance is None or mid_price is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "missing_features")

        if spread > self.max_spread:
            return Signal(snapshot.timestamp_ns, "HOLD", "spread_too_wide", price=mid_price)

        if position.is_flat:
            if imbalance >= self.entry_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="positive_imbalance_entry",
                    price=mid_price,
                    quantity=self.quantity,
                    metadata={"imbalance": imbalance, "spread": spread},
                )

            if imbalance <= -self.entry_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="negative_imbalance_entry",
                    price=mid_price,
                    quantity=self.quantity,
                    metadata={"imbalance": imbalance, "spread": spread},
                )

        elif position.side == 1:
            if imbalance <= self.exit_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="long_exit_on_imbalance_decay",
                    price=mid_price,
                    quantity=position.quantity,
                    metadata={"imbalance": imbalance, "spread": spread},
                )

        elif position.side == -1:
            if imbalance >= -self.exit_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="short_exit_on_imbalance_decay",
                    price=mid_price,
                    quantity=position.quantity,
                    metadata={"imbalance": imbalance, "spread": spread},
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=mid_price)