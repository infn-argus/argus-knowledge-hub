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
