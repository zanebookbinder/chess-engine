from __future__ import annotations
from typing import TYPE_CHECKING

from src.constants import (
    WHITE, BLACK, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    PIECE_VALUES, ENDGAME_MATERIAL_THRESHOLD,
    PAWN_PST, KNIGHT_PST, BISHOP_PST, ROOK_PST, QUEEN_PST,
    KING_MG_PST, KING_EG_PST, on_board,
    PASSED_PAWN_BONUS, DOUBLED_PAWN_PENALTY, ISOLATED_PAWN_PENALTY,
    BISHOP_PAIR_BONUS, ROOK_OPEN_FILE_BONUS, ROOK_SEMI_OPEN_FILE_BONUS,
    ROOK_SEVENTH_RANK_BONUS, MOBILITY_BONUS,
)

if TYPE_CHECKING:
    from src.board import Board

_PIECE_PST = [PAWN_PST, KNIGHT_PST, BISHOP_PST, ROOK_PST, QUEEN_PST, None]

PAWN_SHIELD_BONUS      =  10
PAWN_SHIELD_PENALTY    = -20
OPEN_FILE_PENALTY      = -25
HALF_OPEN_FILE_PENALTY = -10

_BISHOP_DIRS   = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_ROOK_DIRS     = [(-1,  0), ( 1, 0), (0, -1), (0,  1)]
_KNIGHT_OFFSETS = [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]


