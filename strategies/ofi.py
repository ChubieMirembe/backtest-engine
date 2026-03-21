from models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class OFIStrategy(Strategy):
    """
    Order Flow Imbalance (OFI), approximated from consecutive top-of-book snapshots.

    For each update:
        e_bid =
            +Q_bid_t      if P_bid_t > P_bid_t-1
            -(Q_bid_t-1)  if P_bid_t < P_bid_t-1
            Q_bid_t - Q_bid_t-1 otherwise

        e_ask =
            -(Q_ask_t)      if P_ask_t < P_ask_t-1
            +(Q_ask_t-1)    if P_ask_t > P_ask_t-1
            -(Q_ask_t - Q_ask_t-1) otherwise

        OFI = e_bid + e_ask

    Long:
        OFI >= long_threshold
        spread <= max_spread

    Short:
        OFI <= short_threshold
        spread <= max_spread
    """

    def __init__(
        self,
        quantity: int = 1,
        max_spread: float = 0.50,
        long_threshold: float = 50.0,
        short_threshold: float = -50.0,
        exit_band: float = 10.0,
        max_holding_time_ns: int | None = None,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.max_spread = max_spread
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.exit_band = exit_band
        self.max_holding_time_ns = max_holding_time_ns
        self.debug = debug

        self.prev_snapshot: BookSnapshot | None = None

    def _log(self, payload):
        if self.debug:
            print("OFI_DEBUG", payload)

    def _holding_time_expired(self, snapshot: BookSnapshot, position: PositionState) -> bool:
        if (
            self.max_holding_time_ns is None
            or position.entry_timestamp_ns is None
            or position.is_flat
        ):
            return False
        return (snapshot.timestamp_ns - position.entry_timestamp_ns) >= self.max_holding_time_ns

    def _compute_ofi(self, current: BookSnapshot, prev: BookSnapshot) -> float:
        e_bid = 0.0
        e_ask = 0.0

        if current.best_bid is not None and prev.best_bid is not None:
            if current.best_bid > prev.best_bid:
                e_bid = float(current.best_bid_size)
            elif current.best_bid < prev.best_bid:
                e_bid = -float(prev.best_bid_size)
            else:
                e_bid = float(current.best_bid_size - prev.best_bid_size)

        if current.best_ask is not None and prev.best_ask is not None:
            if current.best_ask < prev.best_ask:
                e_ask = float(-current.best_ask_size)
            elif current.best_ask > prev.best_ask:
                e_ask = float(prev.best_ask_size)
            else:
                e_ask = float(-(current.best_ask_size - prev.best_ask_size))

        return e_bid + e_ask

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        if snapshot.best_bid is None or snapshot.best_ask is None or snapshot.mid_price is None:
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        if snapshot.spread is None:
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "missing_features", price=snapshot.mid_price)

        if self.prev_snapshot is None:
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "insufficient_history", price=snapshot.mid_price)

        ofi = self._compute_ofi(snapshot, self.prev_snapshot)
        spread = snapshot.spread

        self._log(
            {
                "timestamp_ns": snapshot.timestamp_ns,
                "ofi": ofi,
                "spread": spread,
                "best_bid": snapshot.best_bid,
                "best_bid_size": snapshot.best_bid_size,
                "best_ask": snapshot.best_ask,
                "best_ask_size": snapshot.best_ask_size,
            }
        )

        self.prev_snapshot = snapshot

        if spread > self.max_spread:
            if position.side == 1:
                return Signal(snapshot.timestamp_ns, "EXIT_LONG", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            if position.side == -1:
                return Signal(snapshot.timestamp_ns, "EXIT_SHORT", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            return Signal(snapshot.timestamp_ns, "HOLD", "spread_too_wide", price=snapshot.mid_price)

        if position.is_flat:
            if ofi >= self.long_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="ofi_long",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"ofi": ofi, "spread": spread},
                )

            if ofi <= self.short_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="ofi_short",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"ofi": ofi, "spread": spread},
                )

            return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=snapshot.mid_price)

        if position.side == 1:
            if ofi <= self.exit_band or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="ofi_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        if position.side == -1:
            if ofi >= -self.exit_band or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="ofi_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "hold_position", price=snapshot.mid_price)