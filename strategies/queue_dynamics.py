from typing import Optional

from features import QueueDynamicsFeatures, compute_queue_dynamics
from models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class QueueDynamicsStrategy(Strategy):
    """
    Uses:
    - same-level queue velocity
    - same-level queue acceleration
    - top-of-book depletion flags

    Long bias:
    - ask gets depleted (bullish)
    - bid queue is strengthening
    - imbalance is supportive
    - spread is not too wide

    Short bias:
    - bid gets depleted (bearish)
    - ask queue is strengthening / bid queue is weakening
    - imbalance is supportive
    - spread is not too wide
    """

    def __init__(
        self,
        quantity: int = 1,
        max_spread: float = 0.50,
        min_imbalance: float = 0.10,
        min_bid_velocity_per_ns: float = 0.0,
        min_ask_velocity_per_ns: float = 0.0,
        min_bid_acceleration_per_ns2: float = 0.0,
        min_ask_acceleration_per_ns2: float = 0.0,
        min_depletion_ratio: float = 0.10,
        max_holding_time_ns: Optional[int] = None,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.max_spread = max_spread
        self.min_imbalance = min_imbalance
        self.min_bid_velocity_per_ns = min_bid_velocity_per_ns
        self.min_ask_velocity_per_ns = min_ask_velocity_per_ns
        self.min_bid_acceleration_per_ns2 = min_bid_acceleration_per_ns2
        self.min_ask_acceleration_per_ns2 = min_ask_acceleration_per_ns2
        self.min_depletion_ratio = min_depletion_ratio
        self.max_holding_time_ns = max_holding_time_ns
        self.debug = debug

        self.prev_snapshot: Optional[BookSnapshot] = None
        self.prev_features: Optional[QueueDynamicsFeatures] = None

    def _holding_time_expired(self, snapshot: BookSnapshot, position: PositionState) -> bool:
        if (
            self.max_holding_time_ns is None
            or position.entry_timestamp_ns is None
            or position.is_flat
        ):
            return False
        return (snapshot.timestamp_ns - position.entry_timestamp_ns) >= self.max_holding_time_ns

    def _log(self, features: QueueDynamicsFeatures):
        if self.debug:
            print("FEATURES", features)

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        features = compute_queue_dynamics(snapshot, self.prev_snapshot, self.prev_features)
        self._log(features)

        self.prev_snapshot = snapshot
        self.prev_features = features

        if snapshot.best_bid is None or snapshot.best_ask is None or snapshot.mid_price is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        if features.spread is None or features.imbalance is None:
            return Signal(snapshot.timestamp_ns, "HOLD", "missing_features", price=snapshot.mid_price)

        if features.spread > self.max_spread:
            return Signal(snapshot.timestamp_ns, "HOLD", "spread_too_wide", price=snapshot.mid_price)

        if features.dt_ns is None or features.dt_ns <= 0:
            return Signal(snapshot.timestamp_ns, "HOLD", "insufficient_history", price=snapshot.mid_price)

        ask_depletion_strong = (
            features.ask_depletion
            and (
                features.ask_depletion_ratio is None
                or features.ask_depletion_ratio >= self.min_depletion_ratio
                or features.ask_price_changed
            )
        )

        bid_depletion_strong = (
            features.bid_depletion
            and (
                features.bid_depletion_ratio is None
                or features.bid_depletion_ratio >= self.min_depletion_ratio
                or features.bid_price_changed
            )
        )

        long_setup = (
            ask_depletion_strong
            and features.imbalance >= self.min_imbalance
            and (
                (features.bid_velocity_per_ns is not None and features.bid_velocity_per_ns > self.min_bid_velocity_per_ns)
                or (features.bid_acceleration_per_ns2 is not None and features.bid_acceleration_per_ns2 > self.min_bid_acceleration_per_ns2)
            )
        )

        short_setup = (
            bid_depletion_strong
            and features.imbalance <= -self.min_imbalance
            and (
                (features.ask_velocity_per_ns is not None and features.ask_velocity_per_ns > self.min_ask_velocity_per_ns)
                or (features.ask_acceleration_per_ns2 is not None and features.ask_acceleration_per_ns2 > self.min_ask_acceleration_per_ns2)
            )
        )

        if position.is_flat:
            if long_setup:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="queue_dynamics_long",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={
                        "imbalance": features.imbalance,
                        "spread": features.spread,
                        "ask_depletion": features.ask_depletion,
                        "bid_velocity_per_ns": features.bid_velocity_per_ns,
                        "bid_acceleration_per_ns2": features.bid_acceleration_per_ns2,
                    },
                )

            if short_setup:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="queue_dynamics_short",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={
                        "imbalance": features.imbalance,
                        "spread": features.spread,
                        "bid_depletion": features.bid_depletion,
                        "ask_velocity_per_ns": features.ask_velocity_per_ns,
                        "ask_acceleration_per_ns2": features.ask_acceleration_per_ns2,
                    },
                )

            return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=snapshot.mid_price)

        if position.side == 1:
            opposite_short = short_setup
            long_support_broken = (
                bid_depletion_strong
                or features.imbalance < 0
                or self._holding_time_expired(snapshot, position)
            )

            if opposite_short or long_support_broken:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="queue_dynamics_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        if position.side == -1:
            opposite_long = long_setup
            short_support_broken = (
                ask_depletion_strong
                or features.imbalance > 0
                or self._holding_time_expired(snapshot, position)
            )

            if opposite_long or short_support_broken:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="queue_dynamics_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "hold_position", price=snapshot.mid_price)