from typing import Optional

from src.features import QueueDynamicsFeatures, compute_queue_dynamics
from src.models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class ObserverStrategy(Strategy):
    """
    Feature-only strategy.

    It never trades.
    It computes and prints queue-dynamics features so you can inspect:
    - spread
    - imbalance
    - same-level bid/ask velocity
    - same-level bid/ask acceleration
    - bid/ask depletion
    - bid/ask price changes

    Useful for tuning thresholds before using a real trading strategy.
    """

    def __init__(
        self,
        print_every_update: bool = True,
        only_print_when_interesting: bool = True,
    ):
        self.print_every_update = print_every_update
        self.only_print_when_interesting = only_print_when_interesting

        self.prev_snapshot: Optional[BookSnapshot] = None
        self.prev_features: Optional[QueueDynamicsFeatures] = None

    def _is_interesting(self, features: QueueDynamicsFeatures) -> bool:
        if features.bid_price_changed or features.ask_price_changed:
            return True

        if features.bid_depletion or features.ask_depletion:
            return True

        if features.bid_velocity_per_ns not in (None, 0.0):
            return True

        if features.ask_velocity_per_ns not in (None, 0.0):
            return True

        if features.bid_acceleration_per_ns2 not in (None, 0.0):
            return True

        if features.ask_acceleration_per_ns2 not in (None, 0.0):
            return True

        return False

    def _print_features(self, features: QueueDynamicsFeatures):
        print(
            "FEATURES",
            {
                "timestamp_ns": features.timestamp_ns,
                "dt_ns": features.dt_ns,
                "best_bid": features.best_bid,
                "best_bid_size": features.best_bid_size,
                "best_ask": features.best_ask,
                "best_ask_size": features.best_ask_size,
                "spread": features.spread,
                "imbalance": features.imbalance,
                "bid_price_changed": features.bid_price_changed,
                "ask_price_changed": features.ask_price_changed,
                "bid_size_delta": features.bid_size_delta,
                "ask_size_delta": features.ask_size_delta,
                "bid_velocity_per_ns": features.bid_velocity_per_ns,
                "ask_velocity_per_ns": features.ask_velocity_per_ns,
                "bid_acceleration_per_ns2": features.bid_acceleration_per_ns2,
                "ask_acceleration_per_ns2": features.ask_acceleration_per_ns2,
                "bid_depletion": features.bid_depletion,
                "ask_depletion": features.ask_depletion,
                "bid_depletion_ratio": features.bid_depletion_ratio,
                "ask_depletion_ratio": features.ask_depletion_ratio,
            },
        )

    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        features = compute_queue_dynamics(snapshot, self.prev_snapshot, self.prev_features)

        should_print = self.print_every_update
        if self.only_print_when_interesting:
            should_print = should_print and self._is_interesting(features)

        if should_print:
            self._print_features(features)

        self.prev_snapshot = snapshot
        self.prev_features = features

        return Signal(
            timestamp_ns=snapshot.timestamp_ns,
            action="HOLD",
            reason="observer_only",
            price=snapshot.mid_price,
            metadata={
                "spread": features.spread,
                "imbalance": features.imbalance,
                "bid_velocity_per_ns": features.bid_velocity_per_ns,
                "ask_velocity_per_ns": features.ask_velocity_per_ns,
                "bid_acceleration_per_ns2": features.bid_acceleration_per_ns2,
                "ask_acceleration_per_ns2": features.ask_acceleration_per_ns2,
                "bid_depletion": features.bid_depletion,
                "ask_depletion": features.ask_depletion,
            },
        )