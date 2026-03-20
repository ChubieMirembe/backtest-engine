from config import FILE_PATH, TARGET_STOCK, MAX_EVENTS, MESSAGE_TYPES
from engine import BacktestEngine
from strategies import ImbalanceStrategy


def main():
    strategy = ImbalanceStrategy(
        entry_threshold=0.60,
        exit_threshold=0.10,
        max_spread=0.50,
    )

    engine = BacktestEngine(
        file_path=FILE_PATH,
        target_stock=TARGET_STOCK,
        message_types=MESSAGE_TYPES,
        strategy=strategy,
        max_events=MAX_EVENTS,
    )

    engine.run()


if __name__ == "__main__":
    main()