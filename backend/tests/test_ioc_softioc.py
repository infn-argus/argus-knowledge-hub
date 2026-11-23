"""The IOC engineer and iocmng soft IOCs (a beamline's `softiocs:`).

A soft IOC owns no device: its logic is the config.yaml in the beamline repository. So what it reads and
writes, and whether iocmng will accept its rules, are answered from that file, with the evaluator's own
whitelist read (never imported) from epik8s-softioc-mng.
"""
import json
import textwrap

import pytest

from app.ioc_engineer import catalog, tools
from app.services import mcp_tools


def _write(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


GOOD = """
    parameters: {mode: continuous, interval: 1.0, timeout: 2.0}
    arguments:
      inputs:
        llrf1: {type: int, value: 0, link: "TL:LLRF1:rf_ctrl", link_mode: monitor}
        chiller: {type: int, value: 1, link: "TL:CHL:STATE"}
        temp: {type: float, value: 0.0, link: "TL:CHL:TEMP", buffer_size: 10}
      outputs:
        INTLK_ACT: {type: int, value: 0}
        LAST_RULE: {type: string, value: ""}
    rule_defaults: {INTLK_ACT: 0}
    rules:
      - id: CHL_OFF
        condition: "chiller == 0 and llrf1 == 1"
        tolerance: 60
        message: "CHL: LLRF1 OFF"
        message_pv: MESSAGE
        outputs: {INTLK_ACT: 1, LAST_RULE: CHL_OFF}
        actuators: {llrf1: 0}
      - id: HOT
        condition: "mean(temp_buf) > 30"
        outputs: {INTLK_ACT: 1}
"""

BAD = """
    arguments:
      inputs:
        a: {type: int, link: "TL:A"}
        manual: {type: int}
      outputs:
        OUT: {type: int}
    colour: blue
    rules:
      - id: R1
        condition: "a == 1 and"
        outputs: {NOPE: 1}
      - id: R1
        condition: "a.real > 0 or evil(a) or ghost == 2"
        actuators: {manual: 0}
        tolerance: -5
      - id: R3
        condition: "manual == 1"
"""


@pytest.fixture()
def soft_catalog(tmp_path, monkeypatch):
    repo = tmp_path / "infn-epics-ioc"
    _write(repo, "docs/architecture.md", "# Arch\n\n## 1. The big picture\n\nOne image.\n")
    mng = tmp_path / "epik8s-softioc-mng"
    _write(mng, "src/iocmng/__init__.py", '__version__ = "2.7.10"\n')
    _write(mng, "src/iocmng/core/safe_eval.py", """
        import ast
        _SAFE_NODES = frozenset(
            {
                ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.Compare, ast.Eq,
                ast.NotEq, ast.Lt, ast.Gt, ast.BinOp, ast.Add, ast.Constant, ast.Name, ast.Load, ast.Call,
            }
        )
    """)
    _write(mng, "src/iocmng/core/functions.py", 'register("mean", _mean)\nregister("max", max)\n')
    (mng / "schemas").mkdir()
    (mng / "schemas" / "iocmng-config.schema.json").write_text(json.dumps({"properties": {
        k: {} for k in ("prefix", "parameters", "pvs", "arguments", "rules", "rule_defaults", "transforms")}}))
    _write(mng, "README.md", "# iocmng\n\nTasks and jobs.\n")
    _write(mng, "MANUAL.md", "# Manual\n\n## 10. Declarative Rules\n\nA rule fires after tolerance seconds.\n")
    line = tmp_path / "epik8s-line"
    _write(line, "deploy/values.yaml", """
        beamline: testline
        softiocDefaults:
          image: ghcr.io/infn-epics/epik8s-softioc-mng
          devgroup: global
          usegateway: true
        softiocs:
          - name: softinterlock
            iocprefix: TL:SOFTINTLK
            module: iocmng.declarative
            className: DeclarativeTask
            usegateway: false
            gitRepoConfig: {url: "https://example.org/x/epik8s-line.git", path: config/iocs/softinterlock}
          - name: broken
            iocprefix: TL:BROKEN
            gitRepoConfig: {path: config/iocs/broken}
          - name: missing
            iocprefix: TL:MISSING
    """)
    _write(line, "config/iocs/softinterlock/config.yaml", GOOD)
    _write(line, "config/iocs/softinterlock/start.sh.j2", "iocmng-run --prefix {{iocprefix}}\n")
    _write(line, "config/iocs/broken/config.yaml", BAD)
    out = tmp_path / "catalog.json.gz"
    catalog.write(catalog.build(repo, beamlines=(str(line),), iocmng=str(mng), workdir=tmp_path / "work"), out)
    monkeypatch.setenv("ARGUS_IOC_CATALOG", str(out))
    catalog.load.cache_clear()
    yield
    catalog.load.cache_clear()


def test_the_catalogue_reads_iocmng_and_the_soft_iocs(soft_catalog):
    cat = catalog.load()
    assert cat["iocmng"]["version"] == "2.7.10"
    assert cat["iocmng"]["functions"] == ["max", "mean"] and "Call" in cat["iocmng"]["safe_nodes"]
    (line,) = cat["beamlines"]
    assert [s["name"] for s in line["softiocs"]] == ["softinterlock", "broken", "missing"]
    configs = line["softioc_configs"]
    assert configs["softinterlock"]["source"]["from_beamline"]             # the beamline's own repository
    assert configs["softinterlock"]["files"] == ["config.yaml", "start.sh.j2"]
    assert "no such directory" in configs["missing"]["problems"][0]


def test_a_soft_ioc_with_its_wiring(soft_catalog):
    g = tools.ioc_get_softioc(None, "", "testline", "softinterlock")
    assert g["found"] and g["check"]["ok"], g["check"]
    assert g["entry"]["image"] == "ghcr.io/infn-epics/epik8s-softioc-mng"   # softiocDefaults merged
    assert any("usegateway" in i for i in g["ignored_by_merge"])            # false does not override true
    w = g["wiring"]
    assert {r["pv"] for r in w["reads"]} == {"TL:LLRF1:rf_ctrl", "TL:CHL:STATE", "TL:CHL:TEMP"}
    (write,) = w["writes"]
    assert write == {"pv": "TL:LLRF1:rf_ctrl", "input": "llrf1", "value": 0, "rule": "CHL_OFF",
                     "condition": "chiller == 0 and llrf1 == 1", "tolerance_s": 60, "message": "CHL: LLRF1 OFF"}
    assert "TL:SOFTINTLK:INTLK_ACT" in w["pvs"] and "TL:SOFTINTLK:MESSAGE" in w["pvs"]


def test_what_iocmng_would_refuse_is_reported(soft_catalog):
    check = tools.ioc_get_softioc(None, "", "testline", "broken")["check"]
    text = "\n".join(check["errors"])
    assert not check["ok"]
    for expected in ("unknown top-level key 'colour'", "does not parse", "sets output 'NOPE'", "id used twice",
                     "Attribute is not allowed", "function 'evil' is not registered", "'ghost' is not a wired input",
                     "actuator 'manual' has no link", "tolerance must be seconds"):
        assert expected in text, expected
    assert any("'manual' is used in a condition but has no link" in w for w in check["warnings"])
    assert "module is missing" in " ".join(check["warnings"])
    missing = tools.ioc_get_softioc(None, "", "testline", "missing")
    assert not missing["check"]["ok"] and "no config.yaml" in missing["check"]["errors"][-1]


def test_what_writes_a_pv_across_soft_iocs(soft_catalog):
    q = tools.ioc_softioc_wiring(None, "", "llrf1")
    assert [(x["softioc"], x["rule"], x["value"]) for x in q["written_by"]] == [("softinterlock", "CHL_OFF", 0)]
    assert [r["in_conditions_of"] for r in q["read_by"]] == [["CHL_OFF"]]
    assert tools.ioc_softioc_wiring(None, "", "TL:NOTHING")["written_by"] == []


def test_beamline_views_include_soft_iocs(soft_catalog):
    check = tools.ioc_check_beamline(None, "", "testline")["softiocs"]
    assert check["passed"] == ["softinterlock"]
    assert {f["softioc"] for f in check["failed"]} == {"broken", "missing"}
    rows = {r["name"]: r for r in tools.ioc_list_beamline(None, "", "testline")["softiocs"]}
    assert rows["softinterlock"]["writes"] == ["TL:LLRF1:rf_ctrl"] and rows["softinterlock"]["rules"] == 2
    hits = tools.ioc_search(None, "", "interlock")["results"]
    assert hits[0]["kind"] == "softioc" and hits[0]["name"] == "softinterlock"


def test_the_guide_serves_the_iocmng_manual(soft_catalog):
    g = tools.ioc_guide(None, "", "declarative rules")
    assert g["section"] == "Soft IOCs (iocmng): 10. Declarative Rules" and "tolerance" in g["text"]
    assert tools.ioc_guide(None, "")["catalogue"]["softiocs"] == {"testline": 3}


def test_the_soft_ioc_tools_are_offered_over_mcp():
    for name in ("ioc_get_softioc", "ioc_softioc_wiring"):
        assert callable(mcp_tools.BY_NAME[name]["handler"])
    assert "softioc" in mcp_tools.BY_NAME["ioc_search"]["inputSchema"]["properties"]["kind"]["enum"]
