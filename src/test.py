from itch.parser import MessageParser

file_path = "Data/03272019.NASDAQ_ITCH50"
target_stock = "AAPL"
max_events = 50

parser = MessageParser(message_type=b"AEXDU")

orders = {}
event_count = 0

prev_timestamp = None
prev_best_bid = None
prev_best_ask = None
prev_bid_size = None
prev_ask_size = None
prev_bid_velocity_ns = None
prev_ask_velocity_ns = None


def rebuild_price_levels(order_map):
    bid_levels = {}
    ask_levels = {}

    for order in order_map.values():
        shares = order["shares"]
        if shares <= 0:
            continue

        price = order["price"]
        side = order["side"]

        if side == "B":
            bid_levels[price] = bid_levels.get(price, 0) + shares
        else:
            ask_levels[price] = ask_levels.get(price, 0) + shares

    return bid_levels, ask_levels


def compute_top_of_book(bid_levels, ask_levels):
    best_bid = max(bid_levels) if bid_levels else None
    best_ask = min(ask_levels) if ask_levels else None

    bid_size = bid_levels.get(best_bid, 0) if best_bid is not None else 0
    ask_size = ask_levels.get(best_ask, 0) if best_ask is not None else 0

    spread = None
    if best_bid is not None and best_ask is not None:
        spread = round(best_ask - best_bid, 4)

    imbalance = None
    total_top_size = bid_size + ask_size
    if total_top_size > 0:
        imbalance = round((bid_size - ask_size) / total_top_size, 6)

    return best_bid, bid_size, best_ask, ask_size, spread, imbalance


with open(file_path, "rb") as f:
    for msg in parser.parse_file(f):
        decoded = msg.decode()
        mtype = msg.message_type
        tracked_event = False

        # A = Add Order
        if mtype == b"A" and decoded.stock == target_stock:
            orders[msg.order_reference_number] = {
                "side": decoded.buy_sell_indicator,
                "price": decoded.price,
                "shares": decoded.shares,
            }

            print("ADD", msg.order_reference_number, orders[msg.order_reference_number])
            tracked_event = True

        # E = Order Executed
        elif mtype == b"E" and msg.order_reference_number in orders:
            orders[msg.order_reference_number]["shares"] -= decoded.executed_shares

            print(
                "EXEC",
                msg.order_reference_number,
                "remaining",
                orders[msg.order_reference_number]["shares"],
            )
            tracked_event = True

            if orders[msg.order_reference_number]["shares"] <= 0:
                del orders[msg.order_reference_number]

        # X = Order Cancel
        elif mtype == b"X" and msg.order_reference_number in orders:
            orders[msg.order_reference_number]["shares"] -= decoded.cancelled_shares

            print(
                "CANCEL",
                msg.order_reference_number,
                "remaining",
                orders[msg.order_reference_number]["shares"],
            )
            tracked_event = True

            if orders[msg.order_reference_number]["shares"] <= 0:
                del orders[msg.order_reference_number]

        # D = Order Delete
        elif mtype == b"D" and msg.order_reference_number in orders:
            print("DELETE", msg.order_reference_number)
            del orders[msg.order_reference_number]
            tracked_event = True

        # U = Order Replace
        elif mtype == b"U" and msg.order_reference_number in orders:
            old_order = orders[msg.order_reference_number]

            new_order = {
                "side": old_order["side"],
                "price": decoded.price,
                "shares": decoded.shares,
            }

            del orders[msg.order_reference_number]
            orders[msg.new_order_reference_number] = new_order

            print(
                "REPLACE",
                msg.order_reference_number,
                "->",
                msg.new_order_reference_number,
                new_order,
            )
            tracked_event = True

        if tracked_event:
            event_count += 1

            bid_levels, ask_levels = rebuild_price_levels(orders)
            best_bid, bid_size, best_ask, ask_size, spread, imbalance = compute_top_of_book(
                bid_levels, ask_levels
            )

            dt_ns = None
            if prev_timestamp is not None:
                dt_ns = msg.timestamp - prev_timestamp

            bid_price_changed = best_bid != prev_best_bid
            ask_price_changed = best_ask != prev_best_ask

            bid_velocity_ns = None
            ask_velocity_ns = None
            bid_acceleration_ns = None
            ask_acceleration_ns = None

            if (
                dt_ns is not None
                and dt_ns > 0
                and prev_bid_size is not None
                and prev_ask_size is not None
            ):
                bid_velocity_ns = (bid_size - prev_bid_size) / dt_ns
                ask_velocity_ns = (ask_size - prev_ask_size) / dt_ns

                if prev_bid_velocity_ns is not None:
                    bid_acceleration_ns = (bid_velocity_ns - prev_bid_velocity_ns) / dt_ns

                if prev_ask_velocity_ns is not None:
                    ask_acceleration_ns = (ask_velocity_ns - prev_ask_velocity_ns) / dt_ns

            print(
                "TOB",
                {
                    "timestamp_ns": msg.timestamp,
                    "dt_ns": dt_ns,
                    "best_bid": best_bid,
                    "bid_size": bid_size,
                    "best_ask": best_ask,
                    "ask_size": ask_size,
                    "spread": spread,
                    "imbalance": imbalance,
                    "bid_price_changed": bid_price_changed,
                    "ask_price_changed": ask_price_changed,
                    "bid_velocity_per_ns": bid_velocity_ns,
                    "ask_velocity_per_ns": ask_velocity_ns,
                    "bid_acceleration_per_ns2": bid_acceleration_ns,
                    "ask_acceleration_per_ns2": ask_acceleration_ns,
                },
            )
            print("-" * 80)

            prev_timestamp = msg.timestamp
            prev_best_bid = best_bid
            prev_best_ask = best_ask
            prev_bid_size = bid_size
            prev_ask_size = ask_size
            prev_bid_velocity_ns = bid_velocity_ns
            prev_ask_velocity_ns = ask_velocity_ns

            if event_count >= max_events:
                break

print(f"Live tracked {target_stock} orders: {len(orders)}")

bid_levels, ask_levels = rebuild_price_levels(orders)
best_bid, bid_size, best_ask, ask_size, spread, imbalance = compute_top_of_book(
    bid_levels, ask_levels
)

print("\nBID LEVELS:")
for price in sorted(bid_levels.keys(), reverse=True)[:10]:
    print(price, bid_levels[price])

print("\nASK LEVELS:")
for price in sorted(ask_levels.keys())[:10]:
    print(price, ask_levels[price])

print("\nTOP OF BOOK:")
print("Best bid:", best_bid, "size:", bid_size)
print("Best ask:", best_ask, "size:", ask_size)
print("Spread:", spread)
print("Top-of-book imbalance:", imbalance)