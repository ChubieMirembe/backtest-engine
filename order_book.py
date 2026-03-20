from copy import deepcopy
from typing import Dict, Tuple, Optional

from models import Order, BookSnapshot


class OrderBook:
    def __init__(self, target_stock: str):
        self.target_stock = target_stock
        self.orders: Dict[int, Order] = {}
        self.last_timestamp_ns: Optional[int] = None

    def process_message(self, msg, decoded) -> bool:
        """
        Updates live order state.
        Returns True only when the target stock book changed.
        """
        mtype = msg.message_type

        # A = Add Order
        if mtype == b"A" and decoded.stock == self.target_stock:
            self.orders[msg.order_reference_number] = Order(
                side=decoded.buy_sell_indicator,
                price=decoded.price,
                shares=decoded.shares,
            )
            self.last_timestamp_ns = msg.timestamp
            return True

        # E = Execute
        elif mtype == b"E" and msg.order_reference_number in self.orders:
            self.orders[msg.order_reference_number].shares -= decoded.executed_shares
            if self.orders[msg.order_reference_number].shares <= 0:
                del self.orders[msg.order_reference_number]
            self.last_timestamp_ns = msg.timestamp
            return True

        # X = Cancel
        elif mtype == b"X" and msg.order_reference_number in self.orders:
            self.orders[msg.order_reference_number].shares -= decoded.cancelled_shares
            if self.orders[msg.order_reference_number].shares <= 0:
                del self.orders[msg.order_reference_number]
            self.last_timestamp_ns = msg.timestamp
            return True

        # D = Delete
        elif mtype == b"D" and msg.order_reference_number in self.orders:
            del self.orders[msg.order_reference_number]
            self.last_timestamp_ns = msg.timestamp
            return True

        # U = Replace
        elif mtype == b"U" and msg.order_reference_number in self.orders:
            old_order = self.orders[msg.order_reference_number]
            new_order = Order(
                side=old_order.side,
                price=decoded.price,
                shares=decoded.shares,
            )
            del self.orders[msg.order_reference_number]
            self.orders[msg.new_order_reference_number] = new_order
            self.last_timestamp_ns = msg.timestamp
            return True

        return False

    def rebuild_price_levels(self) -> Tuple[Dict[float, int], Dict[float, int]]:
        bid_levels: Dict[float, int] = {}
        ask_levels: Dict[float, int] = {}

        for order in self.orders.values():
            if order.shares <= 0:
                continue

            if order.side == "B":
                bid_levels[order.price] = bid_levels.get(order.price, 0) + order.shares
            else:
                ask_levels[order.price] = ask_levels.get(order.price, 0) + order.shares

        return bid_levels, ask_levels

    def best_bid(self, bid_levels: Dict[float, int]) -> Optional[float]:
        return max(bid_levels) if bid_levels else None

    def best_ask(self, ask_levels: Dict[float, int]) -> Optional[float]:
        return min(ask_levels) if ask_levels else None

    def snapshot(self) -> BookSnapshot:
        bid_levels, ask_levels = self.rebuild_price_levels()
        best_bid = self.best_bid(bid_levels)
        best_ask = self.best_ask(ask_levels)

        return BookSnapshot(
            timestamp_ns=self.last_timestamp_ns if self.last_timestamp_ns is not None else 0,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_levels=deepcopy(bid_levels),
            ask_levels=deepcopy(ask_levels),
            orders=deepcopy(self.orders),
        )