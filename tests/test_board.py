import pytest
from src.board import Board
from src.constants import WHITE, BLACK, PAWN, KNIGHT, ROOK, QUEEN, KING
from src.move import Move, NORMAL, DOUBLE_PUSH, CASTLING, EN_PASSANT, PROMOTION
from src.move_generator import MoveGenerator
from src.piece import make_piece


# ------------------------------------------------------------------
# Setup / initial state
# ------------------------------------------------------------------

def test_starting_position_piece_count(starting_board):
    count = sum(
        1 for r in range(8) for f in range(8)
        if starting_board.grid[r][f] is not None
    )
    assert count == 32


def test_starting_position_fen_roundtrip(starting_board):
    fen = starting_board.to_fen()
    restored = Board.from_fen(fen)
    assert restored.to_fen() == fen


def test_starting_fen_is_standard(starting_board):
    assert starting_board.to_fen().startswith(
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
    )


def test_empty_board_has_no_pieces(empty_board):
    for r in range(8):
        for f in range(8):
            assert empty_board.grid[r][f] is None


# ------------------------------------------------------------------
# make_move basics
# ------------------------------------------------------------------

def test_make_move_pawn_single_push(starting_board):
    move = Move((6, 4), (5, 4))  # e2-e3
    starting_board.make_move(move)
    assert starting_board.grid[5][4] is not None
    assert starting_board.grid[6][4] is None


def test_make_move_updates_side_to_move(starting_board):
    assert starting_board.side_to_move == WHITE
    starting_board.make_move(Move((6, 4), (4, 4), DOUBLE_PUSH))
    assert starting_board.side_to_move == BLACK


def test_double_push_sets_en_passant_target(starting_board):
    starting_board.make_move(Move((6, 4), (4, 4), DOUBLE_PUSH))  # e2-e4
    assert starting_board.en_passant_target == (5, 4)


def test_non_double_push_clears_ep_target(board_from_fen):
    b = board_from_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
    assert b.en_passant_target == (5, 4)
    b.make_move(Move((1, 4), (2, 4)))  # e7-e6 (single push)
    assert b.en_passant_target is None


# ------------------------------------------------------------------
# unmake_move
# ------------------------------------------------------------------

def test_unmake_move_restores_piece(starting_board):
    original_fen = starting_board.to_fen()
    starting_board.make_move(Move((6, 4), (4, 4), DOUBLE_PUSH))
    starting_board.unmake_move()
    assert starting_board.to_fen() == original_fen


def test_unmake_move_restores_capture(board_from_fen):
    # Scholar's mate setup, but just test a capture-unmake
    b = board_from_fen("8/8/8/3p4/4P3/8/8/8 w - - 0 1")
    original_fen = b.to_fen()
    b.make_move(Move((4, 4), (3, 3)))  # exd5
    assert b.grid[3][3] is not None
    assert b.grid[4][4] is None
    b.unmake_move()
    assert b.to_fen() == original_fen


def test_unmake_sequence_leaves_board_unchanged(starting_board):
    original_fen = starting_board.to_fen()
    moves = [
        Move((6, 4), (4, 4), DOUBLE_PUSH),
        Move((1, 4), (3, 4), DOUBLE_PUSH),
        Move((7, 6), (5, 5)),
        Move((0, 6), (2, 5)),
    ]
    for m in moves:
        starting_board.make_move(m)
    for _ in moves:
        starting_board.unmake_move()
    assert starting_board.to_fen() == original_fen


def test_unmake_restores_en_passant_target(board_from_fen):
    b = board_from_fen("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1")
    ep_before = b.en_passant_target
    b.make_move(Move((1, 0), (2, 0)))  # a7-a6
    b.unmake_move()
    assert b.en_passant_target == ep_before


def test_unmake_restores_castling_rights(board_from_fen):
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    rights_before = b.castling_rights
    b.make_move(Move((7, 4), (7, 6), CASTLING))  # White kingside castle
    b.unmake_move()
    assert b.castling_rights == rights_before


