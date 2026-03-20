from config import (
    FILE_PATH,
    TARGET_STOCK,
    MESSAGE_TYPES,
    MAX_EVENTS,
    TRADE_QUANTITY,
    FEE_PER_TRADE,
    SLIPPAGE_BPS,
    ALLOW_SHORTS,
    MAX_POSITION_SIZE,
    MAX_NOTIONAL,
    MAX_TRADES,
    COOLDOWN_NS,
    PRINT_EVERY_EVENT,
)
from engine import BacktestEngine
from strategies import ImbalanceStrategy


def main():
    strategy = ImbalanceStrategy(
        entry_threshold=0.60,
        exit_threshold=0.10,
        max_spread=0.50,
        quantity=TRADE_QUANTITY,
    )

    engine = BacktestEngine(
        file_path=FILE_PATH,
        target_stock=TARGET_STOCK,
        message_types=MESSAGE_TYPES,
        strategy=strategy,
        max_events=MAX_EVENTS,
        trade_quantity=TRADE_QUANTITY,
        fee_per_trade=FEE_PER_TRADE,
        slippage_bps=SLIPPAGE_BPS,
        allow_shorts=ALLOW_SHORTS,
        max_position_size=MAX_POSITION_SIZE,
        max_notional=MAX_NOTIONAL,
        max_trades=MAX_TRADES,
        cooldown_ns=COOLDOWN_NS,
        print_every_event=PRINT_EVERY_EVENT,
    )

    engine.run()


if __name__ == "__main__":
    main()