"""The user guide: how to do things in ARGUS, step by step.

One set of Markdown files (guide/*.md) is read three ways: the web app's Help pages, Ask ARGUS (the
`search_help` and `read_help` tools, so it can walk a person through a task), and any MCP client. Each file
is a topic with a small header:

    ---
    title: Export and import
    summary: One line on what the topic covers.
    keywords: [portability, backup, git]
    order: 130
    ---

and `## ` sections, which are what a search returns. Written for the people using ARGUS, not its
developers: what to click, in what order, and what to check.
"""
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

GUIDE = Path(__file__).parent / "guide"
WORD = re.compile(r"[\w']+", re.UNICODE)


@dataclass
class Section:
    heading: str
    anchor: str
    text: str


@dataclass
class Topic:
    slug: str
    title: str
    summary: str
    keywords: list = field(default_factory=list)
    order: int = 1000
    body: str = ""
    sections: list = field(default_factory=list)


def _anchor(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-")


def _parse(path: Path) -> Topic:
    raw = path.read_text(encoding="utf-8")
    meta, body = {}, raw
    if raw.startswith("---\n"):
        head, _, body = raw[4:].partition("\n---\n")
        for line in head.splitlines():
            key, _, value = line.partition(":")
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                meta[key.strip()] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
            else:
                meta[key.strip()] = value.strip("'\"")
    slug = path.stem.split("-", 1)[1] if re.match(r"^\d+-", path.stem) else path.stem
    sections, current, lines = [], None, []
    for line in body.splitlines():
        if line.startswith("## "):
            if current or lines:
                sections.append(Section(current or meta.get("title", slug), _anchor(current or ""),
                                        "\n".join(lines).strip()))
            current, lines = line[3:].strip(), []
        else:
            lines.append(line)
    sections.append(Section(current or meta.get("title", slug), _anchor(current or ""), "\n".join(lines).strip()))
    return Topic(slug=slug, title=meta.get("title", slug), summary=meta.get("summary", ""),
                 keywords=meta.get("keywords", []) or [], order=int(meta.get("order", 1000)),
                 body=body.strip(), sections=[s for s in sections if s.text])


@lru_cache(maxsize=1)
def topics() -> tuple:
    return tuple(sorted((_parse(p) for p in GUIDE.glob("*.md")), key=lambda t: (t.order, t.title)))


def topic(slug: str):
    return next((t for t in topics() if t.slug == slug), None)


def index() -> list[dict]:
    return [{"slug": t.slug, "title": t.title, "summary": t.summary, "keywords": t.keywords,
             "sections": [{"heading": s.heading, "anchor": s.anchor} for s in t.sections if s.anchor]}
            for t in topics()]


def _words(text: str) -> list[str]:
    return [w.lower() for w in WORD.findall(text) if len(w) > 2]


def search(query: str, limit: int = 6) -> list[dict]:
    """The sections that best match the words of the question: a title or keyword match counts most, then
    the section heading, then the text. Plain words, so it works without an embedding model."""
    wanted = set(_words(query))
    if not wanted:
        return []
    scored = []
    for t in topics():
        head = set(_words(t.title + " " + " ".join(t.keywords) + " " + t.summary))
        for s in t.sections:
            heading, text = set(_words(s.heading)), _words(s.text)
            body = set(text)
            score = sum(3 * (w in head) + 2 * (w in heading) + (w in body) for w in wanted)
            if score:
                scored.append((score, -len(text), t, s))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [{"topic": t.slug, "title": t.title, "section": s.heading, "anchor": s.anchor, "text": s.text}
            for _, _, t, s in scored[:limit]]
