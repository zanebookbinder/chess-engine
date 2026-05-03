# Coordinate system: board[rank][file]
#   rank 0 = Black's back rank (rank 8 in chess notation)
#   rank 7 = White's back rank (rank 1 in chess notation)
#   file 0 = a-file, file 7 = h-file

# Colors
WHITE = 0
BLACK = 1

# Piece types
PAWN   = 0
KNIGHT = 1
BISHOP = 2
ROOK   = 3
QUEEN  = 4
KING   = 5

PIECE_NAMES = ["pawn", "knight", "bishop", "rook", "queen", "king"]
PIECE_SYMBOLS = {
    (WHITE, PAWN):   "P", (WHITE, KNIGHT): "N", (WHITE, BISHOP): "B",
    (WHITE, ROOK):   "R", (WHITE, QUEEN):  "Q", (WHITE, KING):   "K",
    (BLACK, PAWN):   "p", (BLACK, KNIGHT): "n", (BLACK, BISHOP): "b",
    (BLACK, ROOK):   "r", (BLACK, QUEEN):  "q", (BLACK, KING):   "k",
}

FEN_PIECE_MAP = {v: k for k, v in PIECE_SYMBOLS.items()}

# Material values in centipawns
PIECE_VALUES: dict[int, int] = {
    PAWN:   100,
    KNIGHT: 320,
    BISHOP: 330,
    ROOK:   500,
    QUEEN:  900,
    KING:   20000,
}

# Castling rights bitmask
CASTLE_WHITE_KINGSIDE  = 0b0001
CASTLE_WHITE_QUEENSIDE = 0b0010
CASTLE_BLACK_KINGSIDE  = 0b0100
CASTLE_BLACK_QUEENSIDE = 0b1000
CASTLE_ALL             = 0b1111

# Maps a square (rank, file) that, when vacated by its piece, revokes those castling rights.
# King's starting squares revoke both rights for that color; rook squares revoke one.
CASTLING_RIGHTS_REVOCATION: dict[tuple[int, int], int] = {
    (7, 4): CASTLE_WHITE_KINGSIDE | CASTLE_WHITE_QUEENSIDE,  # White king e1
    (0, 4): CASTLE_BLACK_KINGSIDE | CASTLE_BLACK_QUEENSIDE,  # Black king e8
    (7, 7): CASTLE_WHITE_KINGSIDE,   # White kingside rook h1
    (7, 0): CASTLE_WHITE_QUEENSIDE,  # White queenside rook a1
    (0, 7): CASTLE_BLACK_KINGSIDE,   # Black kingside rook h8
    (0, 0): CASTLE_BLACK_QUEENSIDE,  # Black queenside rook a8
}

# Castling rook source and destination squares keyed by (color, kingside)
CASTLING_ROOK_SQUARES: dict[tuple[int, bool], tuple[tuple[int, int], tuple[int, int]]] = {
    (WHITE, True):  ((7, 7), (7, 5)),  # h1 -> f1
    (WHITE, False): ((7, 0), (7, 3)),  # a1 -> d1
    (BLACK, True):  ((0, 7), (0, 5)),  # h8 -> f8
    (BLACK, False): ((0, 0), (0, 3)),  # a8 -> d8
}

# King destination squares for castling
CASTLING_KING_DEST: dict[tuple[int, bool], tuple[int, int]] = {
    (WHITE, True):  (7, 6),  # g1
    (WHITE, False): (7, 2),  # c1
    (BLACK, True):  (0, 6),  # g8
    (BLACK, False): (0, 2),  # c8
}


def on_board(rank: int, file: int) -> bool:
    return 0 <= rank <= 7 and 0 <= file <= 7


# Piece-square tables (PSTs) — White's perspective, rank 0 = Black's back rank.
# For Black, mirror rank: use (7 - rank) when looking up.

PAWN_PST = [
    [ 0,  0,  0,  0,  0,  0,  0,  0],
    [50, 50, 50, 50, 50, 50, 50, 50],
    [10, 10, 20, 30, 30, 20, 10, 10],
    [ 5,  5, 10, 25, 25, 10,  5,  5],
    [ 0,  0,  0, 20, 20,  0,  0,  0],
    [ 5, -5,-10,  0,  0,-10, -5,  5],
    [ 5, 10, 10,-20,-20, 10, 10,  5],
    [ 0,  0,  0,  0,  0,  0,  0,  0],
]

