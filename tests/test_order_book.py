from order_book import OrderBook


class DummyAdd:
    message_type = b"A"
    order_reference_number = 1
    timestamp = 100


class DummyExec:
    message_type = b"E"
    order_reference_number = 1
    timestamp = 110


class DummyCancel:
    message_type = b"X"
    order_reference_number = 1
    timestamp = 120


class DummyDelete:
    message_type = b"D"
    order_reference_number = 1
    timestamp = 130


class DummyReplace:
    message_type = b"U"
    order_reference_number = 1
    new_order_reference_number = 2
    timestamp = 140


class DecodedAdd:
    stock = "AAPL"
    buy_sell_indicator = "B"
    price = 100.0
    shares = 10


class DecodedExec:
    executed_shares = 4


class DecodedCancel:
    cancelled_shares = 3


class DecodedReplace:
    price = 101.0
    shares = 5


def run_tests():
    book = OrderBook("AAPL")

    assert book.process_message(DummyAdd(), DecodedAdd()) is True
    assert 1 in book.orders
    assert book.orders[1].shares == 10

    assert book.process_message(DummyExec(), DecodedExec()) is True
    assert book.orders[1].shares == 6

    assert book.process_message(DummyCancel(), DecodedCancel()) is True
    assert book.orders[1].shares == 3

    assert book.process_message(DummyReplace(), DecodedReplace()) is True
    assert 1 not in book.orders
    assert 2 in book.orders
    assert book.orders[2].price == 101.0
    assert book.orders[2].shares == 5

    delete_msg = DummyDelete()
    delete_msg.order_reference_number = 2
    assert book.process_message(delete_msg, None) is True
    assert 2 not in book.orders

    print("All order book tests passed.")


if __name__ == "__main__":
    run_tests()