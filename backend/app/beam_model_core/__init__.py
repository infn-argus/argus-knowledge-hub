"""The canonical beam model, `argus.beam-model/2` (docs/beam-model-format.md), as a pure library.

No database, no ledger, no web framework: the same code runs in the Accelerator Model Toolbox, in a CI job
and in the Knowledge Hub. Modules:

    vocabulary   component types by family, capabilities, observables, measurement models, states, relations
    schema       the object model (pydantic) and its JSON form; `json_schema()` for `*.beam.json`
    upgrade      reading v1 documents as v2, bundles
    validation   errors, warnings and completeness levels (TOPOLOGY … INTEGRATED)
    network      placements, paths, connections; walking the beam network; components as they resolve
    queries      limiting aperture, supports and fiducials
    matching     matching model components to physical assets, with confidence and evidence
"""
from app.beam_model_core.schema import SCHEMA_VERSION, Document, json_schema  # noqa: F401
from app.beam_model_core.validation import LEVELS, Report, load  # noqa: F401

__all__ = ["SCHEMA_VERSION", "Document", "json_schema", "LEVELS", "Report", "load"]
