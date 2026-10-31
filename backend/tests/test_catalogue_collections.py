"""Catalogue collections (docs/catalogue-collections.md): the shipped ones are valid, and every rule a reviewer
would otherwise have to remember is checked — one manufacturer and one product per entry, ids unique everywhere,
references that exist, transfers stated on both sides, and nothing lost between releases."""
from pathlib import Path

import yaml

from app.catalogue.loader import load_tree
from app.catalogue.validate import compare, tree_problems

VENDORS = [{"id": "moxa", "name": "Moxa Inc.", "aliases": ["MOXA Technologies"]},
           {"id": "cisco", "name": "Cisco Systems, Inc."}]
NPORT = {"id": "moxa/nport-5450", "vendor": "moxa", "model_code": "NPort 5450", "name": "Moxa NPort 5450",
         "device_class": "converter", "instance_type": "Serial Converter", "specifications": {"serial_ports": 4}}


def write(root: Path, cid: str, version: str = "1.0.0", vendors=None, models=None, moved=None, **manifest) -> None:
    d = root / cid
    d.mkdir(parents=True, exist_ok=True)
    content = {k: v for k, v in (("vendors", vendors), ("models", models), ("moved", moved)) if v is not None}
    (d / "entries.yaml").write_text(yaml.safe_dump(content, sort_keys=False))
    requires = manifest.pop("requires", {"packages": {"core-objects": ">=2.1,<3", "it": ">=1.1,<2"},
                                          "collections": {} if cid == "vendors" else {"vendors": ">=1.0,<2"}})
    (d / "collection.yaml").write_text(yaml.safe_dump({
        "id": cid, "version": version, "name": cid.title(), "domain": "catalogue" if cid == "vendors" else "it",
        "owner": "INFN ARGUS", "license": "CC-BY-4.0", "requires": requires, "contents": ["entries.yaml"], **manifest}))


def problems(root: Path, previous: Path | None = None) -> list[str]:
    report = tree_problems(load_tree(root), load_tree(previous) if previous else None)
    return [f"{p.collection}: {p.where}: {p.message}" for ps in report.values() for p in ps]


def base(root: Path, models=None) -> Path:
    write(root, "vendors", vendors=VENDORS)
    write(root, "it-network", models=models if models is not None else [NPORT])
    return root


def test_the_shipped_collections_are_valid():
    tree = load_tree()
    assert {"vendors", "it-network", "accelerator-diagnostics", "vacuum", "accelerator-power"} <= set(tree)
    assert tree_problems(tree) == {cid: [] for cid in tree}


def test_a_valid_tree_and_its_checksum_is_stable(tmp_path):
    base(tmp_path)
    assert problems(tmp_path) == []
    first = load_tree(tmp_path)["it-network"].checksum
    assert load_tree(tmp_path)["it-network"].checksum == first           # reading twice changes nothing


def test_one_product_is_one_entry_across_every_collection(tmp_path):
    base(tmp_path)
    write(tmp_path, "timing-control", models=[{**NPORT}])
    found = problems(tmp_path)
    assert any("'moxa/nport-5450' is already used in 'it-network'" in p for p in found)
    # Another id for the same vendor and model code is the same product.
    write(tmp_path, "timing-control", models=[{**NPORT, "id": "moxa/nport5450", "name": "NPort5450"}])
    assert any("the same product as 'moxa/nport-5450'" in p for p in problems(tmp_path))


def test_one_manufacturer_is_one_entry(tmp_path):
    write(tmp_path, "vendors", vendors=[*VENDORS, {"id": "moxa-tech", "name": "Moxa Technologies Ltd."}])
    write(tmp_path, "it-network", models=[NPORT])
    assert any("is the same company as vendor 'moxa'" in p for p in problems(tmp_path))


