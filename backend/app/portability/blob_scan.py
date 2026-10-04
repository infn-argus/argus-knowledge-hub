"""Inspect a blob's content before it may leave ARGUS (docs/export-import-design.md §5.2).

The row scanner sees `sha256:<digest>` once a file is externalized, so every blob — source-revision
contents, attachments, document files, icons — is opened here, its text extracted, and that text
run through the same secret detection, plus restricted-classification markers. Processing is
bounded and never executes anything: no macros, no scripts, no external entity or reference
loading, no URL fetching. PDF text comes from the text layer only; Office files are read as their
XML parts; archives are walked with strict recursion, member-count and size limits.

Outcomes, per blob:

  ok             text was extracted and nothing was found
  finding        a secret (always refused: there is no override) or a classification marker (the
                 content is treated as restricted: excluded, encrypted, accepted or blocked by decision);
                 recorded by kind and location, never the value
  opaque         an image or unsupported binary: no text to inspect
  uninspectable  a supported type that could not be read (corrupt, encrypted, over a limit)

`opaque` and `uninspectable` fail closed: the export refuses unless a decision for that blob, or
for opaque content as a whole, says `approve_opaque`, `exclude` or `block` (`classify_encrypt`
is accepted only when the export is encrypted).
"""
from __future__ import annotations

import email
import email.policy
import io
import json
import re
import tarfile
import zipfile
from dataclasses import dataclass, field
from typing import Iterator, Optional

from app.portability import secret_scan


@dataclass(frozen=True)
class ScanLimits:
    max_bytes: int = 64 * 1024 * 1024          # the largest blob opened at all
    max_text: int = 16 * 1024 * 1024           # extracted text per blob
    max_depth: int = 2                          # archives inside archives
    max_members: int = 2000                     # entries in one archive
    max_member_bytes: int = 32 * 1024 * 1024    # one decompressed member
    max_ratio: int = 100                        # decompressed / compressed, per archive
    max_pdf_pages: int = 500


LIMITS = ScanLimits()

TEXT_TYPES = ("text/", "application/json", "application/xml", "application/yaml", "application/x-yaml",
              "application/toml", "application/javascript", "application/x-sh", "message/rfc822")
OPAQUE_TYPES = ("image/", "video/", "audio/", "font/")
CONTENT_MARKERS = [
    ("classification marker: restricted", re.compile(r"(?i)\b(strictly\s+confidential|restricted\s+distribution|"
                                                     r"riservato|confidential|personal\s+data|dati\s+personali)\b")),
    ("classification marker: export control", re.compile(r"(?i)\b(export[\s-]controlled|dual[\s-]use|ITAR|EAR99)\b")),
]
DECISIONS = ("approve_opaque", "accept_classified", "exclude", "block", "classify_encrypt")
CONFIG_SECRET = re.compile(r"(?im)^[ \t]*[\"']?([A-Za-z0-9_.\-]*(?:password|passwd|secret|api[_-]?key|token|"
                           r"private[_-]?key|client[_-]?secret))[\"']?[ \t]*[:=][ \t]*[\"']?([^\s\"'#]+)")


class UnreadableBlob(ValueError):
    pass


@dataclass
class BlobReport:
    digest: str
    status: str                       # ok | finding | opaque | uninspectable
    kind: Optional[str] = None        # how it was read
    findings: list = field(default_factory=list)
    reason: Optional[str] = None

    def summary(self) -> dict:
        return {"sha256": self.digest, "status": self.status, "read_as": self.kind, "reason": self.reason,
                "findings": self.findings[:20]}


