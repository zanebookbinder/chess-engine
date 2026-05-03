from __future__ import annotations
import os
from typing import Optional

import pygame

from src.constants import (
    WHITE, BLACK, PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING,
    PIECE_NAMES, SQUARE_SIZE, BOARD_SIZE, PANEL_WIDTH,
    WINDOW_WIDTH, WINDOW_HEIGHT, FPS,
    LIGHT_SQUARE_COLOR, DARK_SQUARE_COLOR,
    PANEL_BG_COLOR, PANEL_TEXT_COLOR,
)
from src.board import Board
from src.engine import Engine
from src.move import Move, PROMOTION
from src.move_generator import MoveGenerator

# Unicode fallback symbols
UNICODE_PIECES = {
    (WHITE, KING):   "♔", (WHITE, QUEEN):  "♕", (WHITE, ROOK):  "♖",
    (WHITE, BISHOP): "♗", (WHITE, KNIGHT): "♘", (WHITE, PAWN):  "♙",
    (BLACK, KING):   "♚", (BLACK, QUEEN):  "♛", (BLACK, ROOK):  "♜",
    (BLACK, BISHOP): "♝", (BLACK, KNIGHT): "♞", (BLACK, PAWN):  "♟",
}


class ChessUI:
    def __init__(self, board: Board, engine: Engine) -> None:
        self._board = board
        self._engine = engine
        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Chess Engine")

        self._selected_square: Optional[tuple[int, int]] = None
        self._highlighted_squares: list[tuple[int, int]] = []
        self._game_over = False
        self._status_message = ""
        self._last_move: Optional[Move] = None

        self._piece_images = self._load_piece_images()
        self._font_large  = pygame.font.SysFont("segoe ui symbol", SQUARE_SIZE - 8, bold=False)
        self._font_small  = pygame.font.SysFont("Arial", 16)
        self._font_medium = pygame.font.SysFont("Arial", 20, bold=True)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self._board.setup_starting_position()
                    self._selected_square = None
                    self._highlighted_squares = []
                    self._game_over = False
                    self._status_message = ""
                    self._last_move = None
                if (event.type == pygame.MOUSEBUTTONDOWN
                        and not self._game_over
                        and self._board.side_to_move == WHITE):
                    self._handle_click(*event.pos)

            # Engine's turn
            if (not self._game_over
                    and self._board.side_to_move == BLACK):
                self._trigger_engine_move()

            self._render()

            over, winner = self._board.is_game_over()
            if over and not self._game_over:
                self._game_over = True
                if winner == WHITE:
                    self._status_message = "White wins by checkmate!"
                elif winner == BLACK:
                    self._status_message = "Black wins by checkmate!"
                else:
                    self._status_message = "Draw!"

            clock.tick(FPS)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _handle_click(self, pixel_x: int, pixel_y: int) -> None:
        sq = self._pixel_to_square(pixel_x, pixel_y)
        if sq is None:
            return

        rank, file = sq
        piece = self._board.get_piece(rank, file)

        if self._selected_square is None:
            if piece and piece.color == WHITE:
                self._selected_square = sq
                self._highlighted_squares = self._legal_destinations(sq)
        else:
            legal = self._get_legal_moves_from(self._selected_square)
            matching = [m for m in legal if m.to_sq == sq]

            if matching:
                # Prefer queen promotion automatically
                move = next(
                    (m for m in matching if m.flag == PROMOTION and m.promotion_piece == QUEEN),
                    matching[0],
                )
                self._board.make_move(move)
                self._last_move = move
                self._selected_square = None
                self._highlighted_squares = []
            elif piece and piece.color == WHITE:
                self._selected_square = sq
                self._highlighted_squares = self._legal_destinations(sq)
            else:
                self._selected_square = None
                self._highlighted_squares = []

    def _pixel_to_square(self, px: int, py: int) -> Optional[tuple[int, int]]:
        if px < 0 or px >= BOARD_SIZE or py < 0 or py >= BOARD_SIZE:
            return None
        return (py // SQUARE_SIZE, px // SQUARE_SIZE)

    def _legal_destinations(self, sq: tuple[int, int]) -> list[tuple[int, int]]:
        return [m.to_sq for m in self._get_legal_moves_from(sq)]

    def _get_legal_moves_from(self, sq: tuple[int, int]) -> list[Move]:
        return [
            m for m in MoveGenerator(self._board).generate_legal_moves()
            if m.from_sq == sq
        ]

    # ------------------------------------------------------------------
    # Engine
    # ------------------------------------------------------------------

    def _trigger_engine_move(self) -> None:
        self._status_message = "Engine thinking..."
        self._render()
        pygame.display.flip()

        move = self._engine.get_best_move()
        if move:
            self._board.make_move(move)
            self._last_move = move
        self._status_message = ""

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        self._screen.fill(PANEL_BG_COLOR)
        self._draw_board()
        self._draw_highlights()
        self._draw_pieces()
        self._draw_status_panel()
        pygame.display.flip()

    def _draw_board(self) -> None:
        for rank in range(8):
            for file in range(8):
                color = LIGHT_SQUARE_COLOR if (rank + file) % 2 == 0 else DARK_SQUARE_COLOR
                rect = pygame.Rect(file * SQUARE_SIZE, rank * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE)
                pygame.draw.rect(self._screen, color, rect)

    def _draw_highlights(self) -> None:
        overlay = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)

        # King in check
        if self._board.is_in_check(self._board.side_to_move):
            try:
                kr, kf = self._board.find_king(self._board.side_to_move)
                overlay.fill((220, 50, 50, 160))
                self._screen.blit(overlay, (kf * SQUARE_SIZE, kr * SQUARE_SIZE))
                overlay.fill((0, 0, 0, 0))
            except ValueError:
                pass

        # Selected square
        if self._selected_square:
            sr, sf = self._selected_square
            overlay.fill((255, 255, 0, 150))
            self._screen.blit(overlay, (sf * SQUARE_SIZE, sr * SQUARE_SIZE))

        # Legal move destinations
        for r, f in self._highlighted_squares:
            overlay.fill((100, 200, 100, 120))
            self._screen.blit(overlay, (f * SQUARE_SIZE, r * SQUARE_SIZE))

        # Last move
        if self._last_move:
            for sq in (self._last_move.from_sq, self._last_move.to_sq):
                r, f = sq
                overlay.fill((180, 180, 80, 100))
                self._screen.blit(overlay, (f * SQUARE_SIZE, r * SQUARE_SIZE))

    def _draw_pieces(self) -> None:
        for rank in range(8):
            for file in range(8):
                piece = self._board.grid[rank][file]
                if piece is None:
                    continue
                x = file * SQUARE_SIZE
                y = rank * SQUARE_SIZE
                key = (piece.color, piece.piece_type)
                if key in self._piece_images:
                    self._screen.blit(self._piece_images[key], (x, y))
                else:
                    # Unicode fallback
                    symbol = UNICODE_PIECES.get(key, "?")
                    color = (255, 255, 255) if piece.color == WHITE else (30, 30, 30)
                    text = self._font_large.render(symbol, True, color)
                    tw = text.get_width()
                    th = text.get_height()
                    self._screen.blit(text, (x + (SQUARE_SIZE - tw) // 2, y + (SQUARE_SIZE - th) // 2))

    def _draw_status_panel(self) -> None:
        panel_x = BOARD_SIZE
        panel_rect = pygame.Rect(panel_x, 0, PANEL_WIDTH, WINDOW_HEIGHT)
        pygame.draw.rect(self._screen, PANEL_BG_COLOR, panel_rect)

        y = 20
        lines: list[tuple[str, pygame.font.Font, tuple[int, int, int]]] = []

        title = "Chess Engine"
        lines.append((title, self._font_medium, (255, 220, 100)))

        lines.append(("", self._font_small, PANEL_TEXT_COLOR))

        if self._game_over:
            lines.append((self._status_message, self._font_medium, (255, 100, 100)))
            lines.append(("Press R to restart", self._font_small, (180, 180, 180)))
        elif self._status_message:
            lines.append((self._status_message, self._font_small, (200, 200, 100)))
        else:
            turn = "White to move" if self._board.side_to_move == WHITE else "Black to move"
            lines.append((turn, self._font_medium, (200, 255, 200)))
            if self._board.is_in_check(self._board.side_to_move):
                lines.append(("CHECK!", self._font_medium, (255, 80, 80)))

        lines.append(("", self._font_small, PANEL_TEXT_COLOR))

        if self._last_move:
            lines.append(("Last move:", self._font_small, (150, 150, 150)))
            lines.append((str(self._last_move), self._font_medium, PANEL_TEXT_COLOR))

        lines.append(("", self._font_small, PANEL_TEXT_COLOR))
        lines.append(("Controls:", self._font_small, (150, 150, 150)))
        lines.append(("Click piece to select", self._font_small, PANEL_TEXT_COLOR))
        lines.append(("Click square to move", self._font_small, PANEL_TEXT_COLOR))
        lines.append(("R = restart", self._font_small, PANEL_TEXT_COLOR))

        for text, font, color in lines:
            surf = font.render(text, True, color)
            self._screen.blit(surf, (panel_x + 10, y))
            y += surf.get_height() + 4

    def _load_piece_images(self) -> dict[tuple[int, int], pygame.Surface]:
        images: dict[tuple[int, int], pygame.Surface] = {}
        assets_dir = os.path.join(os.path.dirname(__file__), "..", "assets", "pieces")
        if not os.path.isdir(assets_dir):
            return images
        color_names = {WHITE: "white", BLACK: "black"}
        for color in (WHITE, BLACK):
            for pt in range(6):
                filename = f"{color_names[color]}_{PIECE_NAMES[pt]}.png"
                path = os.path.join(assets_dir, filename)
                if os.path.exists(path):
                    img = pygame.image.load(path).convert_alpha()
                    images[(color, pt)] = pygame.transform.smoothscale(
                        img, (SQUARE_SIZE, SQUARE_SIZE)
                    )
        return images
