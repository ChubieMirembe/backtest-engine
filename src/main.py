
    
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
from strategies import (
    QueueImbalanceStrategy,
    OFIStrategy,
    MLOFIStrategy,
    MicropriceStrategy,
    OFIPersistenceStrategy,
    QueueDynamicsStrategy,
    DepletionStrategy,
)


def build_strategy(name: str):
    if name == "qi":
        return QueueImbalanceStrategy(
        quantity=TRADE_QUANTITY,
        max_spread=0.50,
        long_threshold=0.70,
        short_threshold=-0.70,
        long_exit_threshold=0.30,
        short_exit_threshold=-0.30,
        long_reset_threshold=0.20,
        short_reset_threshold=-0.20,
        max_holding_time_ns=20_000_000_000,
        allow_long=True,
        allow_short=True,
        debug=True,
    )

    if name == "ofi":
        return OFIStrategy(
            quantity=TRADE_QUANTITY,
            max_spread=0.50,
            long_threshold=50.0,
            short_threshold=-50.0,
            exit_band=10.0,
            max_holding_time_ns=20_000_000_000,
            debug=True,
        )

    if name == "mlofi":
        return MLOFIStrategy(
            quantity=TRADE_QUANTITY,
            levels=3,
            weights=[1.0, 0.5, 0.25],
            max_spread=0.50,
            long_threshold=100.0,
            short_threshold=-100.0,
            exit_band=20.0,
            max_holding_time_ns=20_000_000_000,
            debug=True,
        )

    if name == "microprice":
        return MicropriceStrategy(
            quantity=TRADE_QUANTITY,
            max_spread=0.50,
            long_epsilon=0.01,
            short_epsilon=0.01,
            exit_epsilon=0.002,
            max_holding_time_ns=20_000_000_000,
            debug=True,
        )

    if name == "ofi_persistence":
        return OFIPersistenceStrategy(
            quantity=TRADE_QUANTITY,
            max_spread=0.50,
            window_size=20,
            long_threshold=5,
            short_threshold=-5,
            exit_band=1,
            max_holding_time_ns=20_000_000_000,
            debug=True,
        )

    if name == "queue_dynamics":
        return QueueDynamicsStrategy(
            quantity=TRADE_QUANTITY,
            max_spread=0.50,
            min_imbalance=0.10,
            min_depletion_ratio=0.10,
            min_velocity=0.0,
            min_acceleration=0.0,
            exit_imbalance_band=0.0,
            max_holding_time_ns=20_000_000_000,
            debug=True,
        )

    if name == "depletion":
        return DepletionStrategy(
            quantity=TRADE_QUANTITY,
            max_spread=0.40,
            min_imbalance_long=0.30,
            max_imbalance_short=-0.30,
            min_depletion_ratio=0.20,
            thin_ask_threshold=5,
            thin_bid_threshold=5,
            persistence_required=3,
            max_holding_time_ns=20_000_000_000,
            debug=True,
        )

    raise ValueError(f"Unknown strategy name: {name}")


def main():
    strategy_name = "qi"  # Change this to select different strategies: "ofi", "mlofi", "microprice", "ofi_persistence", "queue_dynamics", "depletion"
    strategy = build_strategy(strategy_name)

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