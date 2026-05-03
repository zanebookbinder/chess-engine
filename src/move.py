from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from src.constants import (
    PAWN, KNIGHT, BISHOP, ROOK, QUEEN,
    WHITE, BLACK, on_board,
)

if TYPE_CHECKING:
    from src.board import Board

# Move flags
NORMAL      = 0
DOUBLE_PUSH = 1
CASTLING    = 2
EN_PASSANT  = 3
PROMOTION   = 4


@dataclass(frozen=True)
class Move:
    from_sq: tuple[int, int]
    to_sq:   tuple[int, int]
    flag:    int = NORMAL
    promotion_piece: Optional[int] = None

    def is_capture(self, board: "Board") -> bool:
        if self.flag == EN_PASSANT:
            return True
        return board.grid[self.to_sq[0]][self.to_sq[1]] is not None

    def to_algebraic(self) -> str:
        fr, ff = self.from_sq
        tr, tf = self.to_sq
        files = "abcdefgh"
        ranks = "87654321"
        s = files[ff] + ranks[fr] + files[tf] + ranks[tr]
        if self.flag == PROMOTION and self.promotion_piece is not None:
            s += "nbrq"[self.promotion_piece - KNIGHT] if self.promotion_piece != QUEEN else "q"
            promo_map = {KNIGHT: "n", BISHOP: "b", ROOK: "r", QUEEN: "q"}
            s = files[ff] + ranks[fr] + files[tf] + ranks[tr] + promo_map[self.promotion_piece]
        return s

    def __repr__(self) -> str:
        return self.to_algebraic()


def move_from_algebraic(notation: str, board: "Board") -> Move:
    """Parse long algebraic notation like 'e2e4' or 'e7e8q' into a Move."""
    files = "abcdefgh"
    ranks = "87654321"
    ff = files.index(notation[0])
    fr = ranks.index(notation[1])
    tf = files.index(notation[2])
    tr = ranks.index(notation[3])

    from_sq = (fr, ff)
    to_sq   = (tr, tf)

    piece = board.grid[fr][ff]
    if piece is None:
        raise ValueError(f"No piece on {notation[:2]}")

    from src.constants import PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING

    # Determine flag
    if piece.piece_type == PAWN:
        if abs(tr - fr) == 2:
            return Move(from_sq, to_sq, DOUBLE_PUSH)
        if tf != ff and board.grid[tr][tf] is None:
            return Move(from_sq, to_sq, EN_PASSANT)
        if tr == 0 or tr == 7:
            promo_map = {"n": KNIGHT, "b": BISHOP, "r": ROOK, "q": QUEEN}
            promo = promo_map.get(notation[4].lower() if len(notation) > 4 else "q", QUEEN)
            return Move(from_sq, to_sq, PROMOTION, promo)

    if piece.piece_type == KING and abs(tf - ff) == 2:
        return Move(from_sq, to_sq, CASTLING)

    return Move(from_sq, to_sq)
