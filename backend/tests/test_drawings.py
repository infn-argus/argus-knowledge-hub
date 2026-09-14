"""Converting CAD drawings so a browser can show them.

DWG is a closed, versioned format and the converter's coverage of it is
imperfect by nature, so the behaviour that matters most here is what
happens when a conversion fails: it must be reported, not raised, because
the upload it belongs to has to survive it.
"""
from app.services.drawings import (
    converter_available,
    derivative_filename,
    derivative_marker,
    dwg_to_dxf,
    is_drawing,
    needs_conversion,
)


def test_drawings_are_recognised_by_what_can_be_done_with_them():
    assert needs_conversion("chamber.DWG"), "case doesn't change the format"
    assert not needs_conversion("chamber.dxf"), "already viewable"
    assert is_drawing("chamber.dxf")
    assert not is_drawing("layout.png")


def test_dwf_is_recognised_as_a_drawing_we_cannot_convert():
    """DWF is not DWG — it is Autodesk's published-drawing format, and the
    converter does not read it. Recognising it is what lets an upload say
    so instead of failing with no explanation."""
    assert is_drawing("plan.dwf")
    assert not needs_conversion("plan.dwf")


def test_the_converter_ships_in_the_image():
    """If this fails, the Dockerfile stopped shipping the converter and
    every drawing would quietly arrive without a preview."""
    assert converter_available(), "dwg2dxf is not on PATH"


def test_rubbish_is_reported_not_raised():
    dxf, error = dwg_to_dxf(b"this is definitely not a drawing")
    assert dxf is None
    assert error and "could not be converted" in error


def test_an_empty_file_is_reported_not_raised():
    dxf, error = dwg_to_dxf(b"")
    assert dxf is None
    assert error


def test_a_missing_converter_is_reported_not_raised(monkeypatch):
    """On a server without the converter, a DWG upload must still work —
    it just arrives without a preview."""
    monkeypatch.setattr("app.services.drawings.CONVERTER", "definitely-not-installed")
    dxf, error = dwg_to_dxf(b"AC1015")
    assert dxf is None
    assert "converter" in error.lower()


def test_the_derivative_says_what_it_came_from():
    assert derivative_marker("abc-123") == "dxf-of:abc-123"
    assert derivative_filename("drawings/chamber layout.dwg") == "chamber layout.dxf"