class Evaluator:
    def __init__(self, board: "Board") -> None:
        self._board = board

    def evaluate(self) -> int:
        """Return centipawn evaluation from White's perspective.

        Single-pass over the board to collect all piece data, then compute
        pawn-structure and king-safety terms separately (they need global
        file information that can't be determined piece-by-piece).
        """
        grid = self._board.grid

        # --- Endgame flag (cheap pre-scan) ---
        non_pawn_mat = 0
        for rank in range(8):
            for file in range(8):
                p = grid[rank][file]
                if p is not None and p.piece_type not in (PAWN, KING):
                    non_pawn_mat += PIECE_VALUES[p.piece_type]
        endgame = non_pawn_mat < ENDGAME_MATERIAL_THRESHOLD

        # --- Main pass: material + PST + mobility ---
        score = 0
        w_pawns: list[list[int]] = [[] for _ in range(8)]  # w_pawns[file] = [ranks]
        b_pawns: list[list[int]] = [[] for _ in range(8)]
        w_bishops = 0
        b_bishops = 0
        rooks: list[tuple[int, int, int]] = []  # (rank, file, color) for rook-file bonus

        for rank in range(8):
            for file in range(8):
                p = grid[rank][file]
                if p is None:
                    continue

                pt = p.piece_type
                color = p.color
                sign = 1 if color == WHITE else -1

                # Material
                score += sign * PIECE_VALUES[pt]

                # PST
                lr = rank if color == WHITE else (7 - rank)
                if pt == KING:
                    table = KING_EG_PST if endgame else KING_MG_PST
                else:
                    table = _PIECE_PST[pt]
                score += sign * table[lr][file]

                # Per-piece extras
                if pt == PAWN:
                    (w_pawns if color == WHITE else b_pawns)[file].append(rank)

                elif pt == KNIGHT:
                    mob = 0
                    for dr, df in _KNIGHT_OFFSETS:
                        r2, f2 = rank + dr, file + df
                        if on_board(r2, f2):
                            q = grid[r2][f2]
                            if q is None or q.color != color:
                                mob += 1
                    score += sign * mob * MOBILITY_BONUS

                elif pt == BISHOP:
                    if color == WHITE:
                        w_bishops += 1
                    else:
                        b_bishops += 1
                    score += sign * _sliding_mobility(grid, rank, file, color, _BISHOP_DIRS) * MOBILITY_BONUS

                elif pt == ROOK:
                    score += sign * _sliding_mobility(grid, rank, file, color, _ROOK_DIRS) * MOBILITY_BONUS
                    rooks.append((rank, file, color))

        # Bishop pair
        if w_bishops >= 2:
            score += BISHOP_PAIR_BONUS
        if b_bishops >= 2:
            score -= BISHOP_PAIR_BONUS

        # Rook file/rank bonuses (needs full pawn data collected above)
        for rank, file, color in rooks:
            sign = 1 if color == WHITE else -1
            own_p = w_pawns if color == WHITE else b_pawns
            opp_p = b_pawns if color == WHITE else w_pawns
            own_pawn_on_file = bool(own_p[file])
            opp_pawn_on_file = bool(opp_p[file])
            if not own_pawn_on_file:
                score += sign * (ROOK_OPEN_FILE_BONUS if not opp_pawn_on_file else ROOK_SEMI_OPEN_FILE_BONUS)
            seventh = 1 if color == WHITE else 6
            if rank == seventh:
                score += sign * ROOK_SEVENTH_RANK_BONUS

        # Pawn structure
        score += _pawn_structure(w_pawns, b_pawns, WHITE)
        score -= _pawn_structure(b_pawns, w_pawns, BLACK)

        # King safety
        score += _king_safety(grid, self._board, WHITE)
        score -= _king_safety(grid, self._board, BLACK)

        return score

    # Expose component scores for tests
    def _material_score(self) -> int:
        s = 0
        for rank in range(8):
            for file in range(8):
                p = self._board.grid[rank][file]
                if p:
                    s += PIECE_VALUES[p.piece_type] * (1 if p.color == WHITE else -1)
        return s

    def _pst_score(self) -> int:
        endgame = self._is_endgame()
        s = 0
        for rank in range(8):
            for file in range(8):
                p = self._board.grid[rank][file]
                if p is None:
                    continue
                lr = rank if p.color == WHITE else (7 - rank)
                table = (KING_EG_PST if endgame else KING_MG_PST) if p.piece_type == KING else _PIECE_PST[p.piece_type]
                s += table[lr][file] * (1 if p.color == WHITE else -1)
        return s

    def _is_endgame(self) -> bool:
        total = 0
        for rank in range(8):
            for file in range(8):
                p = self._board.grid[rank][file]
                if p is not None and p.piece_type not in (PAWN, KING):
                    total += PIECE_VALUES[p.piece_type]
        return total < ENDGAME_MATERIAL_THRESHOLD

    def _pawn_structure_score(self) -> int:
        w_pawns: list[list[int]] = [[] for _ in range(8)]
        b_pawns: list[list[int]] = [[] for _ in range(8)]
        for rank in range(8):
            for file in range(8):
                p = self._board.grid[rank][file]
                if p and p.piece_type == PAWN:
                    (w_pawns if p.color == WHITE else b_pawns)[file].append(rank)
        return _pawn_structure(w_pawns, b_pawns, WHITE) - _pawn_structure(b_pawns, w_pawns, BLACK)

    def _king_safety_score(self) -> int:
        return (
            _king_safety(self._board.grid, self._board, WHITE)
            - _king_safety(self._board.grid, self._board, BLACK)
        )

    def _pawn_shield_score(self, color: int) -> int:
        try:
            kr, kf = self._board.find_king(color)
        except ValueError:
            return 0
        direction = -1 if color == WHITE else 1
        score = 0
        for df in (-1, 0, 1):
            f = kf + df
            if not on_board(0, f):
                continue
            shield_rank = kr + direction
            if not on_board(shield_rank, f):
                continue
            p = self._board.grid[shield_rank][f]
            if p is not None and p.color == color and p.piece_type == PAWN:
                score += PAWN_SHIELD_BONUS
            else:
                score += PAWN_SHIELD_PENALTY
        return score

    def _open_file_near_king_penalty(self, color: int) -> int:
        try:
            _, kf = self._board.find_king(color)
        except ValueError:
            return 0
        opp = color ^ 1
        score = 0
        for df in (-1, 0, 1):
            f = kf + df
            if not on_board(0, f):
                continue
            friendly_pawn = False
            enemy_rook_queen = False
            for rank in range(8):
                p = self._board.grid[rank][f]
                if p is None:
                    continue
                if p.color == color and p.piece_type == PAWN:
                    friendly_pawn = True
                if p.color == opp and p.piece_type in (ROOK, QUEEN):
                    enemy_rook_queen = True
            if not friendly_pawn:
                score += OPEN_FILE_PENALTY if enemy_rook_queen else HALF_OPEN_FILE_PENALTY
        return score

    def _activity_for(self, color: int) -> int:
        """For test compatibility."""
        score = 0
        bishops = 0
        grid = self._board.grid
        for rank in range(8):
            for file in range(8):
                p = grid[rank][file]
                if p is None or p.color != color:
                    continue
                pt = p.piece_type
                if pt == BISHOP:
                    bishops += 1
                    score += _sliding_mobility(grid, rank, file, color, _BISHOP_DIRS) * MOBILITY_BONUS
                elif pt == KNIGHT:
                    mob = sum(
                        1 for dr, df in _KNIGHT_OFFSETS
                        if on_board(rank + dr, file + df)
                        and (grid[rank+dr][file+df] is None or grid[rank+dr][file+df].color != color)
                    )
                    score += mob * MOBILITY_BONUS
                elif pt == ROOK:
                    score += _sliding_mobility(grid, rank, file, color, _ROOK_DIRS) * MOBILITY_BONUS
        if bishops >= 2:
            score += BISHOP_PAIR_BONUS
        return score

    def _rook_file_bonus(self, rank: int, file: int, color: int) -> int:
        """For test compatibility."""
        own_pawn = any(
            self._board.grid[r][file] is not None
            and self._board.grid[r][file].piece_type == PAWN
            and self._board.grid[r][file].color == color
            for r in range(8)
        )
        opp_pawn = any(
            self._board.grid[r][file] is not None
            and self._board.grid[r][file].piece_type == PAWN
            and self._board.grid[r][file].color != color
            for r in range(8)
        )
        score = 0
        if not own_pawn:
            score += ROOK_OPEN_FILE_BONUS if not opp_pawn else ROOK_SEMI_OPEN_FILE_BONUS
        seventh = 1 if color == WHITE else 6
        if rank == seventh:
            score += ROOK_SEVENTH_RANK_BONUS
        return score


