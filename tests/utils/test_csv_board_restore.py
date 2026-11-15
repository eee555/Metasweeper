from random import Random

import pytest

from utils import board_bytes_to_board
from utils.csv_export import _restore_csv_board


@pytest.mark.parametrize("rows,cols", [(1, 1), (1, 7), (2, 4), (3, 3)])
def test_all_byte_values(rows, cols):
    for value in range(256):
        data = bytes([value])
        assert _restore_csv_board(rows, cols, data) == board_bytes_to_board(rows, cols, data)


@pytest.mark.parametrize("rows,cols", [(1, 255), (255, 1), (8, 8), (16, 16), (16, 30), (7, 13), (50, 60)])
def test_random_and_extreme_boards(rows, cols):
    rng = Random(20261020)
    length = (rows * cols + 7) // 8
    samples = [bytes(length), b"\xff" * length]
    for size in [0, 1, max(0, length - 1), length, length + 5]:
        samples.extend(rng.randbytes(size) for _ in range(20))
    for data in samples:
        assert _restore_csv_board(rows, cols, data) == board_bytes_to_board(rows, cols, data)
