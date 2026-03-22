from models import PnLState, PositionState, Fill, TradeRecord, BookSnapshot
from metrics import MetricsTracker


class BacktestReporter:
    def print_event_line(
        self,
        timestamp_ns: int,
        best_bid,
        best_ask,
        signal_action: str,
        signal_reason: str,
        position: PositionState,
        pnl: PnLState,
        max_drawdown: float,
    ):
        print(
            f"ts={timestamp_ns} "
            f"bid={best_bid} "
            f"ask={best_ask} "
            f"signal={signal_action} "
            f"reason={signal_reason} "
            f"pos_side={position.side} "
            f"qty={position.quantity} "
            f"realized={pnl.realized_pnl:.6f} "
            f"unrealized={pnl.unrealized_pnl:.6f} "
            f"total={pnl.total_pnl:.6f} "
            f"dd={max_drawdown:.6f}"
        )

    def print_summary(
        self,
        target_stock: str,
        events_processed: int,
        pnl: PnLState,
        metrics_tracker: MetricsTracker,
        position: PositionState,
        fills: list[Fill],
        trades: list[TradeRecord],
        snapshot: BookSnapshot,
    ):
        metrics = metrics_tracker.metrics

        print("\n" + "=" * 100)
        print("BACKTEST SUMMARY")
        print("=" * 100)
        print("Target stock:", target_stock)
        print("Events processed:", events_processed)

        print("\nPNL")
        print("Gross realized PnL:", round(pnl.gross_realized_pnl, 6))
        print("Total fees:", round(pnl.total_fees, 6))
        print("Total slippage:", round(pnl.total_slippage, 6))
        print("Realized PnL:", round(pnl.realized_pnl, 6))
        print("Unrealized PnL:", round(pnl.unrealized_pnl, 6))
        print("Total PnL:", round(pnl.total_pnl, 6))

        print("\nTRADE COUNTS")
        print("Entries:", metrics.entries)
        print("Exits:", metrics.exits)
        print("Round trips:", metrics.round_trips)
        print("Wins:", metrics.wins)
        print("Losses:", metrics.losses)
        print("Breakeven trades:", metrics.breakeven_trades)
        print("Win rate:", round(metrics_tracker.win_rate() * 100, 4), "%")

        print("\nTRADE QUALITY")
        print("Average win:", round(metrics_tracker.average_win(), 6))
        print("Average loss:", round(metrics_tracker.average_loss(), 6))
        print("Average PnL per trade:", round(metrics_tracker.average_pnl_per_trade(trades), 6))
        pf = metrics_tracker.profit_factor()
        print("Profit factor:", round(pf, 6) if pf != float("inf") else "inf")
        print("Max win:", round(metrics.max_win, 6))
        print("Max loss:", round(metrics.max_loss, 6))

        print("\nRISK")
        print("Equity peak:", round(metrics.equity_peak, 6))
        print("Max drawdown:", round(metrics.max_drawdown, 6))
        print("Max drawdown %:", round(metrics.max_drawdown_pct * 100, 6), "%")

        print("\nEXPOSURE")
        print("Exposure events:", metrics.exposure_events)
        print("Total holding time (ns):", metrics.holding_time_ns_total)
        print("Average holding time (ns):", round(metrics_tracker.average_holding_time_ns(), 2))

        print("\nCURRENT POSITION")
        print(position)

        print("\nFILLS")
        if not fills:
            print("No fills")
        else:
            for fill in fills:
                print(fill)

        print("\nTRADES")
        if not trades:
            print("No completed trades")
        else:
            for trade in trades:
                print(trade)

        print("\nFINAL BOOK SNAPSHOT")
        print("Best bid:", snapshot.best_bid)
        print("Best ask:", snapshot.best_ask)