# ---------------------------------------------------------------------------
# Module-level helpers (avoid method call overhead in the hot loop)
# ---------------------------------------------------------------------------

def _sliding_mobility(
    grid: list,
    rank: int,
    file: int,
    color: int,
    directions: list[tuple[int, int]],
) -> int:
    count = 0
    for dr, df in directions:
        r, f = rank + dr, file + df
        while on_board(r, f):
            q = grid[r][f]
            if q is None:
                count += 1
            elif q.color != color:
                count += 1
                break
            else:
                break
            r += dr
            f += df
    return count


def _pawn_structure(
    own: list[list[int]],
    opp: list[list[int]],
    color: int,
) -> int:
    """Score pawn structure terms for one color (from that color's perspective)."""
    score = 0
    for file in range(8):
        if not own[file]:
            continue
        n = len(own[file])

        # Doubled
        if n > 1:
            score += DOUBLED_PAWN_PENALTY * (n - 1)

        # Isolated
        if not ((file > 0 and own[file - 1]) or (file < 7 and own[file + 1])):
            score += ISOLATED_PAWN_PENALTY * n

        # Passed
        for rank in own[file]:
            lr = rank if color == WHITE else (7 - rank)
            if _is_passed(rank, file, color, opp):
                score += PASSED_PAWN_BONUS[lr]

    return score


def _is_passed(rank: int, file: int, color: int, opp: list[list[int]]) -> bool:
    for f in range(max(0, file - 1), min(8, file + 2)):
        for opp_rank in opp[f]:
            if color == WHITE:
                if opp_rank < rank:
                    return False
            else:
                if opp_rank > rank:
                    return False
    return True


def _king_safety(grid: list, board, color: int) -> int:
    try:
        kr, kf = board.find_king(color)
    except ValueError:
        return 0
    direction = -1 if color == WHITE else 1
    opp = color ^ 1

    # Pawn shield
    shield = 0
    for df in (-1, 0, 1):
        f = kf + df
        if not on_board(0, f):
            continue
        sr = kr + direction
        if not on_board(sr, f):
            continue
        p = grid[sr][f]
        if p is not None and p.color == color and p.piece_type == PAWN:
            shield += PAWN_SHIELD_BONUS
        else:
            shield += PAWN_SHIELD_PENALTY

    # Open-file penalty near king
    open_pen = 0
    for df in (-1, 0, 1):
        f = kf + df
        if not on_board(0, f):
            continue
        friendly_pawn = False
        enemy_rq = False
        for r in range(8):
            p = grid[r][f]
            if p is None:
                continue
            if p.color == color and p.piece_type == PAWN:
                friendly_pawn = True
            if p.color == opp and p.piece_type in (ROOK, QUEEN):
                enemy_rq = True
        if not friendly_pawn:
            open_pen += OPEN_FILE_PENALTY if enemy_rq else HALF_OPEN_FILE_PENALTY

    return shield + open_pen
