from typing import Optional

from models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class DepletionStrategy(Strategy):
    def __init__(
        self,
        quantity: int = 1,
        max_spread: float = 0.50,
        min_imbalance_long: float = 0.20,
        max_imbalance_short: float = -0.20,
        min_depletion_ratio: float = 0.10,
        thin_ask_threshold: int = 10,
        thin_bid_threshold: int = 10,
        persistence_required: int = 2,
        max_holding_time_ns: Optional[int] = None,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.max_spread = max_spread
        self.min_imbalance_long = min_imbalance_long
        self.max_imbalance_short = max_imbalance_short
        self.min_depletion_ratio = min_depletion_ratio
        self.thin_ask_threshold = thin_ask_threshold
        self.thin_bid_threshold = thin_bid_threshold
        self.persistence_required = persistence_required
        self.max_holding_time_ns = max_holding_time_ns
        self.debug = debug

        self.prev_snapshot: Optional[BookSnapshot] = None
        self.long_setup_streak = 0
        self.short_setup_streak = 0

    def _log(self, payload):
        if self.debug:
            print("DEPLETION_DEBUG", payload)

    def _holding_time_expired(self, snapshot: BookSnapshot, position: PositionState) -> bool:
        if (
            self.max_holding_time_ns is None
            or position.entry_timestamp_ns is None
            or position.is_flat
        ):
            return False
        return (snapshot.timestamp_ns - position.entry_timestamp_ns) >= self.max_holding_time_ns

    def _same_level_ask_depletion(self, snapshot: BookSnapshot, prev_snapshot: Optional[BookSnapshot]):
        if prev_snapshot is None:
            return False, None
        if snapshot.best_ask is None or prev_snapshot.best_ask is None:
            return False, None
        if snapshot.best_ask != prev_snapshot.best_ask:
            return False, None

        prev_size = prev_snapshot.best_ask_size
        curr_size = snapshot.best_ask_size
        if prev_size <= 0:
            return False, None
        if curr_size < prev_size:
            ratio = (prev_size - curr_size) / prev_size
            return True, ratio
        return False, None

    def _same_level_bid_depletion(self, snapshot: BookSnapshot, prev_snapshot: Optional[BookSnapshot]):
        if prev_snapshot is None:
            return False, None
        if snapshot.best_bid is None or prev_snapshot.best_bid is None:
            return False, None
        if snapshot.best_bid != prev_snapshot.best_bid:
            return False, None

        prev_size = prev_snapshot.best_bid_size
        curr_size = snapshot.best_bid_size
        if prev_size <= 0:
            return False, None
        if curr_size < prev_size:
            ratio = (prev_size - curr_size) / prev_size
            return True, ratio
        return False, None

    def _ask_thin(self, snapshot: BookSnapshot) -> bool:
        return snapshot.best_ask is not None and snapshot.best_ask_size <= self.thin_ask_threshold

    def _bid_thin(self, snapshot: BookSnapshot) -> bool:
        return snapshot.best_bid is not None and snapshot.best_bid_size <= self.thin_bid_threshold

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        if snapshot.best_bid is None or snapshot.best_ask is None or snapshot.mid_price is None:
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        spread = snapshot.spread
        imbalance = snapshot.imbalance

        if spread is None or imbalance is None:
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "missing_features", price=snapshot.mid_price)

        same_ask_dep, ask_dep_ratio = self._same_level_ask_depletion(snapshot, self.prev_snapshot)
        same_bid_dep, bid_dep_ratio = self._same_level_bid_depletion(snapshot, self.prev_snapshot)

        ask_thin = self._ask_thin(snapshot)
        bid_thin = self._bid_thin(snapshot)

        long_setup = (
            spread <= self.max_spread
            and imbalance >= self.min_imbalance_long
            and (
                ask_thin
                or (same_ask_dep and ask_dep_ratio is not None and ask_dep_ratio >= self.min_depletion_ratio)
            )
        )

        short_setup = (
            spread <= self.max_spread
            and imbalance <= self.max_imbalance_short
            and (
                bid_thin
                or (same_bid_dep and bid_dep_ratio is not None and bid_dep_ratio >= self.min_depletion_ratio)
            )
        )

        self.long_setup_streak = self.long_setup_streak + 1 if long_setup else 0
        self.short_setup_streak = self.short_setup_streak + 1 if short_setup else 0

        self._log(
            {
                "timestamp_ns": snapshot.timestamp_ns,
                "spread": spread,
                "imbalance": imbalance,
                "ask_thin": ask_thin,
                "bid_thin": bid_thin,
                "same_ask_dep": same_ask_dep,
                "ask_dep_ratio": ask_dep_ratio,
                "same_bid_dep": same_bid_dep,
                "bid_dep_ratio": bid_dep_ratio,
                "long_streak": self.long_setup_streak,
                "short_streak": self.short_setup_streak,
            }
        )

        if position.is_flat:
            if self.long_setup_streak >= self.persistence_required:
                self.prev_snapshot = snapshot
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="depletion_long",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                )

            if self.short_setup_streak >= self.persistence_required:
                self.prev_snapshot = snapshot
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="depletion_short",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                )

        elif position.side == 1:
            if (
                spread > self.max_spread
                or imbalance < 0
                or (same_bid_dep and bid_dep_ratio is not None and bid_dep_ratio >= self.min_depletion_ratio)
                or self._holding_time_expired(snapshot, position)
            ):
                self.prev_snapshot = snapshot
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="depletion_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        elif position.side == -1:
            if (
                spread > self.max_spread
                or imbalance > 0
                or (same_ask_dep and ask_dep_ratio is not None and ask_dep_ratio >= self.min_depletion_ratio)
                or self._holding_time_expired(snapshot, position)
            ):
                self.prev_snapshot = snapshot
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="depletion_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        self.prev_snapshot = snapshot
        return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=snapshot.mid_price)