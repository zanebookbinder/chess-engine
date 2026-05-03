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
from src.evaluator import Evaluator
from src.move import Move, PROMOTION
from src.move_generator import MoveGenerator

UNICODE_PIECES = {
    (WHITE, KING):   "♔", (WHITE, QUEEN):  "♕", (WHITE, ROOK):  "♖",
    (WHITE, BISHOP): "♗", (WHITE, KNIGHT): "♘", (WHITE, PAWN):  "♙",
    (BLACK, KING):   "♚", (BLACK, QUEEN):  "♛", (BLACK, ROOK):  "♜",
    (BLACK, BISHOP): "♝", (BLACK, KNIGHT): "♞", (BLACK, PAWN):  "♟",
}

_DRAG_THRESHOLD = 6  # pixels — below this, a press+release is treated as a click


class ChessUI:
    def __init__(self, board: Board, engine: Engine) -> None:
        self._board = board
        self._engine = engine
        self._screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Chess Engine")

        self._state = "color_select"  # "color_select" | "playing"
        self._human_color = WHITE
        self._game_over = False
        self._status_message = ""
        self._last_move: Optional[Move] = None
        self._current_eval: int = 0

        # Click-to-click selection state
        self._selected_sq: Optional[tuple[int, int]] = None
        self._selected_dests: list[tuple[int, int]] = []

        # Drag-and-drop state
        self._dragging = False
        self._drag_from_sq: Optional[tuple[int, int]] = None
        self._drag_pos: tuple[int, int] = (0, 0)
        self._drag_start_pos: tuple[int, int] = (0, 0)
        self._drag_legal_dests: list[tuple[int, int]] = []

        # Engine thinking progress: (move_label, moves_done, total_moves)
        self._engine_progress: Optional[tuple[str, int, int]] = None

        self._piece_images = self._load_piece_images()
        self._font_large  = pygame.font.SysFont("segoe ui symbol", SQUARE_SIZE - 8)
        self._font_label  = pygame.font.SysFont("Arial", 13, bold=True)
        self._font_small  = pygame.font.SysFont("Arial", 15)
        self._font_medium = pygame.font.SysFont("Arial", 18, bold=True)
        self._font_title  = pygame.font.SysFont("Arial", 22, bold=True)

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
                    self._restart()
                elif self._state == "color_select":
                    self._handle_color_select_event(event)
                elif self._state == "playing":
                    self._handle_play_event(event)

            if self._state == "playing":
                self._tick_game()

            self._render()
            clock.tick(FPS)

    def _restart(self) -> None:
        self._board.setup_starting_position()
        self._game_over = False
        self._status_message = ""
        self._last_move = None
        self._current_eval = 0
        self._selected_sq = None
        self._selected_dests = []
        self._dragging = False
        self._drag_from_sq = None
        self._drag_legal_dests = []
        self._engine_progress = None
        self._state = "color_select"

    # ------------------------------------------------------------------
    # Color selection
    # ------------------------------------------------------------------

    def _handle_color_select_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        white_rect, black_rect = self._color_button_rects()
        if white_rect.collidepoint(event.pos):
            self._human_color = WHITE
            self._state = "playing"
            # Pre-compute top moves for White's first turn
            self._engine.analyze_for_display()
        elif black_rect.collidepoint(event.pos):
            self._human_color = BLACK
            self._state = "playing"
            # Engine plays first; top moves will populate after engine moves

    def _color_button_rects(self) -> tuple[pygame.Rect, pygame.Rect]:
        cx = WINDOW_WIDTH // 2
        cy = WINDOW_HEIGHT // 2
        w, h, gap = 180, 60, 30
        white_rect = pygame.Rect(cx - w - gap // 2, cy - h // 2, w, h)
        black_rect = pygame.Rect(cx + gap // 2, cy - h // 2, w, h)
        return white_rect, black_rect

    # ------------------------------------------------------------------
    # Play event handling — click-to-click AND drag-and-drop
    # ------------------------------------------------------------------

    def _handle_play_event(self, event: pygame.event.Event) -> None:
        if self._game_over or self._board.side_to_move != self._human_color:
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            sq = self._pixel_to_square(*event.pos)
            if sq is None:
                return
            rank, file = sq
            piece = self._board.grid[rank][file]

            if piece is not None and piece.color == self._human_color:
                # Start a drag (also acts as first click of a click-to-click move)
                self._dragging = True
                self._drag_from_sq = sq
                self._drag_pos = event.pos
                self._drag_start_pos = event.pos
                self._drag_legal_dests = self._legal_destinations(sq)
            else:
                # Clicked on empty square or enemy piece — complete a click-to-click move
                if self._selected_sq is not None and sq in self._selected_dests:
                    self._execute_move(self._selected_sq, sq)
                self._selected_sq = None
                self._selected_dests = []

        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self._drag_pos = event.pos

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if not self._dragging:
                return

            dx = event.pos[0] - self._drag_start_pos[0]
            dy = event.pos[1] - self._drag_start_pos[1]
            was_drag = (dx * dx + dy * dy) ** 0.5 >= _DRAG_THRESHOLD

            if was_drag:
                # Drop the piece on the target square
                drop_sq = self._pixel_to_square(*event.pos)
                if drop_sq is not None and drop_sq != self._drag_from_sq:
                    if drop_sq in self._drag_legal_dests:
                        self._execute_move(self._drag_from_sq, drop_sq)
                # Drag always clears any existing selection
                self._selected_sq = None
                self._selected_dests = []
            else:
                # Treat as a click: toggle selection or change selection
                if self._selected_sq == self._drag_from_sq:
                    # Second click on same piece → deselect
                    self._selected_sq = None
                    self._selected_dests = []
                else:
                    self._selected_sq = self._drag_from_sq
                    self._selected_dests = self._drag_legal_dests

            self._dragging = False
            self._drag_from_sq = None
            self._drag_legal_dests = []

    def _execute_move(self, from_sq: tuple[int, int], to_sq: tuple[int, int]) -> None:
        legal = self._get_legal_moves_from(from_sq)
        matching = [m for m in legal if m.to_sq == to_sq]
        if not matching:
            return
        move = next(
            (m for m in matching if m.flag == PROMOTION and m.promotion_piece == QUEEN),
            matching[0],
        )
        self._board.make_move(move)
        self._last_move = move
        self._current_eval = Evaluator(self._board).evaluate()
        self._selected_sq = None
        self._selected_dests = []

    # ------------------------------------------------------------------
    # Game tick
    # ------------------------------------------------------------------

    def _tick_game(self) -> None:
        over, winner = self._board.is_game_over()
        if over and not self._game_over:
            self._game_over = True
            if winner == WHITE:
                self._status_message = "White wins by checkmate!"
            elif winner == BLACK:
                self._status_message = "Black wins by checkmate!"
            else:
                self._status_message = "Draw!"
            return

        if not self._game_over and self._board.side_to_move != self._human_color:
            self._trigger_engine_move()

    def _trigger_engine_move(self) -> None:
        self._engine_progress = None
        self._status_message = "Engine thinking..."
        self._render()
        pygame.display.flip()

        def on_progress(move: Move, idx: int, total: int) -> None:
            self._engine_progress = (self._move_to_display(move), idx, total)
            pygame.event.pump()
            self._render()
            pygame.display.flip()

        move = self._engine.get_best_move(on_progress=on_progress)
        self._engine_progress = None
        if move:
            self._board.make_move(move)
            self._last_move = move
            self._current_eval = Evaluator(self._board).evaluate()
        self._status_message = ""
        # Compute top moves for the human's turn so the sidebar is relevant
        self._engine.analyze_for_display()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    @property
    def _flip_board(self) -> bool:
        return self._human_color == BLACK

    def _sq_to_pixel(self, rank: int, file: int) -> tuple[int, int]:
        """Top-left pixel corner of a board square."""
        dr = 7 - rank if self._flip_board else rank
        df = 7 - file if self._flip_board else file
        return (df * SQUARE_SIZE, dr * SQUARE_SIZE)

    def _pixel_to_square(self, px: int, py: int) -> Optional[tuple[int, int]]:
        if px < 0 or px >= BOARD_SIZE or py < 0 or py >= BOARD_SIZE:
            return None
        dr = py // SQUARE_SIZE
        df = px // SQUARE_SIZE
        if self._flip_board:
            return (7 - dr, 7 - df)
        return (dr, df)

    def _legal_destinations(self, sq: tuple[int, int]) -> list[tuple[int, int]]:
        return list({m.to_sq for m in self._get_legal_moves_from(sq)})

    def _get_legal_moves_from(self, sq: tuple[int, int]) -> list[Move]:
        return [m for m in MoveGenerator(self._board).generate_legal_moves() if m.from_sq == sq]

    def _active_sq(self) -> Optional[tuple[int, int]]:
        """The square that is currently highlighted (dragging or click-selected)."""
        if self._dragging:
            return self._drag_from_sq
        return self._selected_sq

    def _active_dests(self) -> list[tuple[int, int]]:
        """Legal destinations for the active piece."""
        if self._dragging:
            return self._drag_legal_dests
        return self._selected_dests

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render(self) -> None:
        self._screen.fill(PANEL_BG_COLOR)
        if self._state == "color_select":
            self._draw_color_select()
        else:
            self._draw_board()
            self._draw_dots()
            self._draw_labels()
            self._draw_pieces()
            self._draw_drag_piece()
            self._draw_status_panel()
            self._draw_restart_hint()
        pygame.display.flip()

    def _draw_color_select(self) -> None:
        self._screen.fill((28, 28, 28))

        title = self._font_title.render("Choose Your Color", True, (220, 220, 220))
        tx = WINDOW_WIDTH // 2 - title.get_width() // 2
        self._screen.blit(title, (tx, WINDOW_HEIGHT // 2 - 100))

        white_rect, black_rect = self._color_button_rects()

        pygame.draw.rect(self._screen, (230, 230, 230), white_rect, border_radius=8)
        wt = self._font_medium.render("Play as White", True, (20, 20, 20))
        self._screen.blit(wt, (white_rect.centerx - wt.get_width() // 2,
                               white_rect.centery - wt.get_height() // 2))

        pygame.draw.rect(self._screen, (55, 55, 55), black_rect, border_radius=8)
        pygame.draw.rect(self._screen, (160, 160, 160), black_rect, 2, border_radius=8)
        bt = self._font_medium.render("Play as Black", True, (210, 210, 210))
        self._screen.blit(bt, (black_rect.centerx - bt.get_width() // 2,
                               black_rect.centery - bt.get_height() // 2))

    def _draw_board(self) -> None:
        last_sqs = (self._last_move.from_sq, self._last_move.to_sq) if self._last_move else ()
        for rank in range(8):
            for file in range(8):
                is_light = (rank + file) % 2 == 0
                color = LIGHT_SQUARE_COLOR if is_light else DARK_SQUARE_COLOR
                if (rank, file) in last_sqs:
                    color = tuple(min(255, c + 38) for c in color)
                x, y = self._sq_to_pixel(rank, file)
                pygame.draw.rect(self._screen, color, (x, y, SQUARE_SIZE, SQUARE_SIZE))

        # King-in-check highlight
        if self._board.is_in_check(self._board.side_to_move):
            try:
                kr, kf = self._board.find_king(self._board.side_to_move)
                overlay = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                overlay.fill((220, 50, 50, 160))
                self._screen.blit(overlay, self._sq_to_pixel(kr, kf))
            except ValueError:
                pass

        # Active piece highlight
        active = self._active_sq()
        if active:
            overlay = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            overlay.fill((255, 255, 0, 100))
            self._screen.blit(overlay, self._sq_to_pixel(*active))

    def _draw_dots(self) -> None:
        """Draw dots on legal-move destination squares for the active piece."""
        dests = self._active_dests()
        if not dests:
            return

        dot_surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        ring_surf = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        c = SQUARE_SIZE // 2
        pygame.draw.circle(dot_surf, (0, 0, 0, 75), (c, c), SQUARE_SIZE // 8)
        pygame.draw.circle(ring_surf, (0, 0, 0, 75), (c, c), SQUARE_SIZE // 2 - 4, 5)

        for r, f in dests:
            piece = self._board.grid[r][f]
            surf = ring_surf if piece is not None else dot_surf
            self._screen.blit(surf, self._sq_to_pixel(r, f))

    def _draw_labels(self) -> None:
        """Draw file letters along the top row and rank numbers along the left column."""
        # File letters: top display row (display rank 0)
        board_rank_top = 7 if self._flip_board else 0
        for df in range(8):
            board_file = 7 - df if self._flip_board else df
            letter = "abcdefgh"[board_file]
            is_light = (board_rank_top + board_file) % 2 == 0
            color = DARK_SQUARE_COLOR if is_light else LIGHT_SQUARE_COLOR
            surf = self._font_label.render(letter, True, color)
            # Top-right corner of each top-row square
            x = df * SQUARE_SIZE + SQUARE_SIZE - surf.get_width() - 3
            y = 3
            self._screen.blit(surf, (x, y))

        # Rank numbers: left display column (display file 0)
        board_file_left = 7 if self._flip_board else 0
        for dr in range(8):
            board_rank = 7 - dr if self._flip_board else dr
            num = str(8 - board_rank)  # board_rank 0 → "8", board_rank 7 → "1"
            is_light = (board_rank + board_file_left) % 2 == 0
            color = DARK_SQUARE_COLOR if is_light else LIGHT_SQUARE_COLOR
            surf = self._font_label.render(num, True, color)
            # Top-left corner of each left-column square
            x = 3
            y = dr * SQUARE_SIZE + 3
            self._screen.blit(surf, (x, y))

    def _draw_pieces(self) -> None:
        for rank in range(8):
            for file in range(8):
                if self._dragging and self._drag_from_sq == (rank, file):
                    continue  # drawn separately under cursor
                piece = self._board.grid[rank][file]
                if piece is None:
                    continue
                x, y = self._sq_to_pixel(rank, file)
                self._blit_piece(piece.color, piece.piece_type, x, y)

    def _draw_drag_piece(self) -> None:
        if not self._dragging or self._drag_from_sq is None:
            return
        rank, file = self._drag_from_sq
        piece = self._board.grid[rank][file]
        if piece is None:
            return
        px, py = self._drag_pos
        self._blit_piece(piece.color, piece.piece_type,
                         px - SQUARE_SIZE // 2, py - SQUARE_SIZE // 2)

    def _blit_piece(self, color: int, piece_type: int, x: int, y: int) -> None:
        key = (color, piece_type)
        if key in self._piece_images:
            self._screen.blit(self._piece_images[key], (x, y))
        else:
            symbol = UNICODE_PIECES.get(key, "?")
            fg = (255, 255, 255) if color == WHITE else (30, 30, 30)
            text = self._font_large.render(symbol, True, fg)
            self._screen.blit(text, (x + (SQUARE_SIZE - text.get_width()) // 2,
                                     y + (SQUARE_SIZE - text.get_height()) // 2))

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _draw_status_panel(self) -> None:
        px = BOARD_SIZE
        y = 16

        title = self._font_title.render("Chess Engine", True, (255, 220, 100))
        self._screen.blit(title, (px + 10, y))
        y += title.get_height() + 10

        if self._game_over:
            msg = self._font_medium.render(self._status_message, True, (255, 100, 100))
            self._screen.blit(msg, (px + 10, y))
            y += msg.get_height() + 6
        elif self._status_message:
            msg = self._font_small.render(self._status_message, True, (200, 200, 100))
            self._screen.blit(msg, (px + 10, y))
            y += msg.get_height() + 6
            if self._engine_progress is not None:
                move_label, idx, total = self._engine_progress
                exp = self._font_small.render(f"Exploring {move_label}...", True, (130, 160, 200))
                self._screen.blit(exp, (px + 10, y))
                y += exp.get_height() + 4
                bar_w = PANEL_WIDTH - 20
                bar_h = 10
                bx = px + 10
                pygame.draw.rect(self._screen, (50, 50, 50), (bx, y, bar_w, bar_h), border_radius=4)
                fill_w = int(bar_w * (idx + 1) / max(total, 1))
                if fill_w > 0:
                    pygame.draw.rect(self._screen, (80, 140, 200), (bx, y, fill_w, bar_h), border_radius=4)
                pct = self._font_label.render(f"{idx + 1}/{total}", True, (120, 120, 120))
                self._screen.blit(pct, (px + PANEL_WIDTH - pct.get_width() - 10, y - 1))
                y += bar_h + 6
        else:
            if self._board.side_to_move == WHITE:
                turn_text, turn_color = "White to move", (240, 240, 240)
            else:
                turn_text, turn_color = "Black to move", (160, 160, 160)
            t = self._font_medium.render(turn_text, True, turn_color)
            self._screen.blit(t, (px + 10, y))
            y += t.get_height() + 3
            if self._board.is_in_check(self._board.side_to_move):
                chk = self._font_medium.render("CHECK!", True, (255, 80, 80))
                self._screen.blit(chk, (px + 10, y))
                y += chk.get_height() + 3

        y += 6
        self._draw_divider(y)
        y += 10

        ev_label = self._font_small.render("Evaluation", True, (150, 150, 150))
        self._screen.blit(ev_label, (px + 10, y))
        y += ev_label.get_height() + 5

        self._draw_eval_bar(px, y)
        y += 16 + 5

        if self._current_eval == 0:
            ev_str, ev_color = "0.00", (180, 180, 180)
        elif self._current_eval > 0:
            ev_str, ev_color = f"+{self._current_eval / 100:.2f}", (210, 210, 210)
        else:
            ev_str, ev_color = f"{self._current_eval / 100:.2f}", (160, 160, 160)
        ev_surf = self._font_medium.render(ev_str, True, ev_color)
        self._screen.blit(ev_surf, (px + 10, y))
        y += ev_surf.get_height() + 10

        self._draw_divider(y)
        y += 10

        tm_label = self._font_small.render("Your Best Moves", True, (150, 150, 150))
        self._screen.blit(tm_label, (px + 10, y))
        y += tm_label.get_height() + 5

        top_moves = self._engine.top_moves
        if top_moves:
            for i, (move, score) in enumerate(top_moves):
                move_str = self._move_to_display(move)
                if score > 0:
                    sc_str, sc_color = f"+{score / 100:.2f}", (170, 210, 170)
                elif score < 0:
                    sc_str, sc_color = f"{score / 100:.2f}", (210, 150, 150)
                else:
                    sc_str, sc_color = "0.00", (180, 180, 180)
                row_color = (230, 230, 230) if i == 0 else PANEL_TEXT_COLOR
                line_surf = self._font_small.render(f"{i+1}. {move_str}", True, row_color)
                score_surf = self._font_small.render(sc_str, True, sc_color)
                self._screen.blit(line_surf, (px + 10, y))
                self._screen.blit(score_surf, (px + PANEL_WIDTH - score_surf.get_width() - 10, y))
                y += line_surf.get_height() + 3
        else:
            ph = self._font_small.render("(engine moves shown here)", True, (90, 90, 90))
            self._screen.blit(ph, (px + 10, y))

        if self._last_move:
            y_lm = WINDOW_HEIGHT - 72
            self._draw_divider(y_lm - 8)
            lm_label = self._font_small.render("Last move", True, (150, 150, 150))
            self._screen.blit(lm_label, (px + 10, y_lm))
            lm_text = self._font_medium.render(self._move_to_display(self._last_move), True, PANEL_TEXT_COLOR)
            self._screen.blit(lm_text, (px + 10, y_lm + lm_label.get_height() + 2))

    def _draw_eval_bar(self, panel_x: int, y: int) -> None:
        bar_w = PANEL_WIDTH - 20
        bar_h = 16
        bx = panel_x + 10
        pygame.draw.rect(self._screen, (40, 40, 40), (bx, y, bar_w, bar_h))
        clamped = max(-500, min(500, self._current_eval))
        mid = bar_w // 2
        white_w = int(mid + (clamped / 500) * mid)
        white_w = max(0, min(bar_w, white_w))
        if white_w > 0:
            pygame.draw.rect(self._screen, (210, 210, 210), (bx, y, white_w, bar_h))
        pygame.draw.line(self._screen, (90, 90, 90), (bx + mid, y), (bx + mid, y + bar_h))

    def _draw_divider(self, y: int) -> None:
        pygame.draw.line(self._screen, (70, 70, 70),
                         (BOARD_SIZE + 5, y), (BOARD_SIZE + PANEL_WIDTH - 5, y))

    def _draw_restart_hint(self) -> None:
        hint = self._font_small.render("R = Restart", True, (100, 100, 100))
        x = WINDOW_WIDTH - hint.get_width() - 10
        y = WINDOW_HEIGHT - hint.get_height() - 8
        self._screen.blit(hint, (x, y))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _move_to_display(self, move: Move) -> str:
        files = "abcdefgh"
        ranks = "87654321"
        fr, ff = move.from_sq
        tr, tf = move.to_sq
        s = f"{files[ff]}{ranks[fr]}{files[tf]}{ranks[tr]}"
        if move.flag == PROMOTION and move.promotion_piece is not None:
            s += PIECE_NAMES[move.promotion_piece][0]
        return s

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
                    images[(color, pt)] = pygame.transform.smoothscale(img, (SQUARE_SIZE, SQUARE_SIZE))
        return images
