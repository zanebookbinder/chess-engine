from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from src.constants import (
    WHITE, BLACK, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    CASTLE_WHITE_KINGSIDE, CASTLE_WHITE_QUEENSIDE,
    CASTLE_BLACK_KINGSIDE, CASTLE_BLACK_QUEENSIDE, CASTLE_ALL,
    CASTLING_RIGHTS_REVOCATION, CASTLING_ROOK_SQUARES, CASTLING_KING_DEST,
    FEN_PIECE_MAP, PIECE_SYMBOLS, on_board,
)
from src.piece import Piece, make_piece
from src.move import Move, NORMAL, DOUBLE_PUSH, CASTLING, EN_PASSANT, PROMOTION


@dataclass
class BoardSnapshot:
    move: Move
    captured_piece: Optional[Piece]
    captured_square: Optional[tuple[int, int]]  # differs from to_sq for en passant
    castling_rights_before: int
    en_passant_target_before: Optional[tuple[int, int]]
    halfmove_clock_before: int


class Board:
    def __init__(self) -> None:
        self.grid: list[list[Optional[Piece]]] = [[None] * 8 for _ in range(8)]
        self.side_to_move: int = WHITE
        self.castling_rights: int = CASTLE_ALL
        self.en_passant_target: Optional[tuple[int, int]] = None
        self.halfmove_clock: int = 0
        self.fullmove_number: int = 1
        self._history: list[BoardSnapshot] = []

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_starting_position(self) -> None:
        self.grid = [[None] * 8 for _ in range(8)]
        back_rank = [ROOK, KNIGHT, BISHOP, QUEEN, KING, BISHOP, KNIGHT, ROOK]
        for file, pt in enumerate(back_rank):
            self.grid[0][file] = make_piece(pt, BLACK)
            self.grid[7][file] = make_piece(pt, WHITE)
        for file in range(8):
            self.grid[1][file] = make_piece(PAWN, BLACK)
            self.grid[6][file] = make_piece(PAWN, WHITE)
        self.side_to_move = WHITE
        self.castling_rights = CASTLE_ALL
        self.en_passant_target = None
        self.halfmove_clock = 0
        self.fullmove_number = 1
        self._history = []

    @classmethod
    def from_fen(cls, fen: str) -> "Board":
        board = cls()
        board.grid = [[None] * 8 for _ in range(8)]
        parts = fen.split()
        # Piece placement
        rank = 0
        file = 0
        for ch in parts[0]:
            if ch == "/":
                rank += 1
                file = 0
            elif ch.isdigit():
                file += int(ch)
            else:
                color, piece_type = FEN_PIECE_MAP[ch]
                board.grid[rank][file] = make_piece(piece_type, color)
                file += 1
        # Side to move
        board.side_to_move = WHITE if parts[1] == "w" else BLACK
        # Castling rights
        board.castling_rights = 0
        if "K" in parts[2]: board.castling_rights |= CASTLE_WHITE_KINGSIDE
        if "Q" in parts[2]: board.castling_rights |= CASTLE_WHITE_QUEENSIDE
        if "k" in parts[2]: board.castling_rights |= CASTLE_BLACK_KINGSIDE
        if "q" in parts[2]: board.castling_rights |= CASTLE_BLACK_QUEENSIDE
        # En passant target
        if parts[3] != "-":
            files = "abcdefgh"
            ranks = "87654321"
            ep_file = files.index(parts[3][0])
            ep_rank = ranks.index(parts[3][1])
            board.en_passant_target = (ep_rank, ep_file)
        else:
            board.en_passant_target = None
        board.halfmove_clock  = int(parts[4]) if len(parts) > 4 else 0
        board.fullmove_number = int(parts[5]) if len(parts) > 5 else 1
        board._history = []
        return board

    def to_fen(self) -> str:
        rows = []
        for rank in range(8):
            empty = 0
            row = ""
            for file in range(8):
                p = self.grid[rank][file]
                if p is None:
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += p.symbol
            if empty:
                row += str(empty)
            rows.append(row)
        placement = "/".join(rows)

        side = "w" if self.side_to_move == WHITE else "b"

        castling = ""
        if self.castling_rights & CASTLE_WHITE_KINGSIDE:  castling += "K"
        if self.castling_rights & CASTLE_WHITE_QUEENSIDE: castling += "Q"
        if self.castling_rights & CASTLE_BLACK_KINGSIDE:  castling += "k"
        if self.castling_rights & CASTLE_BLACK_QUEENSIDE: castling += "q"
        if not castling:
            castling = "-"

        if self.en_passant_target:
            files = "abcdefgh"
            ranks = "87654321"
            ep_r, ep_f = self.en_passant_target
            ep = files[ep_f] + ranks[ep_r]
        else:
            ep = "-"

        return f"{placement} {side} {castling} {ep} {self.halfmove_clock} {self.fullmove_number}"

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_piece(self, rank: int, file: int) -> Optional[Piece]:
        return self.grid[rank][file]

    def set_piece(self, rank: int, file: int, piece: Optional[Piece]) -> None:
        self.grid[rank][file] = piece

    def find_king(self, color: int) -> tuple[int, int]:
        for rank in range(8):
            for file in range(8):
                p = self.grid[rank][file]
                if p is not None and p.piece_type == KING and p.color == color:
                    return (rank, file)
        raise ValueError(f"King not found for color {color}")

    def copy(self) -> "Board":
        b = Board()
        b.grid = [[self.grid[r][f] for f in range(8)] for r in range(8)]
        b.side_to_move = self.side_to_move
        b.castling_rights = self.castling_rights
        b.en_passant_target = self.en_passant_target
        b.halfmove_clock = self.halfmove_clock
        b.fullmove_number = self.fullmove_number
        b._history = list(self._history)
        return b

    # ------------------------------------------------------------------
    # Move execution
    # ------------------------------------------------------------------

    def make_move(self, move: Move) -> None:
        fr, ff = move.from_sq
        tr, tf = move.to_sq
        piece = self.grid[fr][ff]

        captured_piece: Optional[Piece] = self.grid[tr][tf]
        captured_square: Optional[tuple[int, int]] = (tr, tf) if captured_piece else None

        snapshot = BoardSnapshot(
            move=move,
            captured_piece=captured_piece,
            captured_square=captured_square,
            castling_rights_before=self.castling_rights,
            en_passant_target_before=self.en_passant_target,
            halfmove_clock_before=self.halfmove_clock,
        )

        # Reset en passant target (will be set below if double push)
        self.en_passant_target = None

        if move.flag == EN_PASSANT:
            # Captured pawn is behind the destination square
            cap_rank = fr  # same rank as capturing pawn
            cap_file = tf
            snapshot.captured_piece = self.grid[cap_rank][cap_file]
            snapshot.captured_square = (cap_rank, cap_file)
            self.grid[cap_rank][cap_file] = None
            captured_piece = snapshot.captured_piece

        elif move.flag == CASTLING:
            kingside = tf > ff
            rook_src, rook_dst = CASTLING_ROOK_SQUARES[(piece.color, kingside)]
            self.grid[rook_dst[0]][rook_dst[1]] = self.grid[rook_src[0]][rook_src[1]]
            self.grid[rook_src[0]][rook_src[1]] = None

        elif move.flag == PROMOTION:
            piece = make_piece(move.promotion_piece, piece.color)

        # Move piece
        self.grid[tr][tf] = piece
        self.grid[fr][ff] = None

        # Set en passant target for double pawn push
        if move.flag == DOUBLE_PUSH:
            ep_rank = (fr + tr) // 2
            self.en_passant_target = (ep_rank, ff)

        # Update castling rights: revoke bits for any piece that moved from/to a key square
        for sq in (move.from_sq, move.to_sq):
            if sq in CASTLING_RIGHTS_REVOCATION:
                self.castling_rights &= ~CASTLING_RIGHTS_REVOCATION[sq]

        # Halfmove clock
        if piece.piece_type == PAWN or captured_piece is not None:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        if self.side_to_move == BLACK:
            self.fullmove_number += 1

        self.side_to_move ^= 1
        self._history.append(snapshot)

    def unmake_move(self) -> None:
        snapshot = self._history.pop()
        move = snapshot.move
        fr, ff = move.from_sq
        tr, tf = move.to_sq

        self.side_to_move ^= 1
        if self.side_to_move == BLACK:
            self.fullmove_number -= 1

        self.castling_rights = snapshot.castling_rights_before
        self.en_passant_target = snapshot.en_passant_target_before
        self.halfmove_clock = snapshot.halfmove_clock_before

        # Retrieve the piece now at to_sq (may have been promoted)
        moved_piece = self.grid[tr][tf]

        if move.flag == PROMOTION:
            # Restore the original pawn
            moved_piece = make_piece(PAWN, self.side_to_move)

        # Restore moving piece to from_sq
        self.grid[fr][ff] = moved_piece
        self.grid[tr][tf] = None

        # Restore captured piece
        if snapshot.captured_square is not None:
            self.grid[snapshot.captured_square[0]][snapshot.captured_square[1]] = snapshot.captured_piece

        if move.flag == CASTLING:
            kingside = tf > ff
            rook_src, rook_dst = CASTLING_ROOK_SQUARES[(self.side_to_move, kingside)]
            self.grid[rook_src[0]][rook_src[1]] = self.grid[rook_dst[0]][rook_dst[1]]
            self.grid[rook_dst[0]][rook_dst[1]] = None

    # ------------------------------------------------------------------
    # Attack detection
    # ------------------------------------------------------------------

    def is_square_attacked(self, rank: int, file: int, by_color: int) -> bool:
        """Return True if any piece of by_color attacks (rank, file)."""
        opp = by_color

        # Knight attacks
        for dr, df in [(-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)]:
            r, f = rank + dr, file + df
            if on_board(r, f):
                p = self.grid[r][f]
                if p is not None and p.color == opp and p.piece_type == KNIGHT:
                    return True

        # Diagonal rays (bishop / queen)
        for dr, df in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            r, f = rank + dr, file + df
            while on_board(r, f):
                p = self.grid[r][f]
                if p is not None:
                    if p.color == opp and p.piece_type in (BISHOP, QUEEN):
                        return True
                    break
                r += dr; f += df

        # Orthogonal rays (rook / queen)
        for dr, df in [(-1,0),(1,0),(0,-1),(0,1)]:
            r, f = rank + dr, file + df
            while on_board(r, f):
                p = self.grid[r][f]
                if p is not None:
                    if p.color == opp and p.piece_type in (ROOK, QUEEN):
                        return True
                    break
                r += dr; f += df

        # Pawn attacks — pawns of by_color attack downward (BLACK) or upward (WHITE)
        pawn_dir = 1 if opp == WHITE else -1  # direction from pawn toward this square
        for df in (-1, 1):
            r, f = rank + pawn_dir, file + df
            if on_board(r, f):
                p = self.grid[r][f]
                if p is not None and p.color == opp and p.piece_type == PAWN:
                    return True

        # King attacks
        for dr in (-1, 0, 1):
            for df in (-1, 0, 1):
                if dr == 0 and df == 0:
                    continue
                r, f = rank + dr, file + df
                if on_board(r, f):
                    p = self.grid[r][f]
                    if p is not None and p.color == opp and p.piece_type == KING:
                        return True

        return False

    def is_in_check(self, color: int) -> bool:
        try:
            kr, kf = self.find_king(color)
        except ValueError:
            return False  # no king on board (simplified test positions)
        return self.is_square_attacked(kr, kf, by_color=color ^ 1)

    def is_checkmate(self, color: int) -> bool:
        if not self.is_in_check(color):
            return False
        from src.move_generator import MoveGenerator
        return len(MoveGenerator(self).generate_legal_moves()) == 0

    def is_stalemate(self, color: int) -> bool:
        if self.is_in_check(color):
            return False
        from src.move_generator import MoveGenerator
        return len(MoveGenerator(self).generate_legal_moves()) == 0

    def is_draw_by_fifty_moves(self) -> bool:
        return self.halfmove_clock >= 100

    def is_game_over(self) -> tuple[bool, Optional[int]]:
        color = self.side_to_move
        if self.is_checkmate(color):
            return True, color ^ 1
        if self.is_stalemate(color):
            return True, None
        if self.is_draw_by_fifty_moves():
            return True, None
        return False, None

    def __repr__(self) -> str:
        rows = []
        for rank in range(8):
            row = ""
            for file in range(8):
                p = self.grid[rank][file]
                row += (p.symbol if p else ".") + " "
            rows.append(row.strip())
        return "\n".join(rows)
