from dataclasses import dataclass
from typing import Optional

from models import PositionState, Signal, Fill, TradeRecord, PnLState


@dataclass
class ExecutionConfig:
    trade_quantity: int
    fee_per_trade: float
    slippage_bps: float


class ExecutionSimulator:
    def __init__(self, config: ExecutionConfig):
        self.config = config

    def apply_slippage(self, price: float, action: str) -> float:
        slippage_fraction = self.config.slippage_bps / 10000.0

        if action in ("BUY", "EXIT_SHORT"):
            return price * (1.0 + slippage_fraction)

        if action in ("SELL", "EXIT_LONG"):
            return price * (1.0 - slippage_fraction)

        return price

    def slippage_cost(
        self,
        raw_price: float,
        slipped_price: float,
        quantity: int,
        action: str,
    ) -> float:
        if action in ("BUY", "EXIT_SHORT"):
            return (slipped_price - raw_price) * quantity

        if action in ("SELL", "EXIT_LONG"):
            return (raw_price - slipped_price) * quantity

        return 0.0

    def build_entry_fill(
        self,
        signal: Signal,
        price: float,
        quantity: int,
        pnl_after_fill: float,
        fee_cost: float,
        slippage_cost: float,
    ) -> Fill:
        return Fill(
            timestamp_ns=signal.timestamp_ns,
            action=signal.action,
            price=price,
            quantity=quantity,
            reason=signal.reason,
            fees=fee_cost,
            slippage=slippage_cost,
            pnl_after_fill=pnl_after_fill,
        )

    def build_exit_fill(
        self,
        signal: Signal,
        price: float,
        quantity: int,
        pnl_after_fill: float,
        fee_cost: float,
        slippage_cost: float,
    ) -> Fill:
        return Fill(
            timestamp_ns=signal.timestamp_ns,
            action=signal.action,
            price=price,
            quantity=quantity,
            reason=signal.reason,
            fees=fee_cost,
            slippage=slippage_cost,
            pnl_after_fill=pnl_after_fill,
        )

    def mark_to_market(
        self,
        position: PositionState,
        best_bid: Optional[float],
        best_ask: Optional[float],
    ) -> Optional[float]:
        if position.is_flat or position.entry_price is None:
            return 0.0

        if best_bid is None or best_ask is None:
            return None

        mid = (best_bid + best_ask) / 2.0

        if position.side == 1:
            return (mid - position.entry_price) * position.quantity

        if position.side == -1:
            return (position.entry_price - mid) * position.quantity

        return None

    def build_trade_record(
        self,
        position: PositionState,
        exit_timestamp_ns: int,
        exit_price: float,
        exit_reason: str,
        exit_fees: float,
        exit_slippage: float,
    ) -> Optional[TradeRecord]:
        if (
            position.entry_price is None
            or position.entry_timestamp_ns is None
            or position.quantity <= 0
            or position.side == 0
        ):
            return None

        if position.side == 1:
            gross_pnl = (exit_price - position.entry_price) * position.quantity
        else:
            gross_pnl = (position.entry_price - exit_price) * position.quantity

        total_fees = position.entry_fees + exit_fees
        total_slippage = position.entry_slippage + exit_slippage
        net_pnl = gross_pnl - total_fees
        holding_time_ns = exit_timestamp_ns - position.entry_timestamp_ns

        return TradeRecord(
            entry_timestamp_ns=position.entry_timestamp_ns,
            exit_timestamp_ns=exit_timestamp_ns,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            gross_pnl=gross_pnl,
            net_pnl=net_pnl,
            fees=total_fees,
            slippage=total_slippage,
            holding_time_ns=holding_time_ns,
            entry_reason=position.entry_reason or "",
            exit_reason=exit_reason,
        )