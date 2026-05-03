from __future__ import annotations
from typing import TYPE_CHECKING

from src.constants import (
    WHITE, BLACK, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    CASTLE_WHITE_KINGSIDE, CASTLE_WHITE_QUEENSIDE,
    CASTLE_BLACK_KINGSIDE, CASTLE_BLACK_QUEENSIDE,
    on_board,
)
from src.move import Move, NORMAL, DOUBLE_PUSH, CASTLING, EN_PASSANT, PROMOTION

if TYPE_CHECKING:
    from src.board import Board

BISHOP_DIRS = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
ROOK_DIRS   = [(-1,  0), ( 1, 0), (0, -1), (0, 1)]
QUEEN_DIRS  = BISHOP_DIRS + ROOK_DIRS
KNIGHT_OFFSETS = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]


class MoveGenerator:
    def __init__(self, board: "Board") -> None:
        self._board = board

    def generate_legal_moves(self) -> list[Move]:
        color = self._board.side_to_move
        pseudo = self._generate_pseudo_legal(color)
        return [m for m in pseudo if self._is_legal(m, color)]

    def generate_pseudo_legal_moves(self, color: int) -> list[Move]:
        return self._generate_pseudo_legal(color)

    # ------------------------------------------------------------------
    # Pseudo-legal generation
    # ------------------------------------------------------------------

    def _generate_pseudo_legal(self, color: int) -> list[Move]:
        moves: list[Move] = []
        for rank in range(8):
            for file in range(8):
                piece = self._board.grid[rank][file]
                if piece is None or piece.color != color:
                    continue
                pt = piece.piece_type
                if pt == PAWN:
                    moves.extend(self._pawn_moves(rank, file, color))
                elif pt == KNIGHT:
                    moves.extend(self._knight_moves(rank, file, color))
                elif pt == BISHOP:
                    moves.extend(self._sliding_moves(rank, file, color, BISHOP_DIRS))
                elif pt == ROOK:
                    moves.extend(self._sliding_moves(rank, file, color, ROOK_DIRS))
                elif pt == QUEEN:
                    moves.extend(self._sliding_moves(rank, file, color, QUEEN_DIRS))
                elif pt == KING:
                    moves.extend(self._king_moves(rank, file, color))
        return moves

    # ------------------------------------------------------------------
    # Per-piece move generators
    # ------------------------------------------------------------------

    def _pawn_moves(self, rank: int, file: int, color: int) -> list[Move]:
        moves: list[Move] = []
        direction = -1 if color == WHITE else 1
        start_rank = 6 if color == WHITE else 1
        promo_rank = 0 if color == WHITE else 7
        from_sq = (rank, file)

        # Single push
        nr = rank + direction
        if on_board(nr, file) and self._board.grid[nr][file] is None:
            to_sq = (nr, file)
            if nr == promo_rank:
                moves.extend(self._promotion_moves(from_sq, to_sq))
            else:
                moves.append(Move(from_sq, to_sq))
                # Double push from starting rank
                if rank == start_rank:
                    nr2 = rank + 2 * direction
                    if self._board.grid[nr2][file] is None:
                        moves.append(Move(from_sq, (nr2, file), DOUBLE_PUSH))

        # Captures
        for df in (-1, 1):
            nf = file + df
            if not on_board(nr, nf):
                continue
            target = self._board.grid[nr][nf]
            to_sq = (nr, nf)
            # Normal capture
            if target is not None and target.color != color:
                if nr == promo_rank:
                    moves.extend(self._promotion_moves(from_sq, to_sq))
                else:
                    moves.append(Move(from_sq, to_sq))
            # En passant capture
            elif self._board.en_passant_target == to_sq:
                moves.append(Move(from_sq, to_sq, EN_PASSANT))

        return moves

    def _promotion_moves(
        self, from_sq: tuple[int, int], to_sq: tuple[int, int]
    ) -> list[Move]:
        return [
            Move(from_sq, to_sq, PROMOTION, KNIGHT),
            Move(from_sq, to_sq, PROMOTION, BISHOP),
            Move(from_sq, to_sq, PROMOTION, ROOK),
            Move(from_sq, to_sq, PROMOTION, QUEEN),
        ]

    def _knight_moves(self, rank: int, file: int, color: int) -> list[Move]:
        moves: list[Move] = []
        from_sq = (rank, file)
        for dr, df in KNIGHT_OFFSETS:
            r, f = rank + dr, file + df
            if on_board(r, f):
                target = self._board.grid[r][f]
                if target is None or target.color != color:
                    moves.append(Move(from_sq, (r, f)))
        return moves

    def _sliding_moves(
        self, rank: int, file: int, color: int, directions: list[tuple[int, int]]
    ) -> list[Move]:
        moves: list[Move] = []
        from_sq = (rank, file)
        for dr, df in directions:
            r, f = rank + dr, file + df
            while on_board(r, f):
                target = self._board.grid[r][f]
                if target is None:
                    moves.append(Move(from_sq, (r, f)))
                elif target.color != color:
                    moves.append(Move(from_sq, (r, f)))
                    break
                else:
                    break
                r += dr; f += df
        return moves

    def _king_moves(self, rank: int, file: int, color: int) -> list[Move]:
        moves: list[Move] = []
        from_sq = (rank, file)
        for dr in (-1, 0, 1):
            for df in (-1, 0, 1):
                if dr == 0 and df == 0:
                    continue
                r, f = rank + dr, file + df
                if on_board(r, f):
                    target = self._board.grid[r][f]
                    if target is None or target.color != color:
                        moves.append(Move(from_sq, (r, f)))
        moves.extend(self._castling_moves(rank, file, color))
        return moves

    def _castling_moves(self, rank: int, file: int, color: int) -> list[Move]:
        moves: list[Move] = []
        board = self._board

        if board.is_in_check(color):
            return moves

        # Kingside
        ks_right = CASTLE_WHITE_KINGSIDE if color == WHITE else CASTLE_BLACK_KINGSIDE
        if board.castling_rights & ks_right:
            # Squares between king (file 4) and rook (file 7) must be empty: files 5, 6
            if (board.grid[rank][5] is None and board.grid[rank][6] is None):
                # King must not pass through or land on an attacked square
                if (not board.is_square_attacked(rank, 5, color ^ 1) and
                        not board.is_square_attacked(rank, 6, color ^ 1)):
                    moves.append(Move((rank, file), (rank, 6), CASTLING))

        # Queenside
        qs_right = CASTLE_WHITE_QUEENSIDE if color == WHITE else CASTLE_BLACK_QUEENSIDE
        if board.castling_rights & qs_right:
            # Squares between king (file 4) and rook (file 0) must be empty: files 1, 2, 3
            if (board.grid[rank][1] is None and board.grid[rank][2] is None and
                    board.grid[rank][3] is None):
                # King passes through file 3 and lands on file 2
                if (not board.is_square_attacked(rank, 3, color ^ 1) and
                        not board.is_square_attacked(rank, 2, color ^ 1)):
                    moves.append(Move((rank, file), (rank, 2), CASTLING))

        return moves

    # ------------------------------------------------------------------
    # Legality filter
    # ------------------------------------------------------------------

    def _is_legal(self, move: Move, color: int) -> bool:
        self._board.make_move(move)
        in_check = self._board.is_in_check(color)
        self._board.unmake_move()
        return not in_check