def test_references_must_exist_and_be_required(tmp_path):
    bad = {**NPORT, "vendor": "siemens", "id": "siemens/x", "instance_type": "Turbo Pump",
           "relations": [{"verb": "successor-of", "model": "moxa/nport-5410"}],
           "retired": {"since": "1.0.0", "reason": "end of sale", "replaced_by": "moxa/nport-6450"}}
    base(tmp_path, models=[bad])
    found = "\n".join(problems(tmp_path))
    assert "no vendor 'siemens'" in found
    assert "'Turbo Pump' comes from 'vacuum-cryo': add it to requires › packages" in found
    assert "no model 'moxa/nport-5410' in the catalogue" in found
    assert "no model 'moxa/nport-6450'" in found


def test_unknown_keys_and_malformed_values_are_refused(tmp_path):
    base(tmp_path, models=[{**NPORT, "serial_number": "TAG-1", "eol_date": "soon",
                            "specifications": {"Serial Ports": {"nested": {"too": "deep"}}},
                            "sources": [{"kind": "rumour"}]}])
    found = "\n".join(problems(tmp_path))
    assert "unknown key 'serial_number'" in found                        # no site data has a key to go in
    assert "must be a date" in found
    assert "a key is lowercase words joined by _" in found and "a value is a number" in found
    assert "kind must be one of" in found and "needs a ref" in found


def test_a_transfer_is_stated_on_both_sides(tmp_path):
    base(tmp_path)
    write(tmp_path, "timing-control", models=[{**NPORT, "transferred_from": "it-network"}])
    assert any("'it-network' has no `moved: {id: moxa/nport-5450, moved_to: timing-control}`" in p
               for p in problems(tmp_path))

    write(tmp_path, "it-network", version="1.1.0", models=[], moved=[{"id": "moxa/nport-5450", "moved_to": "timing-control"}])
    assert problems(tmp_path) == []

    write(tmp_path, "timing-control", models=[])                         # the tombstone points nowhere
    assert any("'timing-control' does not carry it" in p for p in problems(tmp_path))


def test_between_releases_nothing_disappears_and_changes_need_a_new_version(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    base(before)
    base(after, models=[])                                               # gone, same version
    found = "\n".join(problems(after, previous=before))
    assert "is no longer in the collection: retire it" in found
    assert "the content changed and the version did not go up from 1.0.0" in found

    retired = {**NPORT, "retired": {"since": "1.1.0", "reason": "end of sale"}}
    write(after, "it-network", version="1.1.0", models=[retired])
    assert problems(after, previous=before) == []                        # retired, not removed

    base(after)                                                          # unchanged: same version is fine
    assert compare(load_tree(before), load_tree(after)) == {"vendors": [], "it-network": []}


def test_a_moved_entry_between_releases_is_not_a_removal(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    base(before)
    base(after, models=[])
    write(after, "it-network", version="1.1.0", models=[], moved=[{"id": "moxa/nport-5450", "moved_to": "timing-control"}])
    write(after, "timing-control", models=[{**NPORT, "transferred_from": "it-network"}])
    assert problems(after, previous=before) == []


def test_a_collection_never_disappears(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    base(before)
    write(after, "vendors", vendors=VENDORS)
    assert any("the collection is gone" in p for p in problems(after, previous=before))


def test_what_the_production_inventory_asks_of_a_model(tmp_path):
    # 119 of 131 production models had no model code (it was in the name), device classes came in variant
    # spellings, and some descriptions were whole datasheets pasted in.
    base(tmp_path, models=[{**NPORT, "model_code": " ", "device_class": "network switches",
                            "description": "Technical data\n" * 60}])
    found = "\n".join(problems(tmp_path))
    assert "needs a model_code" in found
    assert "'network switches' is not one of" in found
    assert "longer than 500 characters" in found


def test_a_legal_form_does_not_make_another_company():
    from app.services.catalogue_mapping import norm
    assert norm("INSTRUMENTATION TECHNOLOGIES DD") == norm("Instrumentation Technologies d.o.o.") \
        == norm("Instrumentation Technologies")
