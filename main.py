import pygame
from src.board import Board
from src.engine import Engine
from src.ui import ChessUI


def main() -> None:
    pygame.init()
    board = Board()
    board.setup_starting_position()
    engine = Engine(board, depth=4)
    ui = ChessUI(board, engine)
    ui.run()
    pygame.quit()


if __name__ == "__main__":
    main()
