from abc import ABC, abstractmethod

from src.models import BookSnapshot, PositionState, Signal


class Strategy(ABC):
    @abstractmethod
    def on_book_update(self, snapshot: BookSnapshot, position: PositionState) -> Signal:
        raise NotImplementedError