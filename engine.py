from typing import List

from data_loader import ITCHDataLoader
from execution import ExecutionSimulator, ExecutionConfig
from metrics import MetricsTracker
from models import Fill, PositionState, Signal, PnLState, TradeRecord
from order_book import OrderBook
from report import BacktestReporter
from risk import RiskManager, RiskConfig


class BacktestEngine:
    def __init__(
        self,
        file_path: str,
        target_stock: str,
        message_types: bytes,
        strategy,
        max_events: int,
        trade_quantity: int,
        fee_per_trade: float,
        slippage_bps: float,
        allow_shorts: bool,
        max_position_size: int,
        max_notional: float,
        max_trades: int,
        cooldown_ns: int,
        print_every_event: bool = True,
    ):
        self.file_path = file_path
        self.target_stock = target_stock
        self.message_types = message_types
        self.strategy = strategy
        self.max_events = max_events
        self.print_every_event = print_every_event

        self.loader = ITCHDataLoader(file_path=file_path, message_types=message_types)
        self.book = OrderBook(target_stock=target_stock)

        self.execution = ExecutionSimulator(
            ExecutionConfig(
                trade_quantity=trade_quantity,
                fee_per_trade=fee_per_trade,
                slippage_bps=slippage_bps,
            )
        )

        self.risk = RiskManager(
            RiskConfig(
                allow_shorts=allow_shorts,
                max_position_size=max_position_size,
                max_notional=max_notional,
                max_trades=max_trades,
                cooldown_ns=cooldown_ns,
            )
        )

        self.metrics = MetricsTracker()
        self.reporter = BacktestReporter()

        self.position = PositionState()
        self.pnl = PnLState()

        self.fills: List[Fill] = []
        self.trades: List[TradeRecord] = []
        self.events_processed = 0

    def _record_fill(self, fill: Fill):
        self.fills.append(fill)
        self.risk.notify_fill(fill.timestamp_ns)

    def _update_pnl(self, snapshot):
        unrealized = self.execution.mark_to_market(
            self.position,
            snapshot.best_bid,
            snapshot.best_ask,
        )
        self.pnl.unrealized_pnl = 0.0 if unrealized is None else unrealized
        self.pnl.total_pnl = self.pnl.realized_pnl + self.pnl.unrealized_pnl
        self.metrics.on_event_equity(self.pnl.total_pnl, self.position)

    def _execute_signal(self, signal: Signal):
        if signal.price is None:
            return

        qty = signal.quantity if signal.quantity is not None else self.execution.config.trade_quantity
        raw_price = signal.price
        exec_price = self.execution.apply_slippage(raw_price, signal.action)
        slippage_cost = self.execution.slippage_cost(raw_price, exec_price, qty, signal.action)
        fee_cost = self.execution.config.fee_per_trade

        if signal.action == "BUY" and self.position.is_flat:
            self.position.side = 1
            self.position.quantity = qty
            self.position.entry_price = exec_price
            self.position.entry_timestamp_ns = signal.timestamp_ns
            self.position.entry_reason = signal.reason
            self.position.entry_fees = fee_cost
            self.position.entry_slippage = slippage_cost

            self.pnl.total_fees += fee_cost
            self.pnl.total_slippage += slippage_cost
            self.pnl.realized_pnl -= fee_cost

            self.metrics.on_entry()

            fill = self.execution.build_entry_fill(
                signal=signal,
                price=exec_price,
                quantity=qty,
                pnl_after_fill=self.pnl.realized_pnl,
                fee_cost=fee_cost,
                slippage_cost=slippage_cost,
            )
            self._record_fill(fill)

        elif signal.action == "SELL" and self.position.is_flat:
            self.position.side = -1
            self.position.quantity = qty
            self.position.entry_price = exec_price
            self.position.entry_timestamp_ns = signal.timestamp_ns
            self.position.entry_reason = signal.reason
            self.position.entry_fees = fee_cost
            self.position.entry_slippage = slippage_cost

            self.pnl.total_fees += fee_cost
            self.pnl.total_slippage += slippage_cost
            self.pnl.realized_pnl -= fee_cost

            self.metrics.on_entry()

            fill = self.execution.build_entry_fill(
                signal=signal,
                price=exec_price,
                quantity=qty,
                pnl_after_fill=self.pnl.realized_pnl,
                fee_cost=fee_cost,
                slippage_cost=slippage_cost,
            )
            self._record_fill(fill)

        elif signal.action == "EXIT_LONG" and self.position.side == 1:
            gross_pnl = (exec_price - self.position.entry_price) * self.position.quantity
            net_pnl = gross_pnl - fee_cost

            self.pnl.gross_realized_pnl += gross_pnl
            self.pnl.total_fees += fee_cost
            self.pnl.total_slippage += slippage_cost
            self.pnl.realized_pnl += net_pnl

            self.metrics.on_exit()

            fill = self.execution.build_exit_fill(
                signal=signal,
                price=exec_price,
                quantity=self.position.quantity,
                pnl_after_fill=self.pnl.realized_pnl,
                fee_cost=fee_cost,
                slippage_cost=slippage_cost,
            )
            self._record_fill(fill)

            trade = self.execution.build_trade_record(
                position=self.position,
                exit_timestamp_ns=signal.timestamp_ns,
                exit_price=exec_price,
                exit_reason=signal.reason,
                exit_fees=fee_cost,
                exit_slippage=slippage_cost,
            )
            if trade is not None:
                self.trades.append(trade)
                self.metrics.on_trade(trade)

            self.position = PositionState()

        elif signal.action == "EXIT_SHORT" and self.position.side == -1:
            gross_pnl = (self.position.entry_price - exec_price) * self.position.quantity
            net_pnl = gross_pnl - fee_cost

            self.pnl.gross_realized_pnl += gross_pnl
            self.pnl.total_fees += fee_cost
            self.pnl.total_slippage += slippage_cost
            self.pnl.realized_pnl += net_pnl

            self.metrics.on_exit()

            fill = self.execution.build_exit_fill(
                signal=signal,
                price=exec_price,
                quantity=self.position.quantity,
                pnl_after_fill=self.pnl.realized_pnl,
                fee_cost=fee_cost,
                slippage_cost=slippage_cost,
            )
            self._record_fill(fill)

            trade = self.execution.build_trade_record(
                position=self.position,
                exit_timestamp_ns=signal.timestamp_ns,
                exit_price=exec_price,
                exit_reason=signal.reason,
                exit_fees=fee_cost,
                exit_slippage=slippage_cost,
            )
            if trade is not None:
                self.trades.append(trade)
                self.metrics.on_trade(trade)

            self.position = PositionState()

    def run(self):
        for msg, decoded in self.loader.stream_messages():
            changed = self.book.process_message(msg, decoded)

            if not changed:
                continue

            self.events_processed += 1
            snapshot = self.book.snapshot()

            raw_signal = self.strategy.on_book_update(snapshot, self.position)
            signal = self.risk.approve(
                signal=raw_signal,
                snapshot=snapshot,
                position=self.position,
                entries_so_far=self.metrics.metrics.entries,
            )

            self._execute_signal(signal)
            self._update_pnl(snapshot)

            if self.print_every_event:
                self.reporter.print_event_line(
                    timestamp_ns=snapshot.timestamp_ns,
                    best_bid=snapshot.best_bid,
                    best_ask=snapshot.best_ask,
                    signal_action=signal.action,
                    signal_reason=signal.reason,
                    position=self.position,
                    pnl=self.pnl,
                    max_drawdown=self.metrics.metrics.max_drawdown,
                )

            if self.events_processed >= self.max_events:
                break

        self.reporter.print_summary(
            target_stock=self.target_stock,
            events_processed=self.events_processed,
            pnl=self.pnl,
            metrics_tracker=self.metrics,
            position=self.position,
            fills=self.fills,
            trades=self.trades,
            snapshot=self.book.snapshot(),
        )