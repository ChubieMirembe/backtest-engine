from models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class ImbalanceStrategy(Strategy):
    def __init__(
        self,
        entry_threshold: float = 0.60,
        exit_threshold: float = 0.10,
        max_spread: float = 0.50,
    ):
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.max_spread = max_spread

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        if snapshot.best_bid is None or snapshot.best_ask is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        bid_size = snapshot.bid_levels.get(snapshot.best_bid, 0)
        ask_size = snapshot.ask_levels.get(snapshot.best_ask, 0)

        if bid_size + ask_size == 0:
            return Signal(snapshot.timestamp_ns, "HOLD", "empty_top_of_book")

        spread = snapshot.best_ask - snapshot.best_bid
        imbalance = (bid_size - ask_size) / (bid_size + ask_size)
        mid_price = (snapshot.best_bid + snapshot.best_ask) / 2.0

        if spread > self.max_spread:
            return Signal(snapshot.timestamp_ns, "HOLD", "spread_too_wide", price=mid_price)

        if position.side == 0:
            if imbalance >= self.entry_threshold:
                return Signal(
                    snapshot.timestamp_ns,
                    "BUY",
                    "positive_imbalance_entry",
                    price=mid_price,
                    metadata={"imbalance": imbalance, "spread": spread},
                )

            if imbalance <= -self.entry_threshold:
                return Signal(
                    snapshot.timestamp_ns,
                    "SELL",
                    "negative_imbalance_entry",
                    price=mid_price,
                    metadata={"imbalance": imbalance, "spread": spread},
                )

        elif position.side == 1:
            if imbalance <= self.exit_threshold:
                return Signal(
                    snapshot.timestamp_ns,
                    "EXIT_LONG",
                    "long_exit_on_imbalance_decay",
                    price=mid_price,
                    metadata={"imbalance": imbalance, "spread": spread},
                )

        elif position.side == -1:
            if imbalance >= -self.exit_threshold:
                return Signal(
                    snapshot.timestamp_ns,
                    "EXIT_SHORT",
                    "short_exit_on_imbalance_decay",
                    price=mid_price,
                    metadata={"imbalance": imbalance, "spread": spread},
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=mid_price)