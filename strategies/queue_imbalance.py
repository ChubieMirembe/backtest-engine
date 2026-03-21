from models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class QueueImbalanceStrategy(Strategy):
    """
    Queue Imbalance (QI)

    QI = (Q_bid - Q_ask) / (Q_bid + Q_ask)

    Long:
        QI >= long_threshold
        spread <= max_spread

    Short:
        QI <= short_threshold
        spread <= max_spread

    Exit long:
        QI falls back below long_exit_threshold
        or spread widens too much
        or max holding time reached

    Exit short:
        QI rises above short_exit_threshold
        or spread widens too much
        or max holding time reached
    """

    def __init__(
        self,
        quantity: int = 1,
        max_spread: float = 0.50,
        long_threshold: float = 0.60,
        short_threshold: float = -0.60,
        long_exit_threshold: float = 0.10,
        short_exit_threshold: float = -0.10,
        max_holding_time_ns: int | None = None,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.max_spread = max_spread
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.long_exit_threshold = long_exit_threshold
        self.short_exit_threshold = short_exit_threshold
        self.max_holding_time_ns = max_holding_time_ns
        self.debug = debug

    def _log(self, payload):
        if self.debug:
            print("QI_DEBUG", payload)

    def _holding_time_expired(self, snapshot: BookSnapshot, position: PositionState) -> bool:
        if (
            self.max_holding_time_ns is None
            or position.entry_timestamp_ns is None
            or position.is_flat
        ):
            return False
        return (snapshot.timestamp_ns - position.entry_timestamp_ns) >= self.max_holding_time_ns

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        if snapshot.best_bid is None or snapshot.best_ask is None or snapshot.mid_price is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        if snapshot.spread is None or snapshot.imbalance is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "missing_features", price=snapshot.mid_price)

        spread = snapshot.spread
        qi = snapshot.imbalance

        self._log(
            {
                "timestamp_ns": snapshot.timestamp_ns,
                "spread": spread,
                "qi": qi,
                "best_bid": snapshot.best_bid,
                "best_bid_size": snapshot.best_bid_size,
                "best_ask": snapshot.best_ask,
                "best_ask_size": snapshot.best_ask_size,
            }
        )

        if spread > self.max_spread:
            if position.side == 1:
                return Signal(snapshot.timestamp_ns, "EXIT_LONG", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            if position.side == -1:
                return Signal(snapshot.timestamp_ns, "EXIT_SHORT", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            return Signal(snapshot.timestamp_ns, "HOLD", "spread_too_wide", price=snapshot.mid_price)

        if position.is_flat:
            if qi >= self.long_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="qi_long",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"qi": qi, "spread": spread},
                )

            if qi <= self.short_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="qi_short",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"qi": qi, "spread": spread},
                )

            return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=snapshot.mid_price)

        if position.side == 1:
            if qi <= self.long_exit_threshold or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="qi_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        if position.side == -1:
            if qi >= self.short_exit_threshold or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="qi_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "hold_position", price=snapshot.mid_price)