# ------------------------------------------------------------------
# Castling rights revocation
# ------------------------------------------------------------------

def test_king_move_revokes_both_rights(board_from_fen):
    from src.constants import CASTLE_WHITE_KINGSIDE, CASTLE_WHITE_QUEENSIDE
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.make_move(Move((7, 4), (7, 5)))  # Kf1 (king moves)
    assert not (b.castling_rights & CASTLE_WHITE_KINGSIDE)
    assert not (b.castling_rights & CASTLE_WHITE_QUEENSIDE)


def test_rook_move_revokes_kingside_right(board_from_fen):
    from src.constants import CASTLE_WHITE_KINGSIDE
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.make_move(Move((7, 7), (7, 6)))  # Rh1-g1
    assert not (b.castling_rights & CASTLE_WHITE_KINGSIDE)


def test_rook_captured_revokes_right(board_from_fen):
    from src.constants import CASTLE_BLACK_KINGSIDE
    # Black rook on h8 gets captured
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.castling_rights = 0b1111  # all rights
    # Manually place a white rook on h7 so it can capture h8
    b.grid[1][7] = make_piece(ROOK, WHITE)
    b.make_move(Move((1, 7), (0, 7)))  # captures on h8
    assert not (b.castling_rights & CASTLE_BLACK_KINGSIDE)


# ------------------------------------------------------------------
# Check detection
# ------------------------------------------------------------------

def test_king_in_check_by_rook(board_from_fen):
    # Rook on e1 already attacks the black king on e8 — check is active
    b = board_from_fen("4k3/8/8/8/8/8/8/4KR2 w - - 0 1")
    # Move Rf1-e1 to align with king on e-file
    b.make_move(Move((7, 5), (7, 4)))  # Rf1-e1
    # It's now Black's turn — Black king is in check from white rook on e1
    assert b.is_in_check(BLACK)


def test_king_not_in_check_when_blocked(board_from_fen):
    # White rook on e1, black pawn on e6, black king on e8 — rook is blocked
    b = board_from_fen("4k3/8/4p3/8/8/8/8/4KR2 w - - 0 1")
    assert not b.is_in_check(BLACK)


def test_is_not_in_check_at_start(starting_board):
    assert not starting_board.is_in_check(WHITE)
    assert not starting_board.is_in_check(BLACK)


# ------------------------------------------------------------------
# Checkmate
# ------------------------------------------------------------------

def test_fools_mate_is_checkmate(board_from_fen):
    # Fool's mate: 1.f3 e5 2.g4 Qh4#
    b = board_from_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert b.is_in_check(WHITE)
    assert b.is_checkmate(WHITE)


def test_scholars_mate_is_checkmate(board_from_fen):
    # Scholar's mate position
    b = board_from_fen("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4")
    assert b.is_in_check(BLACK)
    assert b.is_checkmate(BLACK)


# ------------------------------------------------------------------
# Stalemate
# ------------------------------------------------------------------

def test_stalemate_detected(board_from_fen):
    # Classic stalemate: Black king trapped in corner with no legal moves
    b = board_from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert not b.is_in_check(BLACK)
    assert b.is_stalemate(BLACK)


def test_checkmate_is_not_stalemate(board_from_fen):
    b = board_from_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert b.is_checkmate(WHITE)
    assert not b.is_stalemate(WHITE)


# ------------------------------------------------------------------
# Game over
# ------------------------------------------------------------------

def test_game_not_over_at_start(starting_board):
    over, _ = starting_board.is_game_over()
    assert not over


