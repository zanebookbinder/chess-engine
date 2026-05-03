from __future__ import annotations
from src.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING, PIECE_SYMBOLS, WHITE, BLACK


class Piece:
    __slots__ = ("_color", "_piece_type")

    def __init__(self, color: int, piece_type: int) -> None:
        self._color = color
        self._piece_type = piece_type

    @property
    def color(self) -> int:
        return self._color

    @property
    def piece_type(self) -> int:
        return self._piece_type

    @property
    def symbol(self) -> str:
        return PIECE_SYMBOLS[(self._color, self._piece_type)]

    def __repr__(self) -> str:
        return self.symbol

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Piece):
            return NotImplemented
        return self._color == other._color and self._piece_type == other._piece_type

    def __hash__(self) -> int:
        return hash((self._color, self._piece_type))


class Pawn(Piece):
    def __init__(self, color: int) -> None:
        super().__init__(color, PAWN)


class Knight(Piece):
    def __init__(self, color: int) -> None:
        super().__init__(color, KNIGHT)


class Bishop(Piece):
    def __init__(self, color: int) -> None:
        super().__init__(color, BISHOP)


class Rook(Piece):
    def __init__(self, color: int) -> None:
        super().__init__(color, ROOK)


class Queen(Piece):
    def __init__(self, color: int) -> None:
        super().__init__(color, QUEEN)


class King(Piece):
    def __init__(self, color: int) -> None:
        super().__init__(color, KING)


_PIECE_CLASSES = [Pawn, Knight, Bishop, Rook, Queen, King]


def make_piece(piece_type: int, color: int) -> Piece:
    return _PIECE_CLASSES[piece_type](color)
