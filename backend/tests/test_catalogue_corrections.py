"""Corrections proposed back to Git as patches (app/catalogue/corrections.py): each lands in the file its
value comes from — an Argus-native entry, a NetBox device type's model, a NetBox model's classification —
only the changed lines move, the patch applies with `git apply` at the pinned commit, and what has no place in
a source's format is listed, not forced in."""
import subprocess

import yaml

from app.catalogue.corrections import patches, set_in_block, set_in_flow
from app.catalogue.loader import load_tree
from app.catalogue.sources import materialize
from app.models.catalogue_entry import CatalogueEntry
from tests.test_catalogue_sources import NPORT, argus_files, git, lock, netbox, repo_with

ENTRIES = """models:
- id: pfeiffer-vacuum/tpg-366
  vendor: pfeiffer-vacuum
  model_code: TPG 366
  name: TPG 366
  device_class: vacuum
  sources:
  - kind: other
    ref: INFN
- id: pfeiffer-vacuum/tpr-270
  vendor: pfeiffer-vacuum
  model_code: TPR 270
  name: TPR 270
  device_class: vacuum
"""


def test_a_value_is_set_where_it_is_and_nothing_else_moves():
    out = set_in_block(ENTRIES, "pfeiffer-vacuum/tpg-366", "name", "MaxiGauge TPG 366")
    assert "  name: MaxiGauge TPG 366\n  device_class: vacuum\n  sources:" in out
    assert out.count("\n") == ENTRIES.count("\n")                              # replaced, not added
    added = set_in_block(ENTRIES, "pfeiffer-vacuum/tpg-366", "datasheet_url", "https://example.org/tpg366.pdf")
    assert "  datasheet_url: https://example.org/tpg366.pdf\n  sources:" in added    # before its sources
    last = set_in_block(ENTRIES, "pfeiffer-vacuum/tpr-270", "eol_date", __import__("datetime").date(2030, 1, 1))
    assert last.rstrip().endswith("  eol_date: 2030-01-01")
    assert set_in_block(ENTRIES, "nobody/nothing", "name", "x") is None
    spares = set_in_block(set_in_block(ENTRIES, "pfeiffer-vacuum/tpg-366", "typical_spares", ["fuse"]),
                          "pfeiffer-vacuum/tpg-366", "typical_spares", ["fuse", "display"])
    assert yaml.safe_load(spares)["models"][0]["typical_spares"] == ["fuse", "display"]
    assert yaml.safe_load(spares)["models"][1] == yaml.safe_load(ENTRIES)["models"][1]


def test_a_classification_is_set_in_its_line_or_added():
    text = "classifications:\n  - {id: moxa/nport-5450, device_class: converter, instance_type: Serial Converter}\n"
    out = set_in_flow(text, "moxa/nport-5450", "device_class", "io", "classifications")
    assert yaml.safe_load(out)["classifications"][0] == {"id": "moxa/nport-5450", "device_class": "io",
                                                         "instance_type": "Serial Converter"}
    added = set_in_flow(text + "other: 1\n", "moxa/nport-5410", "device_class", "converter", "classifications")
    assert [c["id"] for c in yaml.safe_load(added)["classifications"]] == ["moxa/nport-5450", "moxa/nport-5410"]
    assert yaml.safe_load(added)["other"] == 1
    block = "classifications:\n- id: moxa/nport-5450\n  device_class: converter\n"
    added = set_in_flow(block, "moxa/nport-5410", "device_class", "converter", "classifications")
    assert [c["id"] for c in yaml.safe_load(added)["classifications"]] == ["moxa/nport-5450", "moxa/nport-5410"]


def test_corrections_become_patches_that_apply_at_the_pinned_commits(tmp_path):
    models = [{"id": "moxa/tcc-80", "vendor": "moxa", "model_code": "TCC-80", "name": "TCC 80",
               "device_class": "converter"}]
    a = repo_with(tmp_path / "argus", argus_files(models=models))
    n = netbox(tmp_path)
    root = materialize(lock(tmp_path, a, n), cache=tmp_path / "cache")
    tree = load_tree(root)

    class Rows:
        """Installed entries, as the database would hold them, with their corrections."""
        def __init__(self, rows):
            self.rows = rows

        def scalars(self, _query):
            return self.rows

    def row(cid, collection, kind, corrections, stated=None):
        return CatalogueEntry(catalogue_id=cid, record_uid=f"r-{cid}", workspace_id="cat", kind=kind,
                              collection_id=collection, collection_version="0.1.0", collection_checksum="x",
                              stated=stated or {}, corrections=corrections)

    db = Rows([
        row("moxa", "vendors", "vendor", {}),
        row("moxa/tcc-80", "vacuum", "model", {"name": {"value": "Moxa TCC-80 isolator", "by": "u"}},
            {"name": "TCC 80"}),
        row("moxa/nport-5450", "it-devices", "model", {
            "model_code": {"value": "NPort 5450I", "by": "u"},
            "device_class": {"value": "io", "by": "u"},
            "datasheet_url": {"value": "https://example.org/x.pdf", "by": "u"}}),
    ])
    netbox_read = lambda path: git(tmp_path / "netbox", "show", f"{n}:{path}") + "\n"   # noqa: E731
    out = patches(db, "cat", tree=tree, netbox_file=netbox_read)
    by = {(i["catalogue_id"], i["field"]): i for i in out["items"]}
    assert by[("moxa/tcc-80", "name")]["status"] == "patched"
    assert by[("moxa/tcc-80", "name")]["file"] == "collections/vacuum/models.yaml"
    assert by[("moxa/nport-5450", "model_code")]["repo"] == "devicetype-library"
    assert by[("moxa/nport-5450", "device_class")]["file"] == "collections/it-classification/c.yaml"
    assert by[("moxa/nport-5450", "datasheet_url")]["status"] == "skipped"     # no place in NetBox's format
    diffs = {p["repo"]: p["diff"] for p in out["patches"]}

    for repo, name in (("argus-catalogue", "argus"), ("devicetype-library", "netbox")):
        (tmp_path / f"{name}.patch").write_text(diffs[repo])
        subprocess.run(["git", "-C", str(tmp_path / name), "apply", "--check", str(tmp_path / f"{name}.patch")],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(tmp_path / name), "apply", str(tmp_path / f"{name}.patch")], check=True)
    applied = yaml.safe_load((tmp_path / "argus/collections/vacuum/models.yaml").read_text())["models"][0]
    assert applied["name"] == "Moxa TCC-80 isolator" and applied["model_code"] == "TCC-80"
    classes = yaml.safe_load((tmp_path / "argus/collections/it-classification/c.yaml").read_text())
    assert {"id": "moxa/nport-5450", "device_class": "io", "instance_type": "Serial Converter"} in classes["classifications"]
    nport = yaml.safe_load((tmp_path / "netbox/device-types/Moxa/NPort-5450.yaml").read_text())
    assert nport == {**NPORT, "model": "NPort 5450I"}
