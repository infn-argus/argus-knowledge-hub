"""CAD drawings, made viewable.

A browser cannot render DWG — it is a closed format that only AutoCAD and
its licensees read directly. DXF is the interchange format the same tools
write, and there are renderers for it, so a drawing becomes viewable by
converting it once here rather than by asking every reader to own a CAD
seat.

The original is always kept and always downloadable. This produces a
*derivative*, and the conversion is allowed to fail: a drawing whose
preview didn't work is still a drawing someone can download, whereas a
failed conversion that took the upload with it loses the file.
"""
import os
import re
import subprocess
import tempfile
from typing import Optional

# Formats a browser can be made to show, given the converter below.
CONVERTIBLE_SUFFIXES = (".dwg",)
VIEWABLE_SUFFIXES = (".dxf",)

# DWF is not DWG: it is Autodesk's published-drawing format, a container of
# compressed 2D streams, and LibreDWG does not read it. Naming it here so
# an upload can say so rather than failing without explanation.
UNSUPPORTED_SUFFIXES = (".dwf", ".dwfx")

# A drawing that takes longer than this is one nobody wants to wait for in
# an upload request.
CONVERT_TIMEOUT_SECONDS = 60

CONVERTER = os.environ.get("DWG2DXF", "dwg2dxf")

# The Open Design Alliance's converter, when an administrator has installed
# it. It reads the paper-space sheets that LibreDWG drops — which on a
# drawing exported from Inventor is where the dimensions, title block and
# notes live — so it is preferred whenever it is present. It runs here, on
# this machine: no drawing is sent anywhere.
ODA_CONVERTER = os.environ.get("ODA_CONVERTER", "")


