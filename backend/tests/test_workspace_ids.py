"""Deriving a workspace's identifier from its name.

The identifier goes into URLs, PAT scopes and every object key the imports
derive, and it cannot be changed afterwards — so it is worth one rule
rather than whatever each admin types. The ones made by hand already
follow it: "EUAPS" became lnf-euaps, "Divisione Acceleratori" became
lnf-divisione-acceleratori.
"""
import secrets

import pytest

from app.db import Base, SessionLocal, engine
from app.models.app_setting import AppSetting
from app.models.workspace import Workspace
from app.services.workspace_ids import (
    DEFAULTS,
    SETTING_KEY,
    rule,
    save_rule,
    slugify,
    unique_id,
)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean_rule():
    """The rule is installation-wide, so a test that changes it would
    otherwise answer for the next one."""
    db = SessionLocal()
    row = db.get(AppSetting, SETTING_KEY)
    if row is not None:
        db.delete(row)
        db.commit()
    db.close()
    yield


# --- the slug -----------------------------------------------------------

def test_a_name_becomes_the_identifier_it_would_have_been_given_by_hand():
    assert slugify("Divisione Acceleratori") == "divisione-acceleratori"
    assert slugify("EUAPS") == "euaps"


def test_punctuation_and_runs_of_spaces_collapse():
    assert slugify("BTF / Beam Test  Facility!") == "btf-beam-test-facility"


def test_accents_are_folded_rather_than_dropped():
    """A name that loses its letters gives an identifier nobody recognises
    as belonging to it."""
    assert slugify("Acceleratòri Größe") == "acceleratori-grosse"


def test_the_prefix_this_installation_uses_can_be_part_of_the_rule():
    settings = {**DEFAULTS, "prefix": "lnf-"}
    assert slugify("EUAPS", settings) == "lnf-euaps"
    assert slugify("Divisione Acceleratori", settings) == "lnf-divisione-acceleratori"


def test_a_name_that_already_carries_the_prefix_does_not_get_it_twice():
    settings = {**DEFAULTS, "prefix": "lnf-"}
    assert slugify("lnf-euaps", settings) == "lnf-euaps"


def test_the_separator_and_case_are_part_of_the_rule():
    assert slugify("Beam Test", {**DEFAULTS, "separator": "_"}) == "beam_test"
    assert slugify("Beam Test", {**DEFAULTS, "case": "upper"}) == "BEAM-TEST"


def test_a_long_name_is_cut_without_leaving_a_trailing_separator():
    slug = slugify("A very long facility name indeed", {**DEFAULTS, "max_length": 12})
    assert len(slug) <= 12
    assert not slug.endswith("-")


# --- uniqueness ---------------------------------------------------------

def test_a_taken_identifier_gets_a_number_rather_than_a_failed_form():
    """Two workspaces called "Test" is a thing that happens, and the admin
    creating the second should not have to invent a spelling."""
    name = f"Facility {secrets.token_hex(3)}"
    db = SessionLocal()
    first = unique_id(db, name)
    db.add(Workspace(id=first, name=name))
    db.commit()

    second = unique_id(db, name)
    assert second == f"{first}-2"
    db.add(Workspace(id=second, name=name))
    db.commit()
    assert unique_id(db, name) == f"{first}-3"
    db.close()


def test_a_name_with_nothing_sluggable_still_yields_something_usable():
    db = SessionLocal()
    assert unique_id(db, "???").startswith("workspace")
    db.close()


def test_the_numbering_uses_the_configured_separator():
    name = f"Facility {secrets.token_hex(3)}"
    settings = {**DEFAULTS, "separator": "_"}
    db = SessionLocal()
    first = unique_id(db, name, settings)
    db.add(Workspace(id=first, name=name))
    db.commit()
    assert unique_id(db, name, settings) == f"{first}_2"
    db.close()


# --- the setting --------------------------------------------------------

def test_the_rule_defaults_until_somebody_sets_it():
    db = SessionLocal()
    assert rule(db) == DEFAULTS
    db.close()


def test_a_saved_rule_is_what_later_names_are_slugged_with():
    db = SessionLocal()
    save_rule(db, {"prefix": "lnf-", "separator": "-", "case": "lower", "max_length": 40})
    assert rule(db)["prefix"] == "lnf-"
    assert slugify("EUAPS", rule(db)) == "lnf-euaps"
    db.close()


def test_a_partial_rule_keeps_the_defaults_for_what_it_omits():
    db = SessionLocal()
    save_rule(db, {"prefix": "infn-"})
    stored = rule(db)
    assert stored["prefix"] == "infn-"
    assert stored["separator"] == DEFAULTS["separator"]
    assert stored["max_length"] == DEFAULTS["max_length"]
    db.close()
