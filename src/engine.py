from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.constants import WHITE, BLACK, PAWN, QUEEN, PIECE_VALUES
from src.board import Board
from src.move import Move, PROMOTION, CASTLING, EN_PASSANT
from src.move_generator import MoveGenerator
from src.evaluator import Evaluator

CHECKMATE_SCORE = 100_000
INF = 10_000_000

# Transposition table entry flags
TT_EXACT = 0   # score is exact
TT_LOWER = 1   # score is a lower bound (fail-high / beta cutoff)
TT_UPPER = 2   # score is an upper bound (fail-low / alpha cutoff)

_MAX_PLY = 64  # maximum search depth for killer-move table


@dataclass(slots=True)
class _TTEntry:
    depth: int
    score: int
    flag:  int
    best_move: Optional[Move]


class Engine:
    def __init__(self, board: Board, depth: int = 4) -> None:
        self._board = board
        self._depth = depth
        self._tt: dict[int, _TTEntry] = {}
        self._killers: list[list[Optional[Move]]] = [[None, None] for _ in range(_MAX_PLY)]
        self._top_moves: list[tuple[Move, int]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_best_move(self, on_progress=None) -> Optional[Move]:
        """Find the best move.  on_progress(move, idx, total) is called for each
        root move evaluated during the final depth pass."""
        moves = self._order_moves(MoveGenerator(self._board).generate_legal_moves())
        if not moves:
            self._top_moves = []
            return None

        sign = 1 if self._board.side_to_move == WHITE else -1
        best_move = moves[0]

        # Iterative deepening: each iteration refines best_move, and the TT
        # from shallower passes dramatically improves pruning in deeper ones.
        for current_depth in range(1, self._depth + 1):
            self._killers = [[None, None] for _ in range(_MAX_PLY)]
            alpha = -INF
            beta  =  INF
            best_score = -INF
            is_final = current_depth == self._depth

            # Try the PV move (best from last iteration) first
            ordered = [best_move] + [m for m in moves if m != best_move]

            for idx, move in enumerate(ordered):
                if is_final and on_progress is not None:
                    on_progress(move, idx, len(ordered))
                self._board.make_move(move)
                score = -self._negamax(current_depth - 1, -beta, -alpha, ply=1)
                self._board.unmake_move()
                if score > best_score:
                    best_score = score
                    best_move  = move
                alpha = max(alpha, score)

        self._update_display_scores()
        return best_move

    def analyze_for_display(self) -> None:
        """Score top moves for the current side to move (shown in the UI sidebar)."""
        self._update_display_scores()

    @property
    def top_moves(self) -> list[tuple[Move, int]]:
        """Top moves for the current/last-analyzed side; scores in White-centric centipawns."""
        return self._top_moves

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _negamax(self, depth: int, alpha: int, beta: int, ply: int = 0) -> int:
        if depth == 0:
            return self._quiescence(alpha, beta)

        # Transposition table probe
        original_alpha = alpha
        h = self._board.zobrist_hash
        entry = self._tt.get(h)
        tt_move: Optional[Move] = None
        if entry is not None and entry.depth >= depth:
            if entry.flag == TT_EXACT:
                return entry.score
            if entry.flag == TT_LOWER:
                alpha = max(alpha, entry.score)
            elif entry.flag == TT_UPPER:
                beta = min(beta, entry.score)
            if alpha >= beta:
                return entry.score
            tt_move = entry.best_move

        moves = self._order_moves(
            MoveGenerator(self._board).generate_legal_moves(),
            ply=ply,
            tt_move=tt_move,
        )

        if not moves:
            if self._board.is_in_check(self._board.side_to_move):
                return -(CHECKMATE_SCORE - ply)  # prefer faster mates
            return 0  # stalemate

        best = -INF
        best_move: Optional[Move] = None
        for move in moves:
            self._board.make_move(move)
            score = -self._negamax(depth - 1, -beta, -alpha, ply + 1)
            self._board.unmake_move()
            if score > best:
                best = score
                best_move = move
            alpha = max(alpha, score)
            if alpha >= beta:
                self._store_killer(move, ply)
                break

        # Transposition table store
        flag = TT_EXACT
        if best <= original_alpha:
            flag = TT_UPPER
        elif best >= beta:
            flag = TT_LOWER
        self._tt[h] = _TTEntry(depth=depth, score=best, flag=flag, best_move=best_move)

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

    def _order_moves(
        self,
        moves: list[Move],
        ply: int = 0,
        tt_move: Optional[Move] = None,
    ) -> list[Move]:
        return sorted(moves, key=lambda m: self._move_score(m, ply, tt_move), reverse=True)

    def _move_score(self, move: Move, ply: int = 0, tt_move: Optional[Move] = None) -> int:
        if tt_move is not None and move == tt_move:
            return 30_000  # TT/PV move — try first
        if move.flag == PROMOTION:
            return 20_000
        if move.is_capture(self._board):
            return 10_000 + self._mvv_lva_score(move)
        if move.flag == CASTLING:
            return 5_000
        # Killer moves: quiet moves that caused a beta cutoff at this ply before
        p = min(ply, _MAX_PLY - 1)
        if move == self._killers[p][0]:
            return 4_000
        if move == self._killers[p][1]:
            return 3_000
        return 0

    def _mvv_lva_score(self, move: Move) -> int:
        attacker = self._board.grid[move.from_sq[0]][move.from_sq[1]]
        if move.flag == EN_PASSANT:
            return PIECE_VALUES[PAWN]
        victim = self._board.grid[move.to_sq[0]][move.to_sq[1]]
        if victim is None or attacker is None:
            return 0
        return PIECE_VALUES[victim.piece_type] - PIECE_VALUES[attacker.piece_type] // 10

    def _store_killer(self, move: Move, ply: int) -> None:
        """Record a quiet move that caused a beta cutoff — useful for sibling nodes."""
        if move.is_capture(self._board) or move.flag == PROMOTION:
            return
        p = min(ply, _MAX_PLY - 1)
        if move != self._killers[p][0]:
            self._killers[p][1] = self._killers[p][0]
            self._killers[p][0] = move

    # ------------------------------------------------------------------
    # Display scoring (separate from main search for sidebar accuracy)
    # ------------------------------------------------------------------

    def _update_display_scores(self) -> None:
        """Score top candidates with independent full-window searches for distinct evals."""
        moves = self._order_moves(MoveGenerator(self._board).generate_legal_moves())
        if not moves:
            self._top_moves = []
            return
        sign = 1 if self._board.side_to_move == WHITE else -1
        display_depth = max(1, self._depth - 2)
        scored: list[tuple[int, Move]] = []
        for move in moves[:10]:
            self._board.make_move(move)
            score = -self._negamax(display_depth, -INF, INF, ply=1)
            self._board.unmake_move()
            scored.append((score, move))
        scored.sort(key=lambda x: -x[0])
        self._top_moves = [(m, s * sign) for s, m in scored[:5]]