KNIGHT_PST = [
    [-50,-40,-30,-30,-30,-30,-40,-50],
    [-40,-20,  0,  0,  0,  0,-20,-40],
    [-30,  0, 10, 15, 15, 10,  0,-30],
    [-30,  5, 15, 20, 20, 15,  5,-30],
    [-30,  0, 15, 20, 20, 15,  0,-30],
    [-30,  5, 10, 15, 15, 10,  5,-30],
    [-40,-20,  0,  5,  5,  0,-20,-40],
    [-50,-40,-30,-30,-30,-30,-40,-50],
]

BISHOP_PST = [
    [-20,-10,-10,-10,-10,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5, 10, 10,  5,  0,-10],
    [-10,  5,  5, 10, 10,  5,  5,-10],
    [-10,  0, 10, 10, 10, 10,  0,-10],
    [-10, 10, 10, 10, 10, 10, 10,-10],
    [-10,  5,  0,  0,  0,  0,  5,-10],
    [-20,-10,-10,-10,-10,-10,-10,-20],
]

ROOK_PST = [
    [ 0,  0,  0,  0,  0,  0,  0,  0],
    [ 5, 10, 10, 10, 10, 10, 10,  5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [-5,  0,  0,  0,  0,  0,  0, -5],
    [ 0,  0,  0,  5,  5,  0,  0,  0],
]

QUEEN_PST = [
    [-20,-10,-10, -5, -5,-10,-10,-20],
    [-10,  0,  0,  0,  0,  0,  0,-10],
    [-10,  0,  5,  5,  5,  5,  0,-10],
    [ -5,  0,  5,  5,  5,  5,  0, -5],
    [  0,  0,  5,  5,  5,  5,  0, -5],
    [-10,  5,  5,  5,  5,  5,  0,-10],
    [-10,  0,  5,  0,  0,  0,  0,-10],
    [-20,-10,-10, -5, -5,-10,-10,-20],
]

# Middlegame: reward castled position, penalize center exposure
KING_MG_PST = [
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-30,-40,-40,-50,-50,-40,-40,-30],
    [-20,-30,-30,-40,-40,-30,-30,-20],
    [-10,-20,-20,-20,-20,-20,-20,-10],
    [ 20, 20,  0,  0,  0,  0, 20, 20],
    [ 20, 30, 10,  0,  0, 10, 30, 20],
]

# Endgame: reward centralization
KING_EG_PST = [
    [-50,-40,-30,-20,-20,-30,-40,-50],
    [-30,-20,-10,  0,  0,-10,-20,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 30, 40, 40, 30,-10,-30],
    [-30,-10, 20, 30, 30, 20,-10,-30],
    [-30,-30,  0,  0,  0,  0,-30,-30],
    [-50,-30,-30,-30,-30,-30,-30,-50],
]

PIECE_PST = [PAWN_PST, KNIGHT_PST, BISHOP_PST, ROOK_PST, QUEEN_PST, KING_MG_PST]

# Endgame threshold: total non-pawn, non-king material below this → endgame
ENDGAME_MATERIAL_THRESHOLD = PIECE_VALUES[QUEEN] + 2 * PIECE_VALUES[ROOK]  # 1900

# Pawn structure
# Indexed by rank (0 = Black's back rank, 7 = White's back rank).
# White passed pawn is worth more the further advanced it is.
PASSED_PAWN_BONUS = [0, 150, 100, 70, 50, 30, 20, 0]
DOUBLED_PAWN_PENALTY  = -20
ISOLATED_PAWN_PENALTY = -20

# Piece activity
BISHOP_PAIR_BONUS        =  50
ROOK_OPEN_FILE_BONUS     =  25
ROOK_SEMI_OPEN_FILE_BONUS =  15
ROOK_SEVENTH_RANK_BONUS  =  30
MOBILITY_BONUS           =   4  # centipawns per pseudo-legal move (minor pieces + rooks)

# UI constants
SQUARE_SIZE    = 80
BOARD_SIZE     = SQUARE_SIZE * 8
PANEL_WIDTH    = 220
WINDOW_WIDTH   = BOARD_SIZE + PANEL_WIDTH
WINDOW_HEIGHT  = BOARD_SIZE
FPS            = 60

LIGHT_SQUARE_COLOR  = (240, 217, 181)
DARK_SQUARE_COLOR   = (181, 136,  99)
HIGHLIGHT_COLOR     = (205, 210, 106, 180)
SELECTED_COLOR      = (255, 255,   0, 180)
CHECK_COLOR         = (220,  50,  50, 180)
PANEL_BG_COLOR      = ( 40,  40,  40)
PANEL_TEXT_COLOR    = (220, 220, 220)
