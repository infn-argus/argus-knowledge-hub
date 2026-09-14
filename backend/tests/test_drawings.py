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


def _dxf_with(build) -> bytes:
    """A small DXF built in memory, so these tests need no fixture files."""
    import io

    import ezdxf

    doc = ezdxf.new()
    build(doc)
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode("utf-8")


def test_a_modelspace_drawing_renders_one_sheet():
    from app.services.drawings import render_sheets

    def build(doc):
        msp = doc.modelspace()
        msp.add_line((0, 0), (100, 50))
        msp.add_circle((50, 25), 20)

    sheets, error = render_sheets(_dxf_with(build))
    assert error is None
    assert [name for name, _svg in sheets] == ["Model"]
    assert b"<svg" in sheets[0][1]


def test_the_drawings_own_background_is_not_painted():
    """A CAD file's background is black and its lines are drawn black here,
    so painting the background would render a black rectangle."""
    from app.services.drawings import render_sheets

    def build(doc):
        doc.modelspace().add_line((0, 0), (100, 100))

    sheets, _error = render_sheets(_dxf_with(build))
    svg = sheets[0][1].decode()
    assert "</defs><rect" not in svg, "the background rect should be gone"
    assert "#000000" in svg, "and the geometry should be black"


def test_a_drawing_with_nothing_in_it_says_so():
    from app.services.drawings import render_sheets

    sheets, error = render_sheets(_dxf_with(lambda doc: None))
    assert sheets == []
    assert error and "nothing in it" in error


def test_unreadable_input_is_reported_not_raised():
    from app.services.drawings import render_sheets

    sheets, error = render_sheets(b"not a dxf at all")
    assert sheets == []
    assert error and "could not be read" in error


def test_view_blocks_are_rendered_when_nothing_else_is():
    """The real case: converting an Inventor-exported DWG leaves every line
    of the drawing inside blocks with no entity placing them. Without this
    the geometry is in the file and unreachable."""
    from app.services.drawings import render_sheets

    def build(doc):
        block = doc.blocks.new(name="VISTA1")
        for i in range(60):
            block.add_line((i, 0), (i, 100))

    sheets, error = render_sheets(_dxf_with(build))
    assert error is None
    assert [name for name, _svg in sheets] == ["VISTA1"]


def test_symbol_blocks_are_not_mistaken_for_sheets():
    """A CAD file is full of small blocks — arrowheads, markers. Rendering
    those gives a row of sheets each holding one triangle."""
    from app.services.drawings import render_sheets

    def build(doc):
        arrow = doc.blocks.new(name="Filled-1")
        arrow.add_line((0, 0), (1, 1))
        view = doc.blocks.new(name="VISTA1")
        for i in range(60):
            view.add_line((i, 0), (i, 100))

    sheets, _error = render_sheets(_dxf_with(build))
    assert [name for name, _svg in sheets] == ["VISTA1"]
