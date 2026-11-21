"""Vectors stored at half width (L-world-class-174).

An embedding is 384 or more float32 values and, at that width, is most of the
notebook's file: 10.3 MB of a 27.8 MB database for 5,000 notes. Every reader
(search, graph, links, the tools) still does
`np.frombuffer(row.embedding, dtype="float32")`, so the column type does the
packing and hands back float32 bytes: no reader changes, and nothing outside
this file knows the disk holds less.

**Marker without a column.** A float32 blob is `4 * dim` bytes, always even;
a packed one is one marker byte plus `2 * dim`, always odd. Length alone says
which a stored row is, so rows written before this existed stay readable with
no flag day, and a backup bundle from either side of the change restores.
(A bundle made after this change opened by an older build reads the packed
rows as noise: the one direction that does not work, and the reason the
conversion is a migration with a downgrade.)

**What is lost.** float16 keeps 11 bits of mantissa, a relative error of
about 5e-4 per value, which moves a cosine score by less than 1e-3 on a unit
vector: it can reorder two notes whose scores already tie, nothing else
(tests/test_packed_vectors.py measures the top-10 overlap). A vector that
float16 cannot hold (a non-finite value, or one above 60,000) is stored whole.
Private notes are never embedded, so sealing is untouched.
"""

from __future__ import annotations

from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator

MARK = b"\x01"
_F16_MAX = 60000.0


def pack(blob: bytes) -> bytes:
    """float32 bytes to the packed form; anything else is returned as it came."""
    if not blob or len(blob) % 4:
        return blob
    import numpy as np

    values = np.frombuffer(blob, dtype="float32")
    if not np.isfinite(values).all() or float(np.abs(values).max()) > _F16_MAX:
        return blob
    return MARK + values.astype("float16").tobytes()


def unpack(blob: bytes) -> bytes:
    """The packed form back to float32 bytes; a float32 blob is returned as it came."""
    if not blob or len(blob) % 2 == 0 or blob[:1] != MARK:
        return blob
    import numpy as np

    return np.frombuffer(blob, dtype="float16", offset=1).astype("float32").tobytes()


def is_packed(blob: bytes) -> bool:
    return bool(blob) and len(blob) % 2 == 1 and blob[:1] == MARK


class PackedVector(TypeDecorator):
    """A float32 vector, stored as float16 (module docstring)."""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        return pack(bytes(value)) if value is not None else None

    def process_result_value(self, value, dialect):  # noqa: ANN001
        return unpack(bytes(value)) if value is not None else None
