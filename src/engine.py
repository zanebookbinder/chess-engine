from __future__ import annotations
from typing import Optional

from src.constants import WHITE, BLACK, PAWN, QUEEN, PIECE_VALUES
from src.board import Board
from src.move import Move, PROMOTION, CASTLING, EN_PASSANT
from src.move_generator import MoveGenerator
from src.evaluator import Evaluator

CHECKMATE_SCORE = 100_000
INF = 10_000_000


class Engine:
    def __init__(self, board: Board, depth: int = 4) -> None:
        self._board = board
        self._depth = depth

    def get_best_move(self) -> Optional[Move]:
        moves = self._order_moves(MoveGenerator(self._board).generate_legal_moves())
        if not moves:
            self._top_moves: list[tuple[Move, int]] = []
            return None

        # Sign to convert mover-perspective scores → White-centric scores
        sign = 1 if self._board.side_to_move == WHITE else -1

        scored: list[tuple[int, Move]] = []
        alpha = -INF
        beta  =  INF

        for move in moves:
            self._board.make_move(move)
            score = -self._negamax(self._depth - 1, -beta, -alpha)
            self._board.unmake_move()
            scored.append((score, move))
            alpha = max(alpha, score)

        scored.sort(reverse=True)
        # Store top 5 with scores in White-centric centipawns
        self._top_moves = [(m, s * sign) for s, m in scored[:5]]
        return scored[0][1]

    @property
    def top_moves(self) -> list[tuple[Move, int]]:
        """Top moves from the last search; scores in White-centric centipawns."""
        return getattr(self, "_top_moves", [])

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _negamax(self, depth: int, alpha: int, beta: int) -> int:
        if depth == 0:
            return self._quiescence(alpha, beta)

        moves = self._order_moves(MoveGenerator(self._board).generate_legal_moves())

        if not moves:
            if self._board.is_in_check(self._board.side_to_move):
                return -(CHECKMATE_SCORE - (self._depth - depth))
            return 0  # stalemate

        best = -INF
        for move in moves:
            self._board.make_move(move)
            score = -self._negamax(depth - 1, -beta, -alpha)
            self._board.unmake_move()
            if score > best:
                best = score
            alpha = max(alpha, score)
            if alpha >= beta:
                break

        return best

    # Max material gain possible in one capture (used for delta pruning)
    _DELTA_MARGIN = PIECE_VALUES[QUEEN] + 200

    def _quiescence(self, alpha: int, beta: int) -> int:
        """Search captures until the position is quiet, preventing horizon blunders."""
        stand_pat = Evaluator(self._board).evaluate()
        if self._board.side_to_move != WHITE:
            stand_pat = -stand_pat

        if stand_pat >= beta:
            return beta

        # Delta pruning: if even capturing the best piece can't reach alpha, bail early
        if stand_pat + self._DELTA_MARGIN < alpha:
            return alpha

        if stand_pat > alpha:
            alpha = stand_pat

        captures = [
            m for m in MoveGenerator(self._board).generate_legal_moves()
            if m.is_capture(self._board) or m.flag == PROMOTION
        ]
        captures = self._order_moves(captures)

        for move in captures:
            self._board.make_move(move)
            score = -self._quiescence(-beta, -alpha)
            self._board.unmake_move()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    # ------------------------------------------------------------------
    # Move ordering
    # ------------------------------------------------------------------

    def _order_moves(self, moves: list[Move]) -> list[Move]:
        return sorted(moves, key=self._move_score, reverse=True)

    def _move_score(self, move: Move) -> int:
        if move.flag == PROMOTION:
            return 20_000
        if move.is_capture(self._board):
            return 10_000 + self._mvv_lva_score(move)
        if move.flag == CASTLING:
            return 5_000
        return 0

    def _mvv_lva_score(self, move: Move) -> int:
        attacker = self._board.grid[move.from_sq[0]][move.from_sq[1]]
        if move.flag == EN_PASSANT:
            return PIECE_VALUES[PAWN]

        victim = self._board.grid[move.to_sq[0]][move.to_sq[1]]
        if victim is None or attacker is None:
            return 0
        return PIECE_VALUES[victim.piece_type] - PIECE_VALUES[attacker.piece_type] // 10