def suffix_of(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def is_drawing(filename: str) -> bool:
    """Whether this is a CAD drawing at all — viewable, convertible, or
    one of the formats we have to decline."""
    return suffix_of(filename) in (
        CONVERTIBLE_SUFFIXES + VIEWABLE_SUFFIXES + UNSUPPORTED_SUFFIXES
    )


def needs_conversion(filename: str) -> bool:
    return suffix_of(filename) in CONVERTIBLE_SUFFIXES


def converter_available() -> bool:
    try:
        subprocess.run([CONVERTER, "--version"], capture_output=True, timeout=10)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def oda_available() -> bool:
    return bool(ODA_CONVERTER) and os.path.exists(ODA_CONVERTER)


def _convert_with_oda(source_dir: str, target_dir: str) -> Optional[str]:
    """ODAFileConverter works on directories, not files: in, out, version,
    type, recurse, audit, filter."""
    try:
        subprocess.run(
            [ODA_CONVERTER, source_dir, target_dir, "ACAD2018", "DXF", "0", "1", "*.DWG"],
            capture_output=True,
            timeout=CONVERT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as e:
        return f"The ODA converter could not be run: {e}"
    return None


def dwg_to_dxf(content: bytes) -> tuple[Optional[bytes], Optional[str]]:
    """Convert a DWG to DXF. Returns (dxf, error) — exactly one is set.

    DWG is a moving target: the format changes with AutoCAD releases and
    the converter's coverage of the newest ones is imperfect. Failure is
    an expected outcome, reported as a reason rather than raised, so the
    caller can keep the original and say why there is no preview.
    """
    with tempfile.TemporaryDirectory() as work:
        source = os.path.join(work, "drawing.dwg")
        target = os.path.join(work, "drawing.dxf")
        with open(source, "wb") as f:
            f.write(content)

        if oda_available():
            out_dir = os.path.join(work, "out")
            os.makedirs(out_dir, exist_ok=True)
            error = _convert_with_oda(work, out_dir)
            produced = os.path.join(out_dir, "drawing.dxf")
            if not error and os.path.exists(produced) and os.path.getsize(produced) > 0:
                with open(produced, "rb") as f:
                    return f.read(), None
            # Falls through to LibreDWG rather than failing: a converter
            # that is installed but unhappy with one file should not stop
            # the one that might manage it.

        try:
            result = subprocess.run(
                [CONVERTER, "-o", target, source],
                capture_output=True,
                timeout=CONVERT_TIMEOUT_SECONDS,
            )
        except FileNotFoundError:
            return None, "No DWG converter is installed on the server."
        except subprocess.TimeoutExpired:
            return None, f"Converting took longer than {CONVERT_TIMEOUT_SECONDS}s."
        except OSError as e:
            return None, f"The converter could not be run: {e}"

        if not os.path.exists(target) or os.path.getsize(target) == 0:
            detail = (result.stderr or b"").decode("utf-8", "replace").strip().splitlines()
            reason = detail[-1] if detail else f"converter exited with {result.returncode}"
            return None, f"This drawing could not be converted: {reason}"

        with open(target, "rb") as f:
            return f.read(), None


def derivative_marker(source_attachment_uid: str) -> str:
    """How a converted file says what it was made from, so the viewer can
    pair the two and nothing has to guess from filenames."""
    return f"dxf-of:{source_attachment_uid}"


def derivative_filename(filename: str) -> str:
    return f"{os.path.splitext(os.path.basename(filename))[0]}.dxf"


# --- Rendering ----------------------------------------------------------
#
# A drawing is shown as SVG produced here rather than by a renderer in the
# browser, because the browser renderers do not draw paper space — and an
# engineering drawing is usually *entirely* paper space: the sheet, its
# title block, its dimensions. Rendering here also means the reader
# downloads a picture rather than a twenty-megabyte DXF.

MAX_SHEETS = 12

# Below this a block is a symbol, not a drawing: an arrowhead is three
# entities, a view of a vacuum chamber is thousands.
MIN_BLOCK_ENTITIES = 50

# The single background rectangle the SVG backend emits right after its
# style definitions.
BACKGROUND_RECT = re.compile(r"(</defs>)<rect[^>]*/>")


def _render_layout(doc, entities, name: str) -> Optional[bytes]:
    from ezdxf.addons.drawing import Frontend, RenderContext, layout as dlayout, svg
    from ezdxf.addons.drawing.config import ColorPolicy, Configuration

    backend = svg.SVGBackend()
    # Black on white, the way the drawing would be plotted. CAD stores its
    # own background — usually black — in the layout's properties, and the
    # background policy does not override that, so the colours are set on
    # the context directly. Without this the sheet renders black on black.
    config = Configuration(color_policy=ColorPolicy.BLACK)
    frontend = Frontend(RenderContext(doc), backend, config=config)
    frontend.draw_entities(entities)
    page = dlayout.Page(0, 0, dlayout.Units.mm, dlayout.Margins.all(5))
    try:
        drawing = backend.get_string(page)
    except ValueError:
        # "empty bounding box" — nothing was drawn, so there is no sheet.
        return None

    # The backend paints the drawing's own background first, and a CAD
    # file's background is black — which with black lines is a black
    # rectangle. The colour belongs to the viewer, not to the file, so the
    # background is dropped and the sheet arrives transparent.
    return BACKGROUND_RECT.sub(r"\1", drawing, count=1).encode("utf-8")


def render_sheets(dxf: bytes) -> tuple[list[tuple[str, bytes]], Optional[str]]:
    """Every sheet of a drawing, as SVG. Returns (sheets, error).

    Tried in the order that matches how drawings are actually built: the
    paper-space layouts, which is where a sheet drawing lives; then
    modelspace, for a drawing made the plain way; and finally the view
    blocks on their own.

    That last case is not hypothetical. Converting a real Inventor-exported
    DWG yields blocks holding every line of the drawing and *no entity
    placing them* — the geometry is in the file but orphaned, and without
    this it would be unreachable. What it recovers is the geometry alone;
    the annotations were lost before we saw the file.
    """
    import ezdxf

    with tempfile.TemporaryDirectory() as work:
        path = os.path.join(work, "drawing.dxf")
        with open(path, "wb") as f:
            f.write(dxf)
        try:
            doc = ezdxf.readfile(path)
        except Exception as e:
            return [], f"The converted drawing could not be read: {e}"

    sheets: list[tuple[str, bytes]] = []

    for layout in doc.layouts:
        if layout.name.lower() == "model":
            continue
        rendered = _render_layout(doc, layout, layout.name)
        if rendered:
            sheets.append((layout.name, rendered))
        if len(sheets) >= MAX_SHEETS:
            return sheets, None
    if sheets:
        return sheets, None

    rendered = _render_layout(doc, doc.modelspace(), "Model")
    if rendered:
        return [("Model", rendered)], None

    # Biggest first, and only blocks substantial enough to be a drawing.
    # A CAD file is full of small blocks — arrowheads, sketch markers, title
    # symbols — and rendering those produces a row of "sheets" containing a
    # single triangle each.
    candidates = []
    for block in doc.blocks:
        if block.name.startswith("*"):  # anonymous: hatches, dimensions
            continue
        count = len(list(block))
        if count >= MIN_BLOCK_ENTITIES:
            candidates.append((count, block.name, block))
    for _count, name, block in sorted(candidates, key=lambda c: -c[0])[:MAX_SHEETS]:
        rendered = _render_layout(doc, block, name)
        if rendered:
            sheets.append((name, rendered))
    if sheets:
        return sheets, None
    return [], "This drawing converted, but there was nothing in it to draw."


def sheet_marker(source_attachment_uid: str) -> str:
    return f"sheet-of:{source_attachment_uid}"


def sheet_filename(filename: str, sheet_name: str) -> str:
    stem = os.path.splitext(os.path.basename(filename))[0]
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", sheet_name).strip("-") or "sheet"
    return f"{stem} ({safe}).svg"
