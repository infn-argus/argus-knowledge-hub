"""_author_display_name exists because production data proved the
assumption "author is always {'displayName': ...}" wrong: Jira Insight
returns a plain username string for some object types (attachments, in the
observed case) and a nested object for others (comments/history), and the
old `(x.get("author") or {}).get("displayName")` code crashed with
`AttributeError: 'str' object has no attribute 'get'` on the string form —
silently zeroing out every attachment for the whole import.
"""
from app.services.jira_import import _author_display_name


def test_dict_with_display_name():
    assert _author_display_name({"displayName": "Mario Rossi"}) == "Mario Rossi"


def test_dict_falls_back_to_name_then_key():
    assert _author_display_name({"name": "mrossi"}) == "mrossi"
    assert _author_display_name({"key": "mrossi"}) == "mrossi"
    assert _author_display_name({"displayName": None, "name": "mrossi"}) == "mrossi"


def test_plain_string_author():
    assert _author_display_name("mrossi") == "mrossi"


def test_missing_or_empty_author():
    assert _author_display_name(None) is None
    assert _author_display_name("") is None
    assert _author_display_name({}) is None
