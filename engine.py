from typing import List, Optional

from data_loader import ITCHDataLoader
from models import Fill, PositionState, Signal
from order_book import OrderBook


class BacktestEngine:
    def __init__(
        self,
        file_path: str,
        target_stock: str,
        message_types: bytes,
        strategy,
        max_events: int,
    ):
        self.file_path = file_path
        self.target_stock = target_stock
        self.message_types = message_types
        self.strategy = strategy
        self.max_events = max_events

        self.loader = ITCHDataLoader(file_path=file_path, message_types=message_types)
        self.book = OrderBook(target_stock=target_stock)

        self.position = PositionState()
        self.fills: List[Fill] = []
        self.realized_pnl: float = 0.0
        self.events_processed: int = 0

    def execute_signal(self, signal: Signal):
        if signal.price is None:
            return

        if signal.action == "BUY" and self.position.side == 0:
            self.position.side = 1
            self.position.entry_price = signal.price
            self.position.entry_timestamp_ns = signal.timestamp_ns
            self.fills.append(Fill(signal.timestamp_ns, "BUY", signal.price, signal.reason))

        elif signal.action == "SELL" and self.position.side == 0:
            self.position.side = -1
            self.position.entry_price = signal.price
            self.position.entry_timestamp_ns = signal.timestamp_ns
            self.fills.append(Fill(signal.timestamp_ns, "SELL", signal.price, signal.reason))

        elif signal.action == "EXIT_LONG" and self.position.side == 1:
            pnl = signal.price - self.position.entry_price
            self.realized_pnl += pnl
            self.fills.append(Fill(signal.timestamp_ns, "EXIT_LONG", signal.price, signal.reason))
            self.position = PositionState()

        elif signal.action == "EXIT_SHORT" and self.position.side == -1:
            pnl = self.position.entry_price - signal.price
            self.realized_pnl += pnl
            self.fills.append(Fill(signal.timestamp_ns, "EXIT_SHORT", signal.price, signal.reason))
            self.position = PositionState()

    def mark_to_market_pnl(self) -> Optional[float]:
        snapshot = self.book.snapshot()

        if self.position.side == 0 or self.position.entry_price is None:
            return 0.0

        if snapshot.best_bid is None or snapshot.best_ask is None:
            return None

        mid = (snapshot.best_bid + snapshot.best_ask) / 2.0

        if self.position.side == 1:
            return mid - self.position.entry_price

        if self.position.side == -1:
            return self.position.entry_price - mid

        return None

    def run(self):
        for msg, decoded in self.loader.stream_messages():
            changed = self.book.process_message(msg, decoded)

            if not changed:
                continue

            self.events_processed += 1
            snapshot = self.book.snapshot()
            signal = self.strategy.on_book_update(snapshot, self.position)
            self.execute_signal(signal)

            print("SNAPSHOT", snapshot)
            print("SIGNAL", signal)
            print("POSITION", self.position)
            print("REALIZED_PNL", round(self.realized_pnl, 6))
            print("-" * 100)

            if self.events_processed >= self.max_events:
                break

        self.print_summary()

    def print_summary(self):
        print("\n" + "=" * 100)
        print("BACKTEST SUMMARY")
        print("=" * 100)
        print("Target stock:", self.target_stock)
        print("Events processed:", self.events_processed)
        print("Realized PnL:", round(self.realized_pnl, 6))

        mtm = self.mark_to_market_pnl()
        print("Open position MTM:", None if mtm is None else round(mtm, 6))
        print("Current position:", self.position)

        print("\nFILLS:")
        if not self.fills:
            print("No fills")
        else:
            for fill in self.fills:
                print(fill)

        snapshot = self.book.snapshot()
        print("\nFINAL BOOK SNAPSHOT")
        print("Best bid:", snapshot.best_bid)
        print("Best ask:", snapshot.best_ask)