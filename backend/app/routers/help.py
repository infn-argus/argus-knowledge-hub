"""The user guide (app/help), for the web app's Help pages. Anyone signed in may read it, with or without a
workspace: it is how to use ARGUS, not anybody's data."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app import help as guide
from app.auth import get_identity

router = APIRouter(prefix="/v1/help", tags=["help"])


@router.get("")
def list_topics(_identity=Depends(get_identity)) -> list[dict]:
    """The guide's topics, in reading order, with their sections."""
    return guide.index()


@router.get("/search")
def search_guide(q: str = Query(..., min_length=2), limit: int = Query(8, ge=1, le=20),
                 _identity=Depends(get_identity)) -> list[dict]:
    """The sections that best match the words of a question."""
    return guide.search(q, limit)


@router.get("/{slug}")
def read_topic(slug: str, _identity=Depends(get_identity)) -> dict:
    """One topic, whole, as Markdown."""
    t = guide.topic(slug)
    if t is None:
        raise HTTPException(status_code=404, detail="No such help topic")
    return {"slug": t.slug, "title": t.title, "summary": t.summary, "keywords": t.keywords, "body": t.body}
