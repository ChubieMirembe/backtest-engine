from collections import deque

from src.models import BookSnapshot, PositionState, Signal
from strategies.base import Strategy


class OFIPersistenceStrategy(Strategy):
    """
    Simple order-flow persistence using signed top-of-book events.

    Instead of full Hawkes modelling, track recent buy/sell pressure counts.

    We infer event direction from top-of-book state changes:

    bullish contribution:
        - best bid price rises
        - best ask price rises
        - best bid size increases at same price
        - best ask size decreases at same price

    bearish contribution:
        - best bid price falls
        - best ask price falls
        - best bid size decreases at same price
        - best ask size increases at same price
    """

    def __init__(
        self,
        quantity: int = 1,
        max_spread: float = 0.50,
        window_size: int = 20,
        long_threshold: int = 5,
        short_threshold: int = -5,
        exit_band: int = 1,
        max_holding_time_ns: int | None = None,
        debug: bool = False,
    ):
        self.quantity = quantity
        self.max_spread = max_spread
        self.window_size = window_size
        self.long_threshold = long_threshold
        self.short_threshold = short_threshold
        self.exit_band = exit_band
        self.max_holding_time_ns = max_holding_time_ns
        self.debug = debug

        self.prev_snapshot: BookSnapshot | None = None
        self.flow_window = deque(maxlen=window_size)

    def _log(self, payload):
        if self.debug:
            print("OFI_PERSIST_DEBUG", payload)

    def _holding_time_expired(self, snapshot: BookSnapshot, position: PositionState) -> bool:
        if (
            self.max_holding_time_ns is None
            or position.entry_timestamp_ns is None
            or position.is_flat
        ):
            return False
        return (snapshot.timestamp_ns - position.entry_timestamp_ns) >= self.max_holding_time_ns

    def _event_score(self, current: BookSnapshot, prev: BookSnapshot) -> int:
        score = 0

        if current.best_bid is not None and prev.best_bid is not None:
            if current.best_bid > prev.best_bid:
                score += 1
            elif current.best_bid < prev.best_bid:
                score -= 1
            else:
                if current.best_bid_size > prev.best_bid_size:
                    score += 1
                elif current.best_bid_size < prev.best_bid_size:
                    score -= 1

        if current.best_ask is not None and prev.best_ask is not None:
            if current.best_ask > prev.best_ask:
                score += 1
            elif current.best_ask < prev.best_ask:
                score -= 1
            else:
                if current.best_ask_size < prev.best_ask_size:
                    score += 1
                elif current.best_ask_size > prev.best_ask_size:
                    score -= 1

        return score

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

        score = self._event_score(snapshot, self.prev_snapshot)
        self.flow_window.append(score)
        persistence_signal = sum(self.flow_window)

        self._log(
            {
                "timestamp_ns": snapshot.timestamp_ns,
                "event_score": score,
                "persistence_signal": persistence_signal,
                "spread": snapshot.spread,
                "window_size": len(self.flow_window),
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
            if persistence_signal >= self.long_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="BUY",
                    reason="ofi_persistence_long",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"persistence_signal": persistence_signal},
                )

            if persistence_signal <= self.short_threshold:
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="SELL",
                    reason="ofi_persistence_short",
                    price=snapshot.mid_price,
                    quantity=self.quantity,
                    metadata={"persistence_signal": persistence_signal},
                )

            return Signal(snapshot.timestamp_ns, "HOLD", "no_action", price=snapshot.mid_price)

        if position.side == 1:
            if persistence_signal <= self.exit_band or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_LONG",
                    reason="ofi_persistence_exit_long",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        if position.side == -1:
            if persistence_signal >= -self.exit_band or self._holding_time_expired(snapshot, position):
                return Signal(
                    timestamp_ns=snapshot.timestamp_ns,
                    action="EXIT_SHORT",
                    reason="ofi_persistence_exit_short",
                    price=snapshot.mid_price,
                    quantity=position.quantity,
                )

        return Signal(snapshot.timestamp_ns, "HOLD", "hold_position", price=snapshot.mid_price)