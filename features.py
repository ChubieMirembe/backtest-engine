from dataclasses import dataclass
from typing import Optional

from models import BookSnapshot


@dataclass
class QueueDynamicsFeatures:
    timestamp_ns: int
    dt_ns: Optional[int]

    best_bid: Optional[float]
    best_ask: Optional[float]
    best_bid_size: int
    best_ask_size: int

    spread: Optional[float]
    imbalance: Optional[float]

    bid_price_changed: bool
    ask_price_changed: bool

    bid_velocity_per_ns: Optional[float]
    ask_velocity_per_ns: Optional[float]

    bid_acceleration_per_ns2: Optional[float]
    ask_acceleration_per_ns2: Optional[float]

    bid_size_delta: Optional[int]
    ask_size_delta: Optional[int]

    bid_depletion: bool
    ask_depletion: bool

    bid_depletion_ratio: Optional[float]
    ask_depletion_ratio: Optional[float]


def compute_queue_dynamics(
    current: BookSnapshot,
    previous: Optional[BookSnapshot],
    previous_features: Optional[QueueDynamicsFeatures],
) -> QueueDynamicsFeatures:
    dt_ns = None
    if previous is not None:
        dt_ns = current.timestamp_ns - previous.timestamp_ns

    best_bid = current.best_bid
    best_ask = current.best_ask
    best_bid_size = current.best_bid_size
    best_ask_size = current.best_ask_size
    spread = current.spread
    imbalance = current.imbalance

    if previous is None:
        return QueueDynamicsFeatures(
            timestamp_ns=current.timestamp_ns,
            dt_ns=None,
            best_bid=best_bid,
            best_ask=best_ask,
            best_bid_size=best_bid_size,
            best_ask_size=best_ask_size,
            spread=spread,
            imbalance=imbalance,
            bid_price_changed=False,
            ask_price_changed=False,
            bid_velocity_per_ns=None,
            ask_velocity_per_ns=None,
            bid_acceleration_per_ns2=None,
            ask_acceleration_per_ns2=None,
            bid_size_delta=None,
            ask_size_delta=None,
            bid_depletion=False,
            ask_depletion=False,
            bid_depletion_ratio=None,
            ask_depletion_ratio=None,
        )

    prev_best_bid = previous.best_bid
    prev_best_ask = previous.best_ask
    prev_best_bid_size = previous.best_bid_size
    prev_best_ask_size = previous.best_ask_size

    bid_price_changed = best_bid != prev_best_bid
    ask_price_changed = best_ask != prev_best_ask

    bid_size_delta = None
    ask_size_delta = None
    bid_velocity_per_ns = None
    ask_velocity_per_ns = None
    bid_acceleration_per_ns2 = None
    ask_acceleration_per_ns2 = None

    if dt_ns is not None and dt_ns > 0:
        if not bid_price_changed:
            bid_size_delta = best_bid_size - prev_best_bid_size
            bid_velocity_per_ns = bid_size_delta / dt_ns

        if not ask_price_changed:
            ask_size_delta = best_ask_size - prev_best_ask_size
            ask_velocity_per_ns = ask_size_delta / dt_ns

        if (
            previous_features is not None
            and bid_velocity_per_ns is not None
            and previous_features.bid_velocity_per_ns is not None
        ):
            bid_acceleration_per_ns2 = (
                bid_velocity_per_ns - previous_features.bid_velocity_per_ns
            ) / dt_ns

        if (
            previous_features is not None
            and ask_velocity_per_ns is not None
            and previous_features.ask_velocity_per_ns is not None
        ):
            ask_acceleration_per_ns2 = (
                ask_velocity_per_ns - previous_features.ask_velocity_per_ns
            ) / dt_ns

    bid_depletion = False
    ask_depletion = False
    bid_depletion_ratio = None
    ask_depletion_ratio = None

    # Bid depletion (bearish): best bid price drops, or same best bid size shrinks.
    if prev_best_bid is not None:
        if best_bid is None:
            bid_depletion = True
        elif best_bid < prev_best_bid:
            bid_depletion = True
        elif not bid_price_changed and prev_best_bid_size > 0 and best_bid_size < prev_best_bid_size:
            bid_depletion = True
            bid_depletion_ratio = (prev_best_bid_size - best_bid_size) / prev_best_bid_size

    # Ask depletion (bullish): best ask price rises, or same best ask size shrinks.
    if prev_best_ask is not None:
        if best_ask is None:
            ask_depletion = True
        elif best_ask > prev_best_ask:
            ask_depletion = True
        elif not ask_price_changed and prev_best_ask_size > 0 and best_ask_size < prev_best_ask_size:
            ask_depletion = True
            ask_depletion_ratio = (prev_best_ask_size - best_ask_size) / prev_best_ask_size

    return QueueDynamicsFeatures(
        timestamp_ns=current.timestamp_ns,
        dt_ns=dt_ns,
        best_bid=best_bid,
        best_ask=best_ask,
        best_bid_size=best_bid_size,
        best_ask_size=best_ask_size,
        spread=spread,
        imbalance=imbalance,
        bid_price_changed=bid_price_changed,
        ask_price_changed=ask_price_changed,
        bid_velocity_per_ns=bid_velocity_per_ns,
        ask_velocity_per_ns=ask_velocity_per_ns,
        bid_acceleration_per_ns2=bid_acceleration_per_ns2,
        ask_acceleration_per_ns2=ask_acceleration_per_ns2,
        bid_size_delta=bid_size_delta,
        ask_size_delta=ask_size_delta,
        bid_depletion=bid_depletion,
        ask_depletion=ask_depletion,
        bid_depletion_ratio=bid_depletion_ratio,
        ask_depletion_ratio=ask_depletion_ratio,
    )