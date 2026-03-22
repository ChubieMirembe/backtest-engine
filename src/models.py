from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


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

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid is None or self.best_ask is None:
            return None
        return (self.best_bid + self.best_ask) / 2.0

    @property
    def spread(self) -> Optional[float]:
        if self.best_bid is None or self.best_ask is None:
            return None
        return self.best_ask - self.best_bid

    @property
    def best_bid_size(self) -> int:
        if self.best_bid is None:
            return 0
        return self.bid_levels.get(self.best_bid, 0)

    @property
    def best_ask_size(self) -> int:
        if self.best_ask is None:
            return 0
        return self.ask_levels.get(self.best_ask, 0)

    @property
    def imbalance(self) -> Optional[float]:
        bid_size = self.best_bid_size
        ask_size = self.best_ask_size
        total = bid_size + ask_size
        if total == 0:
            return None
        return (bid_size - ask_size) / total


@dataclass
class Signal:
    timestamp_ns: int
    action: str
    reason: str
    price: Optional[float] = None
    quantity: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fill:
    timestamp_ns: int
    action: str
    price: float
    quantity: int
    reason: str
    fees: float = 0.0
    slippage: float = 0.0
    pnl_after_fill: float = 0.0


@dataclass
class TradeRecord:
    entry_timestamp_ns: int
    exit_timestamp_ns: int
    side: int
    quantity: int
    entry_price: float
    exit_price: float
    gross_pnl: float
    net_pnl: float
    fees: float
    slippage: float
    holding_time_ns: int
    entry_reason: str
    exit_reason: str


@dataclass
class PositionState:
    side: int = 0
    quantity: int = 0
    entry_price: Optional[float] = None
    entry_timestamp_ns: Optional[int] = None
    entry_reason: Optional[str] = None
    entry_fees: float = 0.0
    entry_slippage: float = 0.0

    @property
    def is_flat(self) -> bool:
        return self.side == 0 or self.quantity == 0

    @property
    def signed_quantity(self) -> int:
        return self.side * self.quantity


@dataclass
class PnLState:
    gross_realized_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    total_fees: float = 0.0
    total_slippage: float = 0.0


@dataclass
class PerformanceMetrics:
    entries: int = 0
    exits: int = 0
    round_trips: int = 0
    wins: int = 0
    losses: int = 0
    breakeven_trades: int = 0

    gross_profit: float = 0.0
    gross_loss: float = 0.0

    max_win: float = 0.0
    max_loss: float = 0.0

    exposure_events: int = 0
    holding_time_ns_total: int = 0

    equity_peak: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0

    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)