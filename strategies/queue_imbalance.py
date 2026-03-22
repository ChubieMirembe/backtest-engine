from src.models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class QueueImbalanceStrategy(Strategy):
    """
    Queue Imbalance (QI)

    QI = (Q_bid - Q_ask) / (Q_bid + Q_ask)

    Improvements over the simple version:
    - Enter only on threshold CROSS, not while QI merely remains above/below threshold
    - Require a RESET before the same-side signal can arm again
    - Optional long-only / short-only mode

    Long entry:
        prev_qi < long_threshold
        and qi >= long_threshold
        and long side is armed
        and spread <= max_spread

    Long re-arm:
        after a long entry/exit, long side only becomes armed again when
        qi <= long_reset_threshold

    Short entry:
        prev_qi > short_threshold
        and qi <= short_threshold
        and short side is armed
        and spread <= max_spread

    Short re-arm:
        after a short entry/exit, short side only becomes armed again when
        qi >= short_reset_threshold

    Long exit:
        qi <= long_exit_threshold
        or spread widens too much
        or max holding time reached

    Short exit:
        qi >= short_exit_threshold
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
        long_reset_threshold: float = 0.20,
        short_reset_threshold: float = -0.20,
        max_holding_time_ns: int | None = None,
        allow_long: bool = True,
        allow_short: bool = True,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.max_spread = max_spread
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.long_exit_threshold = long_exit_threshold
        self.short_exit_threshold = short_exit_threshold
        self.long_reset_threshold = long_reset_threshold
        self.short_reset_threshold = short_reset_threshold
        self.max_holding_time_ns = max_holding_time_ns
        self.allow_long = allow_long
        self.allow_short = allow_short
        self.debug = debug

        self.prev_qi: float | None = None

        # Armed means allowed to take the next fresh cross in that direction.
        self.long_armed = True
        self.short_armed = True

    def _log(self, payload: dict) -> None:
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

    def _update_arming_state(self, qi: float) -> None:
        """
        Re-arm a side only after QI has reset back through a neutral-ish band.
        This prevents repeated same-side entries in the same stale regime.
        """
        if qi <= self.long_reset_threshold:
            self.long_armed = True

        if qi >= self.short_reset_threshold:
            self.short_armed = True

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        if snapshot.best_bid is None or snapshot.best_ask is None or snapshot.mid_price is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        if snapshot.spread is None or snapshot.imbalance is None:
            return Signal(
                snapshot.timestamp_ns,
                "HOLD",
                "missing_features",
                price=snapshot.mid_price,
            )

        spread = snapshot.spread
        qi = snapshot.imbalance

        # Re-arm logic is based on the latest observed QI state.
        self._update_arming_state(qi)

        self._log(
            {
                "timestamp_ns": snapshot.timestamp_ns,
                "spread": spread,
                "qi": qi,
                "prev_qi": self.prev_qi,
                "best_bid": snapshot.best_bid,
                "best_bid_size": snapshot.best_bid_size,
                "best_ask": snapshot.best_ask,
                "best_ask_size": snapshot.best_ask_size,
                "long_armed": self.long_armed,
                "short_armed": self.short_armed,
                "position_side": position.side,
            }
        )

        # Hard safety exit on bad spread
        if spread > self.max_spread:
            self.prev_qi = qi

            if position.side == 1:
                self.long_armed = False
                return Signal(
                    snapshot.timestamp_ns,
                    "EXIT_LONG",
                    "spread_too_wide",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

            if position.side == -1:
                self.short_armed = False
                return Signal(
                    snapshot.timestamp_ns,
                    "EXIT_SHORT",
                    "spread_too_wide",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

            return Signal(
                snapshot.timestamp_ns,
                "HOLD",
                "spread_too_wide",
                price=snapshot.mid_price,
            )

        # Need previous QI to detect true threshold crossing
        if self.prev_qi is None:
            self.prev_qi = qi
            return Signal(
                snapshot.timestamp_ns,
                "HOLD",
                "insufficient_history",
                price=snapshot.mid_price,
            )

        crossed_long = self.prev_qi < self.long_threshold and qi >= self.long_threshold
        crossed_short = self.prev_qi > self.short_threshold and qi <= self.short_threshold

        if position.is_flat:
            if self.allow_long and self.long_armed and crossed_long:
                self.long_armed = False
                self.prev_qi = qi
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="qi_long_cross",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={
                        "qi": qi,
                        "prev_qi": self.prev_qi,
                        "spread": spread,
                    },
                )

            if self.allow_short and self.short_armed and crossed_short:
                self.short_armed = False
                self.prev_qi = qi
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="qi_short_cross",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={
                        "qi": qi,
                        "prev_qi": self.prev_qi,
                        "spread": spread,
                    },
                )

            self.prev_qi = qi
            return Signal(
                snapshot.timestamp_ns,
                "HOLD",
                "no_action",
                price=snapshot.mid_price,
            )

        if position.side == 1:
            if qi <= self.long_exit_threshold or self._holding_time_expired(snapshot, position):
                self.long_armed = False
                self.prev_qi = qi
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="qi_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        if position.side == -1:
            if qi >= self.short_exit_threshold or self._holding_time_expired(snapshot, position):
                self.short_armed = False
                self.prev_qi = qi
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="qi_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        self.prev_qi = qi
        return Signal(
            snapshot.timestamp_ns,
            "HOLD",
            "hold_position",
            price=snapshot.mid_price,
        )