from models import PerformanceMetrics, TradeRecord, PnLState, PositionState


class MetricsTracker:
    def __init__(self, starting_capital: float = 0.0):
        self.metrics = PerformanceMetrics()
        self.starting_capital = starting_capital

    def on_entry(self):
        self.metrics.entries += 1

    def on_exit(self):
        self.metrics.exits += 1

    def on_trade(self, trade: TradeRecord):
        self.metrics.round_trips += 1
        self.metrics.holding_time_ns_total += trade.holding_time_ns

        if trade.net_pnl > 0:
            self.metrics.wins += 1
            self.metrics.gross_profit += trade.net_pnl
            self.metrics.max_win = max(self.metrics.max_win, trade.net_pnl)
        elif trade.net_pnl < 0:
            self.metrics.losses += 1
            self.metrics.gross_loss += abs(trade.net_pnl)
            self.metrics.max_loss = min(self.metrics.max_loss, trade.net_pnl)
        else:
            self.metrics.breakeven_trades += 1

    def on_event_equity(self, total_pnl: float, position: PositionState):
        equity = self.starting_capital + total_pnl
        self.metrics.equity_curve.append(equity)

        if equity > self.metrics.equity_peak:
            self.metrics.equity_peak = equity

        drawdown = self.metrics.equity_peak - equity
        self.metrics.drawdown_curve.append(drawdown)
        self.metrics.max_drawdown = max(self.metrics.max_drawdown, drawdown)

        if self.metrics.equity_peak > 0:
            drawdown_pct = drawdown / self.metrics.equity_peak
            self.metrics.max_drawdown_pct = max(self.metrics.max_drawdown_pct, drawdown_pct)

        if not position.is_flat:
            self.metrics.exposure_events += 1

    def average_win(self) -> float:
        if self.metrics.wins == 0:
            return 0.0
        return self.metrics.gross_profit / self.metrics.wins

    def average_loss(self) -> float:
        if self.metrics.losses == 0:
            return 0.0
        return self.metrics.gross_loss / self.metrics.losses

    def average_pnl_per_trade(self, trades: list[TradeRecord]) -> float:
        if self.metrics.round_trips == 0:
            return 0.0
        return sum(t.net_pnl for t in trades) / self.metrics.round_trips

    def win_rate(self) -> float:
        if self.metrics.round_trips == 0:
            return 0.0
        return self.metrics.wins / self.metrics.round_trips

    def profit_factor(self) -> float:
        if self.metrics.gross_loss == 0:
            return float("inf") if self.metrics.gross_profit > 0 else 0.0
        return self.metrics.gross_profit / self.metrics.gross_loss

    def average_holding_time_ns(self) -> float:
        if self.metrics.round_trips == 0:
            return 0.0
        return self.metrics.holding_time_ns_total / self.metrics.round_trips