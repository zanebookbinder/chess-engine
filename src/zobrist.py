from __future__ import annotations
import random

from src.constants import BLACK

_rng = random.Random(20250503)  # fixed seed — reproducible hashes


def _r() -> int:
    return _rng.getrandbits(64)


# [color][piece_type][rank][file]
PIECE_HASHES: list[list[list[list[int]]]] = [
    [[[_r() for _ in range(8)] for _ in range(8)] for _ in range(6)]
    for _ in range(2)
]
SIDE_HASH: int     = _r()          # XOR when Black is to move
CASTLE_HASH: list[int] = [_r() for _ in range(4)]   # one per castling-rights bit
EP_FILE_HASH: list[int] = [_r() for _ in range(8)]  # one per en-passant file


def compute_zobrist(
    grid: list,
    side_to_move: int,
    castling_rights: int,
    en_passant_target,
) -> int:
    h = 0
    for rank in range(8):
        for file in range(8):
            p = grid[rank][file]
            if p is not None:
                h ^= PIECE_HASHES[p.color][p.piece_type][rank][file]
    if side_to_move == BLACK:
        h ^= SIDE_HASH
    for i in range(4):
        if castling_rights & (1 << i):
            h ^= CASTLE_HASH[i]
    if en_passant_target is not None:
        h ^= EP_FILE_HASH[en_passant_target[1]]
    return h