def test_game_over_on_checkmate(board_from_fen):
    b = board_from_fen("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    over, winner = b.is_game_over()
    assert over
    assert winner == BLACK


def test_game_over_on_stalemate(board_from_fen):
    b = board_from_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    over, winner = b.is_game_over()
    assert over
    assert winner is None


# ------------------------------------------------------------------
# is_square_attacked
# ------------------------------------------------------------------

def test_square_attacked_by_knight(board_from_fen):
    b = board_from_fen("8/8/8/8/3N4/8/8/8 w - - 0 1")
    # White knight on d4 (rank 4, file 3) attacks c6, e6, b5, f5, b3, f3, c2, e2
    assert b.is_square_attacked(2, 2, WHITE)   # c6
    assert b.is_square_attacked(2, 4, WHITE)   # e6
    assert not b.is_square_attacked(4, 3, WHITE)  # d4 itself not attacked by knight there


def test_square_attacked_by_rook(board_from_fen):
    b = board_from_fen("8/8/8/8/3R4/8/8/8 w - - 0 1")
    assert b.is_square_attacked(4, 0, WHITE)  # same rank
    assert b.is_square_attacked(0, 3, WHITE)  # same file


def test_square_not_attacked_when_blocked(board_from_fen):
    b = board_from_fen("8/8/8/3p4/3R4/8/8/8 w - - 0 1")
    # White rook on d4, black pawn on d5 — d6 should not be attacked by rook
    assert not b.is_square_attacked(2, 3, WHITE)  # d6 blocked by d5 pawn


# ------------------------------------------------------------------
# En passant make/unmake
# ------------------------------------------------------------------

def test_en_passant_removes_captured_pawn(board_from_fen):
    # White pawn on e5, Black pawn just double-pushed to d5 (ep target d6)
    b = board_from_fen("8/8/8/3pP3/8/8/8/8 w - d6 0 1")
    b.make_move(Move((3, 4), (2, 3), EN_PASSANT))  # exd6 en passant
    assert b.grid[2][3] is not None  # white pawn on d6
    assert b.grid[3][3] is None      # captured black pawn removed from d5
    assert b.grid[3][4] is None      # white pawn moved away


def test_en_passant_unmake_restores_captured_pawn(board_from_fen):
    b = board_from_fen("8/8/8/3pP3/8/8/8/8 w - d6 0 1")
    original_fen = b.to_fen()
    b.make_move(Move((3, 4), (2, 3), EN_PASSANT))
    b.unmake_move()
    assert b.to_fen() == original_fen


# ------------------------------------------------------------------
# Castling make/unmake
# ------------------------------------------------------------------

def test_kingside_castle_moves_both_pieces(board_from_fen):
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.make_move(Move((7, 4), (7, 6), CASTLING))
    assert b.grid[7][6] is not None  # king on g1
    assert b.grid[7][5] is not None  # rook on f1
    assert b.grid[7][4] is None       # e1 empty
    assert b.grid[7][7] is None       # h1 empty


def test_queenside_castle_moves_both_pieces(board_from_fen):
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    b.make_move(Move((7, 4), (7, 2), CASTLING))
    assert b.grid[7][2] is not None  # king on c1
    assert b.grid[7][3] is not None  # rook on d1
    assert b.grid[7][4] is None
    assert b.grid[7][0] is None


def test_castling_unmake(board_from_fen):
    b = board_from_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    original_fen = b.to_fen()
    b.make_move(Move((7, 4), (7, 6), CASTLING))
    b.unmake_move()
    assert b.to_fen() == original_fen


# ------------------------------------------------------------------
# Promotion make/unmake
# ------------------------------------------------------------------

def test_promotion_replaces_pawn(board_from_fen):
    b = board_from_fen("8/4P3/8/8/8/8/8/8 w - - 0 1")
    b.make_move(Move((1, 4), (0, 4), PROMOTION, QUEEN))
    p = b.grid[0][4]
    assert p is not None
    assert p.piece_type == QUEEN
    assert p.color == WHITE


def test_promotion_unmake_restores_pawn(board_from_fen):
    b = board_from_fen("8/4P3/8/8/8/8/8/8 w - - 0 1")
    original_fen = b.to_fen()
    b.make_move(Move((1, 4), (0, 4), PROMOTION, QUEEN))
    b.unmake_move()
    assert b.to_fen() == original_fen
