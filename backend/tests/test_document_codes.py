"""How a document's code is chosen when nobody supplies one."""
from app.services.document_codes import prefix_for


def test_a_multi_word_type_becomes_initials():
    assert prefix_for("Work Instruction") == "WI"
    assert prefix_for("Maintenance Report") == "MR"
    assert prefix_for("Commissioning Record") == "CR"


def test_a_single_word_type_becomes_its_first_letters():
    assert prefix_for("Procedure") == "PROC"
    assert prefix_for("Drawing") == "DRAW"
    assert prefix_for("Note") == "NOTE"


def test_no_type_still_yields_a_prefix():
    assert prefix_for(None) == "DOC"
    assert prefix_for("") == "DOC"
    assert prefix_for("123") == "DOC", "a name with no letters is no name"