def _sniff(data: bytes, mime: Optional[str], name: str) -> str:
    n = (name or "").lower()
    if data.startswith(b"%PDF"):
        return "pdf"
    if data[:4] == b"PK\x03\x04":
        if n.endswith((".docx", ".xlsx", ".pptx", ".odt", ".ods")) or b"word/" in data[:4096] or \
                b"xl/" in data[:4096] or b"[Content_Types].xml" in data[:4096]:
            return "office"
        return "zip"
    if data[:2] == b"\x1f\x8b" or n.endswith((".tar", ".tgz", ".tar.gz")) or data[257:262] == b"ustar":
        return "tar"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "ole"                                  # legacy Office: binary, may carry macros
    m = (mime or "").lower()
    if m.startswith(OPAQUE_TYPES) or data[:8] in (b"\x89PNG\r\n\x1a\n",) or data[:3] == b"\xff\xd8\xff" or \
            data[:6] in (b"GIF87a", b"GIF89a"):
        return "opaque"
    if m == "message/rfc822" or n.endswith(".eml"):
        return "email"
    try:
        data[:65536].decode("utf-8")
        return "text"
    except UnicodeDecodeError:
        pass
    if m.startswith(TEXT_TYPES):
        return "text"
    return "opaque"


def extract(data: bytes, mime: Optional[str], name: str, limits: ScanLimits = LIMITS, depth: int = 0
            ) -> Iterator[tuple[str, str]]:
    """(location, text) pieces of a blob's content. Raises UnreadableBlob for what cannot be read
    within the limits; yields nothing for opaque content (the caller decides)."""
    if len(data) > limits.max_bytes:
        raise UnreadableBlob(f"over {limits.max_bytes} bytes")
    kind = _sniff(data, mime, name)
    if kind == "text":
        yield "", data.decode("utf-8", errors="replace")[: limits.max_text]
    elif kind == "email":
        msg = email.message_from_bytes(data, policy=email.policy.default)
        for h in ("from", "to", "cc", "subject"):
            if msg.get(h):
                yield f"header:{h}", str(msg.get(h))
        for i, part in enumerate(msg.walk()):
            if part.is_multipart():
                continue
            payload = part.get_payload(decode=True) or b""
            if depth >= limits.max_depth:
                raise UnreadableBlob("e-mail nesting beyond the limit")
            for loc, text in extract(payload, part.get_content_type(), part.get_filename() or "", limits, depth + 1):
                yield f"part{i}:{part.get_filename() or part.get_content_type()}{'/' + loc if loc else ''}", text
    elif kind == "pdf":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise UnreadableBlob("encrypted PDF")
            meta = reader.metadata or {}
            yield "metadata", " ".join(str(v) for v in meta.values())
            for i, page in enumerate(reader.pages[: limits.max_pdf_pages]):
                yield f"page{i + 1}", page.extract_text() or ""
            if len(reader.pages) > limits.max_pdf_pages:
                raise UnreadableBlob(f"more than {limits.max_pdf_pages} pages")
        except UnreadableBlob:
            raise
        except Exception as e:  # noqa: BLE001 — a malformed PDF is uninspectable, not ok
            raise UnreadableBlob(f"unreadable PDF ({type(e).__name__})") from e
    elif kind == "office":
        yield from _zip(data, limits, depth, office=True)
    elif kind == "zip":
        yield from _zip(data, limits, depth, office=False)
    elif kind == "tar":
        yield from _tar(data, limits, depth)
    elif kind == "ole":
        raise UnreadableBlob("legacy binary Office format: not read (it may carry macros)")
    # opaque: nothing to yield


def kind_of(data: bytes, mime: Optional[str], name: str) -> str:
    return _sniff(data, mime, name)


def _xml_text(raw: bytes) -> str:
    """Text of an XML part, without parsing entities or DTDs (no external loading, no expansion)."""
    if b"<!DOCTYPE" in raw[:2048] or b"<!ENTITY" in raw:
        raise UnreadableBlob("XML with a DTD or entities is not read")
    text = re.sub(rb"<[^>]+>", b" ", raw)
    return text.decode("utf-8", errors="replace")


