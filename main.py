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
from strategies import ObserverStrategy
from strategies import QueueDynamicsStrategy


def main():
    # strategy = QueueDynamicsStrategy(
    #     quantity=TRADE_QUANTITY,
    #     max_spread=0.50,
    #     min_imbalance=0.10,
    #     min_bid_velocity_per_ns=0.0,
    #     min_ask_velocity_per_ns=0.0,
    #     min_bid_acceleration_per_ns2=0.0,
    #     min_ask_acceleration_per_ns2=0.0,
    #     min_depletion_ratio=0.10,
    #     max_holding_time_ns=30_000_000_000,
    #     debug=False,
    # )
    
    strategy = ObserverStrategy(
       print_every_update=True,
       only_print_when_interesting=True,
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