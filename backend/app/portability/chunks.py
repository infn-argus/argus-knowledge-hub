"""Immutable NDJSON chunks, zstd-compressed, written deterministically and read defensively.

A chunk line is one envelope: `{"f": <family>, "k": <key>, "d": <row>}`, serialized with sorted keys
and no insignificant whitespace, so the same rows always give the same bytes and the same hash.

Reading treats the file as hostile: the decompressed size, the compression ratio and the length of a
line are bounded, and a line that is not a JSON object with the envelope's fields stops the read.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import zstandard

ZSTD_LEVEL = 10


@dataclass(frozen=True)
class Limits:
    max_chunk_bytes: int = 512 * 1024 * 1024         # decompressed, per chunk
    max_ratio: int = 200                             # decompressed / compressed
    max_line_bytes: int = 16 * 1024 * 1024           # one record
    max_rows_per_chunk: int = 50_000
    max_file_bytes: int = 256 * 1024 * 1024          # any file in a checkpoint, as stored
    max_blob_bytes: int = 4 * 1024 * 1024 * 1024     # one external artifact


LIMITS = Limits()


class ChunkError(ValueError):
    """A chunk that cannot be trusted: too big, too compressed, malformed."""


def line(family: str, key: str, row: dict) -> bytes:
    return (json.dumps({"f": family, "k": key, "d": row}, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, default=str) + "\n").encode()


def write_chunks(out_dir: Path, prefix: str, family: str, items: Iterable[tuple[str, dict]],
                 limits: Limits = LIMITS) -> list[dict]:
    """Write `items` (key, row) as one or more chunks `<prefix>-000001.ndjson.zst`. Returns one entry
    per chunk: file, rows, the SHA-256 of the uncompressed lines and of the stored file, and the
    first and last key (a ledger family's sequence range)."""
    out: list[dict] = []
    buf, n, first, last = io.BytesIO(), 0, None, None

    def flush():
        nonlocal buf, n, first, last
        if n == 0:
            return
        raw = buf.getvalue()
        name = f"{prefix}-{len(out) + 1:06d}.ndjson.zst"
        data = zstandard.ZstdCompressor(level=ZSTD_LEVEL, write_content_size=True, threads=0).compress(raw)
        (out_dir / name).write_bytes(data)
        out.append({"file": name, "family": family, "rows": n, "first": first, "last": last,
                    "content_sha256": hashlib.sha256(raw).hexdigest(),
                    "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "raw_bytes": len(raw)})
        buf, n, first, last = io.BytesIO(), 0, None, None

    for key, row in items:
        b = line(family, key, row)
        if len(b) > limits.max_line_bytes:
            raise ChunkError(f"{family} {key}: a record of {len(b)} bytes is over the line limit")
        if n and (n >= limits.max_rows_per_chunk or buf.tell() + len(b) > limits.max_chunk_bytes // 2):
            flush()
        buf.write(b)
        first = key if first is None else first
        last = key
        n += 1
    flush()
    return out


def read_chunk(path: Path, family: str, limits: Limits = LIMITS) -> Iterator[tuple[str, dict]]:
    """The (key, row) pairs of one chunk, refusing anything over the limits or malformed."""
    size = os.path.getsize(path)
    if size > limits.max_file_bytes:
        raise ChunkError(f"{path.name}: {size} bytes stored is over the limit")
    cap = min(limits.max_chunk_bytes, max(size, 1) * limits.max_ratio)
    reader = zstandard.ZstdDecompressor().stream_reader(open(path, "rb"), read_across_frames=True)
    total = 0
    pending = b""
    try:
        while True:
            block = reader.read(1 << 20)
            if not block:
                break
            total += len(block)
            if total > cap:
                raise ChunkError(f"{path.name}: decompresses past {cap} bytes (a decompression bomb, "
                                 "or over the chunk limit)")
            pending += block
            while b"\n" in pending:
                raw, pending = pending.split(b"\n", 1)
                yield _parse(path, raw, family, limits)
            if len(pending) > limits.max_line_bytes:
                raise ChunkError(f"{path.name}: a line longer than {limits.max_line_bytes} bytes")
    except zstandard.ZstdError as e:
        raise ChunkError(f"{path.name}: not a valid zstd stream ({e})") from e
    finally:
        reader.close()
    if pending.strip():
        raise ChunkError(f"{path.name}: the last line has no newline")


def _parse(path: Path, raw: bytes, family: str, limits: Limits) -> tuple[str, dict]:
    if len(raw) > limits.max_line_bytes:
        raise ChunkError(f"{path.name}: a line longer than {limits.max_line_bytes} bytes")
    try:
        env = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as e:
        raise ChunkError(f"{path.name}: a line is not JSON ({e})") from e
    if not isinstance(env, dict) or set(env) != {"f", "k", "d"} or not isinstance(env["d"], dict) \
            or not isinstance(env["k"], str):
        raise ChunkError(f"{path.name}: a line is not a record envelope")
    if env["f"] != family:
        raise ChunkError(f"{path.name}: holds {env['f']} where {family} was declared")
    return env["k"], env["d"]


def content_sha256(path: Path, family: str, limits: Limits = LIMITS) -> tuple[int, str]:
    """Rows and the SHA-256 of the uncompressed lines, re-serialized: what the manifest states."""
    h = hashlib.sha256()
    n = 0
    for key, row in read_chunk(path, family, limits):
        h.update(line(family, key, row))
        n += 1
    return n, h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()