def _zip(data: bytes, limits: ScanLimits, depth: int, office: bool) -> Iterator[tuple[str, str]]:
    if depth >= limits.max_depth:
        raise UnreadableBlob("archive nesting beyond the limit")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise UnreadableBlob("corrupt zip") from e
    members = z.infolist()
    if len(members) > limits.max_members:
        raise UnreadableBlob(f"more than {limits.max_members} entries")
    total = 0
    for m in members:
        if m.is_dir():
            continue
        if m.flag_bits & 0x1:
            raise UnreadableBlob(f"encrypted entry {m.filename}")
        if m.file_size > limits.max_member_bytes or m.file_size > max(m.compress_size, 1) * limits.max_ratio:
            raise UnreadableBlob(f"entry {m.filename} decompresses beyond the limits")
        total += m.file_size
        if total > limits.max_bytes:
            raise UnreadableBlob("archive content beyond the limit")
        name = m.filename.lower()
        if office and name.endswith("vbaproject.bin"):
            yield f"{m.filename}", "macro project present (not executed)"
            continue
        raw = z.read(m)
        if office and name.endswith((".xml", ".rels")):
            yield m.filename, _xml_text(raw)
        elif office:
            if not name.endswith((".png", ".jpeg", ".jpg", ".emf", ".wmf", ".gif", ".bin")):
                for loc, text in extract(raw, None, m.filename, limits, depth + 1):
                    yield f"{m.filename}/{loc}" if loc else m.filename, text
        else:
            k = _sniff(raw, None, m.filename)
            if k == "opaque":
                raise UnreadableBlob(f"opaque entry {m.filename} inside an archive")
            for loc, text in extract(raw, None, m.filename, limits, depth + 1):
                yield f"{m.filename}/{loc}" if loc else m.filename, text


def _tar(data: bytes, limits: ScanLimits, depth: int) -> Iterator[tuple[str, str]]:
    if depth >= limits.max_depth:
        raise UnreadableBlob("archive nesting beyond the limit")
    try:
        t = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
    except tarfile.TarError as e:
        raise UnreadableBlob("corrupt tar") from e
    count, total = 0, 0
    for m in t:
        count += 1
        if count > limits.max_members:
            raise UnreadableBlob(f"more than {limits.max_members} entries")
        if not m.isfile():
            continue
        if m.size > limits.max_member_bytes:
            raise UnreadableBlob(f"entry {m.name} beyond the limit")
        total += m.size
        if total > limits.max_bytes or total > max(len(data), 1) * limits.max_ratio:
            raise UnreadableBlob("archive content beyond the limits")
        raw = t.extractfile(m).read()
        if _sniff(raw, None, m.name) == "opaque":
            raise UnreadableBlob(f"opaque entry {m.name} inside an archive")
        for loc, text in extract(raw, None, m.name, limits, depth + 1):
            yield f"{m.name}/{loc}" if loc else m.name, text


def scan(digest: str, data: bytes, mime: Optional[str], name: str, where: str,
         limits: ScanLimits = LIMITS) -> BlobReport:
    """Inspect one blob. `where` names it (family, key, column) in findings."""
    try:
        kind = kind_of(data, mime, name)
        pieces = list(extract(data, mime, name, limits))
    except UnreadableBlob as e:
        return BlobReport(digest, "uninspectable", reason=str(e))
    if kind == "opaque":
        return BlobReport(digest, "opaque", kind, reason=f"{mime or 'unknown type'}: no text to inspect")
    findings = []
    for loc, text in pieces:
        at = f"{where}{'#' + loc if loc else ''}"
        findings += [{**f, "category": "secret"} for f in secret_scan.scan_text(text, at)]
        if text.lstrip()[:1] in "{[":
            findings += [{**f, "category": "secret"} for f in secret_scan.scan_value(_json_or_none(text), at)]
        for m in CONFIG_SECRET.finditer(text):
            if secret_scan.credential_like(m.group(2)):
                findings.append({"where": at, "kind": f"credential assigned to {m.group(1)}", "category": "secret"})
        for label, rx in CONTENT_MARKERS:
            if rx.search(text):
                findings.append({"where": at, "kind": label, "category": "classification"})
        if "macro project present" in text:
            findings.append({"where": at, "kind": "Office macros present", "category": "classification"})
    unique = {(f["where"], f["kind"]): f for f in findings}
    return BlobReport(digest, "finding" if unique else "ok", kind, list(unique.values()))


def _json_or_none(text: str):
    try:
        return json.loads(text)
    except ValueError:
        return None
