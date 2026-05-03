import pytest
from src.board import Board
from src.constants import WHITE, BLACK, PAWN, KNIGHT, QUEEN
from src.move import Move, NORMAL, DOUBLE_PUSH, CASTLING, EN_PASSANT, PROMOTION
from src.move_generator import MoveGenerator
from tests.conftest import perft


# ------------------------------------------------------------------
# Basics
# ------------------------------------------------------------------

def test_starting_position_has_20_moves(starting_board):
    moves = MoveGenerator(starting_board).generate_legal_moves()
    assert len(moves) == 20


def test_no_moves_when_checkmated(board_from_fen):
    b = board_from_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    moves = MoveGenerator(b).generate_legal_moves()
    assert len(moves) == 0


def test_side_to_move_respected(starting_board):
    # After the initial position it's White's turn — only white pieces should have moves
    moves = MoveGenerator(starting_board).generate_legal_moves()
    for m in moves:
        piece = starting_board.grid[m.from_sq[0]][m.from_sq[1]]
        assert piece is not None
        assert piece.color == WHITE


# ------------------------------------------------------------------
# Pawn moves
# ------------------------------------------------------------------

def test_pawn_double_push_from_start(board_from_fen):
    b = board_from_fen("8/8/8/8/8/8/4P3/8 w - - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    to_squares = {m.to_sq for m in moves}
    assert (4, 4) in to_squares  # e4 (double push)
    assert (5, 4) in to_squares  # e3 (single push)
    double = [m for m in moves if m.flag == DOUBLE_PUSH]
    assert len(double) == 1


def test_pawn_no_double_push_when_blocked(board_from_fen):
    b = board_from_fen("8/8/8/8/4p3/8/4P3/8 w - - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    # e3 is empty but e4 has black pawn — single push to e3 only
    double = [m for m in moves if m.flag == DOUBLE_PUSH]
    assert len(double) == 0


def test_pawn_captures_diagonally(board_from_fen):
    # White pawn e4, black pawns d5 and f5 — can capture both diagonally
    b = board_from_fen("8/8/8/3p1p2/4P3/8/8/8 w - - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    to_squares = {m.to_sq for m in moves}
    assert (3, 3) in to_squares  # exd5 (capture left)
    assert (3, 5) in to_squares  # exf5 (capture right)
    # e5 is also reachable as a single push — captures are a superset


def test_pawn_cannot_capture_friendly(board_from_fen):
    b = board_from_fen("8/8/8/3PP3/4P3/8/8/8 w - - 0 1")
    moves = [m for m in MoveGenerator(b).generate_legal_moves() if m.from_sq == (4, 4)]
    to_squares = {m.to_sq for m in moves}
    # e5 and d5 are white pawns — e-pawn is blocked, no diagonal captures
    assert (3, 3) not in to_squares
    assert (3, 5) not in to_squares


def test_pawn_promotion_generates_four_moves(board_from_fen):
    b = board_from_fen("8/4P3/8/8/8/8/8/8 w - - 0 1")
    moves = [m for m in MoveGenerator(b).generate_legal_moves() if m.flag == PROMOTION]
    assert len(moves) == 4
    promo_pieces = {m.promotion_piece for m in moves}
    assert promo_pieces == {KNIGHT, 2, 3, QUEEN}  # KNIGHT=1,BISHOP=2,ROOK=3,QUEEN=4


def test_pawn_promotion_capture_generates_four_moves(board_from_fen):
    b = board_from_fen("3r4/4P3/8/8/8/8/8/8 w - - 0 1")
    promo_moves = [m for m in MoveGenerator(b).generate_legal_moves() if m.flag == PROMOTION]
    # Can push to e8 (4 promos) and capture on d8 (4 promos) = 8 total
    assert len(promo_moves) == 8


def test_en_passant_capture_generated(board_from_fen):
    b = board_from_fen("8/8/8/3pP3/8/8/8/8 w - d6 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    ep_moves = [m for m in moves if m.flag == EN_PASSANT]
    assert len(ep_moves) == 1
    assert ep_moves[0].to_sq == (2, 3)


def test_en_passant_not_generated_without_target(board_from_fen):
    b = board_from_fen("8/8/8/3pP3/8/8/8/8 w - - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    ep_moves = [m for m in moves if m.flag == EN_PASSANT]
    assert len(ep_moves) == 0


# ------------------------------------------------------------------
# Knight moves
# ------------------------------------------------------------------

def test_knight_in_corner_has_two_moves(board_from_fen):
    b = board_from_fen("N7/8/8/8/8/8/8/8 w - - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    assert len(moves) == 2


def test_knight_in_center_has_eight_moves(board_from_fen):
    b = board_from_fen("8/8/8/3N4/8/8/8/8 w - - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    assert len(moves) == 8


# ------------------------------------------------------------------
# Castling
# ------------------------------------------------------------------

def test_kingside_castle_generated(board_from_fen):
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    castle_moves = [m for m in moves if m.flag == CASTLING and m.to_sq == (7, 6)]
    assert len(castle_moves) == 1


def test_queenside_castle_generated(board_from_fen):
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    castle_moves = [m for m in moves if m.flag == CASTLING and m.to_sq == (7, 2)]
    assert len(castle_moves) == 1


def test_castle_not_generated_when_in_check(board_from_fen):
    # White king in check from black rook on e-file — cannot castle
    b = board_from_fen("4r3/8/8/8/8/8/8/R3K2R w KQ - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    castle_moves = [m for m in moves if m.flag == CASTLING]
    assert len(castle_moves) == 0


def test_castle_not_generated_through_attacked_square(board_from_fen):
    # f1 attacked by black rook — kingside castle forbidden
    b = board_from_fen("5r2/8/8/8/8/8/8/R3K2R w KQ - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    ks_castles = [m for m in moves if m.flag == CASTLING and m.to_sq == (7, 6)]
    assert len(ks_castles) == 0


def test_castle_not_generated_when_path_blocked(board_from_fen):
    b = board_from_fen("r3k2r/8/8/8/8/8/8/RN2K2R w KQkq - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    qs_castles = [m for m in moves if m.flag == CASTLING and m.to_sq == (7, 2)]
    assert len(qs_castles) == 0


def test_castle_not_generated_after_king_moved(board_from_fen):
    from src.constants import CASTLE_WHITE_KINGSIDE, CASTLE_WHITE_QUEENSIDE
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.make_move(Move((7, 4), (7, 5)))   # king moves
    b.make_move(Move((0, 4), (0, 5)))   # black king moves (just to flip side)
    b.make_move(Move((7, 5), (7, 4)))   # king moves back
    b.make_move(Move((0, 5), (0, 4)))
    moves = MoveGenerator(b).generate_legal_moves()
    castle_moves = [m for m in moves if m.flag == CASTLING]
    assert len(castle_moves) == 0


def test_castle_not_generated_after_rook_moved(board_from_fen):
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.make_move(Move((7, 7), (7, 6)))   # rook moves
    b.make_move(Move((0, 0), (0, 1)))   # black rook moves
    moves = MoveGenerator(b).generate_legal_moves()
    ks_castles = [m for m in moves if m.flag == CASTLING and m.to_sq == (7, 6)]
    assert len(ks_castles) == 0


# ------------------------------------------------------------------
# Legal move correctness (pin / check)
# ------------------------------------------------------------------

def test_pinned_piece_cannot_expose_king(board_from_fen):
    # White rook on e2 is pinned to white king on e1 by black rook on e8
    b = board_from_fen("4r3/8/8/8/8/8/4R3/4K3 w - - 0 1")
    moves = [m for m in MoveGenerator(b).generate_legal_moves() if m.from_sq == (6, 4)]
    # The rook can only move along the e-file (can't move off it)
    for m in moves:
        assert m.to_sq[1] == 4


def test_only_legal_moves_when_in_check(board_from_fen):
    # White king in check, must block or move
    b = board_from_fen("4r3/8/8/8/8/8/8/4K3 w - - 0 1")
    moves = MoveGenerator(b).generate_legal_moves()
    # Apply each move and verify king is no longer in check
    for m in moves:
        b.make_move(m)
        assert not b.is_in_check(WHITE)
        b.unmake_move()


# ------------------------------------------------------------------
# Perft — ground truth validation
# ------------------------------------------------------------------

def test_perft_depth_1(starting_board):
    assert perft(starting_board, 1) == 20


def test_perft_depth_2(starting_board):
    assert perft(starting_board, 2) == 400


def test_perft_depth_3(starting_board):
    assert perft(starting_board, 3) == 8902
