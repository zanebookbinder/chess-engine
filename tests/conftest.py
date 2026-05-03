import pytest
from src.board import Board
from src.move_generator import MoveGenerator


@pytest.fixture
def starting_board() -> Board:
    b = Board()
    b.setup_starting_position()
    return b


@pytest.fixture
def empty_board() -> Board:
    return Board()


@pytest.fixture
def board_from_fen():
    def _factory(fen: str) -> Board:
        return Board.from_fen(fen)
    return _factory


def perft(board: Board, depth: int) -> int:
    """Count leaf nodes at <depth> — used to validate move generator correctness."""
    if depth == 0:
        return 1
    moves = MoveGenerator(board).generate_legal_moves()
    count = 0
    for move in moves:
        board.make_move(move)
        count += perft(board, depth - 1)
        board.unmake_move()
    return count
