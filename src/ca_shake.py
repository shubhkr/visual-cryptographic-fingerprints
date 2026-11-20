"""Deterministic SHAKE-256-seeded Game-of-Life visual fingerprint."""

import hashlib
import numpy as np
from PIL import Image

CA_SIZE = 32
CA_STEPS = 8


def ca_encode_shake(digest_bytes: bytes, grid_size: int = CA_SIZE,
                    steps: int = CA_STEPS, *, mirror: bool = True) -> np.ndarray:
    """Seed a Game-of-Life board entirely from SHAKE-256, evolve, return heat map.

    The board is a pure function of `digest_bytes`. No library PRNG is used
    and no global state is touched, so any implementation with SHA-3 can
    reproduce the output bit for bit.
    """
    n_cells = grid_size * grid_size
    # Request enough whole bytes to seed every cell.
    xof = hashlib.shake_256(digest_bytes).digest((n_cells + 7) // 8)
    bits = np.unpackbits(np.frombuffer(xof, dtype=np.uint8))[:n_cells]

    board = bits.reshape(grid_size, grid_size).astype(np.uint8).copy()

    # Horizontal symmetry for recognisability, following LifeHash.
    if mirror:
        half = grid_size // 2
        board[:, half:] = np.fliplr(board[:, :grid_size - half])

    heat = board.astype(np.int32).copy()
    for _ in range(steps):
        padded = np.pad(board, 1, mode='wrap')
        neighbours = sum(
            padded[r:r + grid_size, c:c + grid_size]
            for r in range(3) for c in range(3)
        ) - board
        board = np.where(
            (board == 1) & ((neighbours == 2) | (neighbours == 3)), 1,
            np.where((board == 0) & (neighbours == 3), 1, 0)
        ).astype(np.uint8)
        heat += board
    return heat


def ca_to_image(heat: np.ndarray, size: int = 64) -> np.ndarray:
    """Render the accumulated heat map as a grayscale image array."""
    max_val = max(heat.max(), 1)
    normed = (heat.astype(np.float64) / max_val * 255).astype(np.uint8)
    img = Image.fromarray(normed).resize((size, size), Image.Resampling.NEAREST)
    return np.array(img)


# --- Golden test vectors -----------------------------------------------
# Any conforming implementation must reproduce these exactly.
# Values are SHA-256 of the raw 64x64 grayscale pixel bytes.

GOLDEN = {
    "llama3-70b-v1": "85f422df3f32c5f439f4364f16c2214e52fed314f1325d38653bab6492ad315b",
    "gpt2-base": "0618fbc44993e107a34517698af774ee72d35a28e0b8a505be76da992df531c6",
    "mistral-7b-instruct": "0e5279836e06ea06c69fd65daf78b0d570026c0de4de3ad7790f9565ea82d48e",
}


def _generate_golden():
    out = {}
    for label in GOLDEN:
        digest = hashlib.sha256(label.encode()).digest()
        img = ca_to_image(ca_encode_shake(digest))
        out[label] = hashlib.sha256(img.tobytes()).hexdigest()
    return out


if __name__ == '__main__':
    actual = _generate_golden()
    for label, expected in GOLDEN.items():
        if actual[label] != expected:
            raise SystemExit(f"Unexpected pixel digest for {label}: {actual[label]}")
        print(f"{label:24} {expected}")
