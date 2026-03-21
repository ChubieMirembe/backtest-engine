from models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class QueueDynamicsStrategy(Strategy):
    """
    Uses:
    - queue velocity
    - queue acceleration
    - depletion
    computed from consecutive top-of-book states
    """

    def __init__(
        self,
        quantity: int = 1,
        max_spread: float = 0.50,
        min_imbalance: float = 0.10,
        min_depletion_ratio: float = 0.10,
        min_velocity: float = 0.0,
        min_acceleration: float = 0.0,
        exit_imbalance_band: float = 0.0,
        max_holding_time_ns: int | None = None,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.max_spread = max_spread
        self.min_imbalance = min_imbalance
        self.min_depletion_ratio = min_depletion_ratio
        self.min_velocity = min_velocity
        self.min_acceleration = min_acceleration
        self.exit_imbalance_band = exit_imbalance_band
        self.max_holding_time_ns = max_holding_time_ns
        self.debug = debug

        self.prev_snapshot: BookSnapshot | None = None
        self.prev_bid_velocity: float | None = None
        self.prev_ask_velocity: float | None = None

    def _log(self, payload):
        if self.debug:
            print("QUEUE_DYN_DEBUG", payload)

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
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "no_valid_book")

        if snapshot.spread is None or snapshot.imbalance is None:
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "missing_features", price=snapshot.mid_price)

        if self.prev_snapshot is None:
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "insufficient_history", price=snapshot.mid_price)

        dt_ns = snapshot.timestamp_ns - self.prev_snapshot.timestamp_ns
        if dt_ns <= 0:
            self.prev_snapshot = snapshot
            return Signal(snapshot.timestamp_ns, "HOLD", "bad_dt", price=snapshot.mid_price)

        bid_velocity = None
        ask_velocity = None
        bid_acceleration = None
        ask_acceleration = None
        bid_depletion = False
        ask_depletion = False
        bid_dep_ratio = None
        ask_dep_ratio = None

        if snapshot.best_bid == self.prev_snapshot.best_bid:
            prev_bid_size = self.prev_snapshot.best_bid_size
            curr_bid_size = snapshot.best_bid_size
            bid_delta = curr_bid_size - prev_bid_size
            bid_velocity = bid_delta / dt_ns
            if prev_bid_size > 0 and curr_bid_size < prev_bid_size:
                bid_depletion = True
                bid_dep_ratio = (prev_bid_size - curr_bid_size) / prev_bid_size

        elif snapshot.best_bid < self.prev_snapshot.best_bid:
            bid_depletion = True

        if snapshot.best_ask == self.prev_snapshot.best_ask:
            prev_ask_size = self.prev_snapshot.best_ask_size
            curr_ask_size = snapshot.best_ask_size
            ask_delta = curr_ask_size - prev_ask_size
            ask_velocity = ask_delta / dt_ns
            if prev_ask_size > 0 and curr_ask_size < prev_ask_size:
                ask_depletion = True
                ask_dep_ratio = (prev_ask_size - curr_ask_size) / prev_ask_size

        elif snapshot.best_ask > self.prev_snapshot.best_ask:
            ask_depletion = True

        if bid_velocity is not None and self.prev_bid_velocity is not None:
            bid_acceleration = (bid_velocity - self.prev_bid_velocity) / dt_ns

        if ask_velocity is not None and self.prev_ask_velocity is not None:
            ask_acceleration = (ask_velocity - self.prev_ask_velocity) / dt_ns

        self._log(
            {
                "timestamp_ns": snapshot.timestamp_ns,
                "spread": snapshot.spread,
                "imbalance": snapshot.imbalance,
                "bid_velocity": bid_velocity,
                "ask_velocity": ask_velocity,
                "bid_acceleration": bid_acceleration,
                "ask_acceleration": ask_acceleration,
                "bid_depletion": bid_depletion,
                "ask_depletion": ask_depletion,
                "bid_dep_ratio": bid_dep_ratio,
                "ask_dep_ratio": ask_dep_ratio,
            }
        )

        self.prev_snapshot = snapshot
        self.prev_bid_velocity = bid_velocity
        self.prev_ask_velocity = ask_velocity

        if snapshot.spread > self.max_spread:
            if position.side == 1:
                return Signal(snapshot.timestamp_ns, "EXIT_LONG", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            if position.side == -1:
                return Signal(snapshot.timestamp_ns, "EXIT_SHORT", "spread_too_wide", price=snapshot.mid_price, quantity=position.quantity)
            return Signal(snapshot.timestamp_ns, "HOLD", "spread_too_wide", price=snapshot.mid_price)

        long_setup = (
            snapshot.imbalance >= self.min_imbalance
            and (
                (ask_depletion and (ask_dep_ratio is None or ask_dep_ratio >= self.min_depletion_ratio))
                or (bid_velocity is not None and bid_velocity >= self.min_velocity)
                or (bid_acceleration is not None and bid_acceleration >= self.min_acceleration)
            )
        )

        short_setup = (
            snapshot.imbalance <= -self.min_imbalance
            and (
                (bid_depletion and (bid_dep_ratio is None or bid_dep_ratio >= self.min_depletion_ratio))
                or (ask_velocity is not None and ask_velocity >= self.min_velocity)
                or (ask_acceleration is not None and ask_acceleration >= self.min_acceleration)
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
                )

            if short_setup:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="queue_dynamics_short",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                )

            return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=snapshot.mid_price)

        if position.side == 1:
            if snapshot.imbalance <= self.exit_imbalance_band or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="queue_dynamics_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        if position.side == -1:
            if snapshot.imbalance >= -self.exit_imbalance_band or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="queue_dynamics_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "hold_position", price=snapshot.mid_price)