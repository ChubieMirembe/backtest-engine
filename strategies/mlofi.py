from src.models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class MLOFIStrategy(Strategy):
    """
    Multi-Level OFI using the first N bid/ask levels from BookSnapshot.

    Approximates OFI at each level from aggregated level sizes across snapshots,
    then takes a weighted sum.

    This is not order-ID level MLOFI, but it is a useful depth-aware approximation
    that works with your current snapshot interface.
    """

    def __init__(
        self,
        quantity: int = 1,
        levels: int = 3,
        weights: list[float] | None = None,
        max_spread: float = 0.50,
        long_threshold: float = 100.0,
        short_threshold: float = -100.0,
        exit_band: float = 20.0,
        max_holding_time_ns: int | None = None,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.levels = levels
        self.weights = weights if weights is not None else [1.0 / (i + 1) for i in range(levels)]
        self.max_spread = max_spread
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.exit_band = exit_band
        self.max_holding_time_ns = max_holding_time_ns
        self.debug = debug

        self.prev_snapshot: BookSnapshot | None = None

    def _log(self, payload):
        if self.debug:
            print("MLOFI_DEBUG", payload)

    def _holding_time_expired(self, snapshot: BookSnapshot, position: PositionState) -> bool:
        if (
            self.max_holding_time_ns is None
            or position.entry_timestamp_ns is None
            or position.is_flat
        ):
            return False
        return (snapshot.timestamp_ns - position.entry_timestamp_ns) >= self.max_holding_time_ns

    def _top_bid_levels(self, snapshot: BookSnapshot) -> list[tuple[float, int]]:
        return sorted(snapshot.bid_levels.items(), key=lambda x: x[0], reverse=True)[: self.levels]

    def _top_ask_levels(self, snapshot: BookSnapshot) -> list[tuple[float, int]]:
        return sorted(snapshot.ask_levels.items(), key=lambda x: x[0])[: self.levels]

    def _level_ofi(self, curr_levels: list[tuple[float, int]], prev_levels: list[tuple[float, int]], is_bid: bool) -> list[float]:
        curr_map = {p: q for p, q in curr_levels}
        prev_map = {p: q for p, q in prev_levels}
        all_prices = sorted(set(curr_map.keys()) | set(prev_map.keys()), reverse=is_bid)

        out = []
        for price in all_prices[: self.levels]:
            curr_q = curr_map.get(price, 0)
            prev_q = prev_map.get(price, 0)
            out.append(float(curr_q - prev_q))
        while len(out) < self.levels:
            out.append(0.0)
        return out[: self.levels]

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

        curr_bid_levels = self._top_bid_levels(snapshot)
        prev_bid_levels = self._top_bid_levels(self.prev_snapshot)
        curr_ask_levels = self._top_ask_levels(snapshot)
        prev_ask_levels = self._top_ask_levels(self.prev_snapshot)

        bid_ofi = self._level_ofi(curr_bid_levels, prev_bid_levels, is_bid=True)
        ask_ofi = self._level_ofi(curr_ask_levels, prev_ask_levels, is_bid=False)

        weighted_ofi = 0.0
        for i in range(self.levels):
            weighted_ofi += self.weights[i] * bid_ofi[i]
            weighted_ofi -= self.weights[i] * ask_ofi[i]

        self._log(
            {
                "timestamp_ns": snapshot.timestamp_ns,
                "weighted_ofi": weighted_ofi,
                "bid_ofi": bid_ofi,
                "ask_ofi": ask_ofi,
                "spread": snapshot.spread,
            }
        )

        self.prev_snapshot = snapshot

        if snapshot.spread > self.max_spread:
            if position.side == 1:
                return Signal(snapshot.timestamp_ns, "EXIT_LONG", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            if position.side == -1:
                return Signal(snapshot.timestamp_ns, "EXIT_SHORT", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            return Signal(snapshot.timestamp_ns, "HOLD", "spread_too_wide", price=snapshot.mid_price)

        if position.is_flat:
            if weighted_ofi >= self.long_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="mlofi_long",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"weighted_ofi": weighted_ofi},
                )

            if weighted_ofi <= self.short_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="mlofi_short",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"weighted_ofi": weighted_ofi},
                )

            return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=snapshot.mid_price)

        if position.side == 1:
            if weighted_ofi <= self.exit_band or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="mlofi_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        if position.side == -1:
            if weighted_ofi >= -self.exit_band or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="mlofi_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "hold_position", price=snapshot.mid_price)