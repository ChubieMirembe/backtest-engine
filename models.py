from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class Order:
    side: str
    price: float
    shares: int


@dataclass
class BookSnapshot:
    timestamp_ns: int
    best_bid: Optional[float]
    best_ask: Optional[float]
    bid_levels: Dict[float, int]
    ask_levels: Dict[float, int]
    orders: Dict[int, Order]


@dataclass
class Signal:
    timestamp_ns: int
    action: str
    reason: str
    price: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fill:
    timestamp_ns: int
    action: str
    price: float
    reason: str


@dataclass
class PositionState:
    side: int = 0
    entry_price: Optional[float] = None
    entry_timestamp_ns: Optional[int] = None