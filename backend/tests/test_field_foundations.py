"""The rest of the field client's server foundations (asset-model-revision §24.3): one problem
shape, idempotency keys, record versions with preconditions, resumable uploads."""
import secrets
import uuid

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models.issue import Issue
from app.models.workspace import Workspace
from tests.test_ledger_transition import token

client = TestClient(app)


def workspace():
    ws = f"fnd-{secrets.token_hex(3)}"
    db = SessionLocal()
    db.add(Workspace(id=ws, name=ws))
    db.flush()
    headers = token(db, ws)
    db.commit()
    db.close()
    return ws, headers


# --------------------------------------------------------------------------- A60

def test_A60_every_error_carries_the_problem_shape_and_keeps_its_detail():
    ws, h = workspace()
    missing = client.get(f"/v1/assets/{uuid.uuid4()}", headers=h)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Asset not found"                        # unchanged
    assert missing.json()["problem"] == {"code": "not_found", "error": "Asset not found"}
    unauth = client.get("/v1/me", headers={"Authorization": "Bearer nope"})
    assert unauth.json()["problem"]["code"] == "unauthenticated"
    invalid = client.post("/v1/issues", headers=h, json={"uid": str(uuid.uuid4())})
    assert invalid.status_code == 422
    assert invalid.json()["problem"]["code"] == "invalid" and invalid.json()["problem"]["field"] == "title"
    assert isinstance(invalid.json()["detail"], list)                           # FastAPI's list, unchanged
    too_old = client.get("/v1/meta/api", headers={"X-ARGUS-Client": "flutter/0.0.1/1"})
    assert too_old.json()["problem"]["code"] == "client_too_old"
    assert too_old.json()["problem"]["minimum"]


# --------------------------------------------------------------------------- A57, A63

def test_A57_a_replayed_create_returns_the_same_answer_and_writes_once():
    ws, h = workspace()
    uid = str(uuid.uuid4())
    body = {"uid": uid, "title": "Gauge reads zero"}
    k = {**h, "Idempotency-Key": str(uuid.uuid4())}
    first = client.post("/v1/issues", headers=k, json=body)
    assert first.status_code == 201, first.text
    again = client.post("/v1/issues", headers=k, json=body)
    assert again.status_code == 201 and again.json() == first.json()
    assert again.headers["Idempotent-Replayed"] == "true"
    other = client.post("/v1/issues", headers=k, json={**body, "title": "Something else"})
    assert other.status_code == 422 and other.json()["problem"]["code"] == "idempotency_mismatch"
    db = SessionLocal()
    assert db.query(Issue).filter(Issue.workspace_id == ws).count() == 1
    db.close()


def test_A63_a_lost_answer_is_returned_again_even_for_a_second_new_uid():
    """The retry of a create without a client uid would make a second record; the key stops it."""
    ws, h = workspace()
    k = {**h, "Idempotency-Key": "retry-1"}
    first = client.post("/v1/issues", headers=k, json={"uid": str(uuid.uuid4()), "title": "Leak"})
    body = first.request.content
    replay = client.post("/v1/issues", headers={**k, "Content-Type": "application/json"}, content=body)
    assert replay.json()["uid"] == first.json()["uid"]
    db = SessionLocal()
    assert db.query(Issue).filter(Issue.workspace_id == ws).count() == 1
    db.close()


def test_keys_are_per_principal_and_refusals_are_remembered_but_not_auth_failures():
    ws, h = workspace()
    ws2, h2 = workspace()
    key = str(uuid.uuid4())
    a = client.post("/v1/issues", headers={**h, "Idempotency-Key": key}, json={"uid": str(uuid.uuid4()), "title": "A"})
    b = client.post("/v1/issues", headers={**h2, "Idempotency-Key": key}, json={"uid": str(uuid.uuid4()), "title": "B"})
    assert a.status_code == b.status_code == 201 and a.json()["uid"] != b.json()["uid"]
    bad = {"uid": str(uuid.uuid4())}
    r1 = client.post("/v1/issues", headers={**h, "Idempotency-Key": "k-bad"}, json=bad)
    r2 = client.post("/v1/issues", headers={**h, "Idempotency-Key": "k-bad"}, json=bad)
    assert r1.status_code == r2.status_code == 422 and r2.headers.get("Idempotent-Replayed") == "true"
    anon = client.post("/v1/issues", headers={"Authorization": "Bearer nope", "Idempotency-Key": "x"},
                       json={"uid": str(uuid.uuid4()), "title": "C"})
    assert anon.status_code == 401
    assert client.post("/v1/issues", headers={**h, "Idempotency-Key": "  "}, json=bad).json()["problem"]["field"] \
        == "Idempotency-Key"


# --------------------------------------------------------------------------- A58, A59

def _pump(ws, h, attrs):
    from app.ledger import engine
    db = SessionLocal()
    sid = engine.ensure_type(db, ws, "Ion Pump").uid
    db.commit()
    db.close()
    uid = str(uuid.uuid4())
    r = client.post("/v1/assets", headers=h, json={"uid": uid, "schema_uid": sid, "key": f"{ws}-{uid[:6]}",
                                                   "name": "pump", "type": "Ion Pump", "attributes": attrs})
    assert r.status_code == 201, r.text
    return uid


def test_A58_an_edit_on_an_old_version_applies_unless_it_touches_what_changed():
    """`notes` stands for the location and `model` for the condition: free-text fields of the type."""
    ws, h = workspace()
    uid = _pump(ws, h, {"notes": "Rack A", "model": "TiTan 45", "serial": "S-1", "manufacturer": "Agilent"})
    read = client.get(f"/v1/assets/{uid}", headers=h)
    v1 = read.headers["ETag"]
    assert read.json()["version"] == int(v1.strip('"'))
    attrs = read.json()["attributes"]
    # Someone else moves it (v2).
    moved = client.put(f"/v1/assets/{uid}", headers={**h, "If-Match": v1},
                       json={"attributes": {**attrs, "notes": "Rack B"}})
    assert moved.status_code == 200, moved.text
    assert moved.json()["version"] > int(v1.strip('"'))
    # The field client, still on v1, changes another field: nothing it touches changed.
    other = client.put(f"/v1/assets/{uid}", headers={**h, "If-Match": v1},
                       json={"attributes": {**attrs, "notes": "Rack B", "model": "TiTan 75"}})
    assert other.status_code == 200, other.text
    assert other.json()["attributes"]["model"] == "TiTan 75"
    # ...and then the location, which did change since v1: stale, with the current value.
    loc = client.put(f"/v1/assets/{uid}", headers={**h, "If-Match": v1},
                     json={"attributes": {**other.json()["attributes"], "notes": "Rack C"}})
    assert loc.status_code == 409
    p = loc.json()["problem"]
    assert p["code"] == "stale" and p["field"] == "attr:notes"
    assert p["current"]["values"] == {"attr:notes": "Rack B"}
    assert client.get(f"/v1/assets/{uid}", headers=h).json()["attributes"]["notes"] == "Rack B"


def test_a_stale_edit_of_a_protected_field_becomes_a_review_item_not_an_overwrite():
    ws, h = workspace()
    uid = _pump(ws, h, {"serial": "S-1", "manufacturer": "Agilent"})
    read = client.get(f"/v1/assets/{uid}", headers=h)
    v1, attrs = read.headers["ETag"], read.json()["attributes"]
    assert client.put(f"/v1/assets/{uid}", headers=h, json={"attributes": {**attrs, "serial": "S-2"}}).status_code == 200
    r = client.put(f"/v1/assets/{uid}", headers={**h, "If-Match": v1}, json={"attributes": {**attrs, "serial": "S-3"}})
    assert r.status_code == 409 and r.json()["problem"]["code"] == "stale"
    item = r.json()["problem"]["review_item"]
    assert client.get(f"/v1/assets/{uid}", headers=h).json()["attributes"]["serial"] == "S-2"
    queue = client.get("/v1/ledger/review", headers=h).json()["conflicts"]
    [row] = [c for c in queue if c["conflict_id"] == item]
    assert row["type"] == "stale_command" and row["detail"]["command"]["changes"]["attr:serial"] == "S-3"
    # A later edit re-projects the record; the review item stays until a person closes it.
    assert client.put(f"/v1/assets/{uid}", headers=h, json={"attributes": {**attrs, "serial": "S-2",
                                                                          "notes": "ok"}}).status_code == 200
    assert any(c["conflict_id"] == item for c in client.get("/v1/ledger/review", headers=h).json()["conflicts"])
    assert client.post(f"/v1/ledger/review/stale/{item}/close", headers=h,
                       json={"outcome": "dismissed"}).status_code == 200
    assert not any(c["conflict_id"] == item for c in client.get("/v1/ledger/review", headers=h).json()["conflicts"])


def test_A59_an_offline_replacement_against_a_changed_position_is_reviewed_not_applied():
    from tests.test_ledger_slice import Slice, setup_confirmed
    from app.ledger import engine
    s = Slice()
    db = SessionLocal()
    i1 = setup_confirmed(db, s)
    pos, spare = s.pos(db).uid, s.unit(db, "90001").uid
    db.close()
    # Another technician replaces the unit online.
    online = client.post("/v1/installations/swap", headers=s.headers, json={
        "position_uid": pos, "new_asset_uid": spare, "at": "2026-09-20T10:00:00+00:00",
        "seen_installation_uid": i1})
    assert online.status_code == 200, online.text
    # The offline replacement, captured while I1 was current, arrives.
    offline = client.post("/v1/installations/swap", headers=s.headers, json={
        "position_uid": pos, "new_asset_uid": s_unit_uid(s), "at": "2026-09-20T11:00:00+00:00",
        "seen_installation_uid": i1, "evidence": {"photo_sha256": "ab" * 32, "note": "old unit removed"}})
    assert offline.status_code == 409 and offline.json()["problem"]["code"] == "stale"
    item = offline.json()["problem"]["review_item"]
    db = SessionLocal()
    confirmed = [v for v in engine.installations(db, position_uid=pos, status="Confirmed")]
    assert len(confirmed) == 2                                                  # I1 and the online one, nothing more
    from app.models.ledger import Conflict
    c = db.get(Conflict, item)
    assert c.detail["evidence"]["note"] == "old unit removed" and c.detail["seen_version"] == [i1]
    db.close()


def s_unit_uid(s):
    db = SessionLocal()
    uid = s.unit(db).uid
    db.close()
    return uid


def test_ticket_versions_refuse_only_what_changed():
    ws, h = workspace()
    uid = str(uuid.uuid4())
    client.post("/v1/issues", headers=h, json={"uid": uid, "title": "Leak", "description": "at the flange"})
    read = client.get(f"/v1/issues/{uid}", headers=h)
    v1 = read.headers["ETag"]
    assert client.put(f"/v1/issues/{uid}", headers={**h, "If-Match": v1},
                      json={"description": "at the flange, worse"}).status_code == 200
    title = client.put(f"/v1/issues/{uid}", headers={**h, "If-Match": v1}, json={"title": "Big leak"})
    assert title.status_code == 200 and title.json()["version"] == 3
    desc = client.put(f"/v1/issues/{uid}", headers={**h, "If-Match": v1}, json={"description": "fixed?"})
    assert desc.status_code == 409 and desc.json()["problem"]["field"] == "description"
    assert desc.json()["problem"]["current"]["values"]["description"] == "at the flange, worse"
    assert client.put(f"/v1/issues/{uid}", headers={**h, "If-Match": '"3"'},
                      json={"description": "fixed?"}).status_code == 200


# --------------------------------------------------------------------------- uploads

def _jpeg_with_gps() -> bytes:
    import io
    from PIL import Image
    img = Image.new("RGB", (16, 16), (200, 30, 30))
    exif = Image.Exif()
    exif[0x010F] = "ArgusCam"                                   # Make: kept
    exif[0x8825] = {1: "N", 2: (41.0, 48.0, 30.0)}              # GPS: removed
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif.tobytes())
    return out.getvalue()


def test_a_photo_is_uploaded_in_pieces_verified_stripped_of_gps_and_attached(tmp_path, monkeypatch):
    import hashlib
    import io
    from PIL import Image
    monkeypatch.setattr("app.routers.issues.ATTACHMENTS_DIR", str(tmp_path))
    ws, h = workspace()
    ticket = str(uuid.uuid4())
    client.post("/v1/issues", headers=h, json={"uid": ticket, "title": "Cracked flange"})
    data = _jpeg_with_gps()
    assert 0x8825 in Image.open(io.BytesIO(data)).getexif()
    u = client.post("/v1/uploads", headers=h, json={"filename": "IMG_1.jpg", "content_type": "image/jpeg",
                                                    "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    assert u.status_code == 201, u.text
    uid, half = u.json()["uid"], len(data) // 2
    assert client.put(f"/v1/uploads/{uid}?offset=0", headers=h, content=data[:half]).json()["offset"] == half
    # A retried first piece (its answer was lost) is refused with where to resume.
    again = client.put(f"/v1/uploads/{uid}?offset=0", headers=h, content=data[:half])
    assert again.status_code == 409 and again.json()["problem"]["current"]["offset"] == half
    assert client.get(f"/v1/uploads/{uid}", headers=h).json()["offset"] == half
    early = client.post(f"/v1/uploads/{uid}/complete", headers=h)
    assert early.status_code == 409
    assert client.put(f"/v1/uploads/{uid}?offset={half}", headers=h, content=data[half:]).status_code == 200
    done = client.post(f"/v1/uploads/{uid}/complete", headers=h)
    assert done.status_code == 200 and done.json()["state"] == "complete" and done.json()["gps_removed"]
    att = client.post(f"/v1/uploads/{uid}/attach/ticket/{ticket}", headers=h)
    assert att.status_code == 200 and att.json()["state"] == "attached"
    [row] = client.get(f"/v1/issues/{ticket}/attachments", headers=h).json()
    stored = (tmp_path / row["uid"]).read_bytes()
    exif = Image.open(io.BytesIO(stored)).getexif()
    assert 0x8825 not in exif and exif[0x010F] == "ArgusCam"
    # Attaching twice (a retry) does not make a second attachment.
    client.post(f"/v1/uploads/{uid}/attach/ticket/{ticket}", headers=h)
    assert len(client.get(f"/v1/issues/{ticket}/attachments", headers=h).json()) == 1


def test_uploads_refuse_oversize_wrong_type_bad_hash_and_other_peoples_uploads(tmp_path, monkeypatch):
    import hashlib
    monkeypatch.setattr("app.routers.issues.ATTACHMENTS_DIR", str(tmp_path))
    monkeypatch.setenv("ARGUS_UPLOAD_MAX_IMAGE", "1000")
    ws, h = workspace()
    big = client.post("/v1/uploads", headers=h, json={"filename": "a.jpg", "content_type": "image/jpeg",
                                                      "size": 5000, "sha256": "0" * 64})
    assert big.status_code == 413 and big.json()["problem"] == {
        "code": "too_large", "error": big.json()["problem"]["error"], "limit": 1000, "field": "size"}
    exe = client.post("/v1/uploads", headers=h, json={"filename": "a.exe", "content_type": "application/x-msdownload",
                                                      "size": 10, "sha256": "0" * 64})
    assert exe.status_code == 422 and exe.json()["problem"]["field"] == "content_type"
    data = b"hello field"
    u = client.post("/v1/uploads", headers=h, json={"filename": "a.txt", "content_type": "text/plain",
                                                    "size": len(data), "sha256": hashlib.sha256(b"other").hexdigest()})
    uid = u.json()["uid"]
    client.put(f"/v1/uploads/{uid}?offset=0", headers=h, content=data)
    bad = client.post(f"/v1/uploads/{uid}/complete", headers=h)
    assert bad.status_code == 422 and bad.json()["problem"]["field"] == "sha256"
    assert client.get(f"/v1/uploads/{uid}", headers=h).json()["offset"] == 0
    over = client.put(f"/v1/uploads/{uid}?offset=0", headers=h, content=data + b"!")
    assert over.status_code == 413
    _ws2, h2 = workspace()
    assert client.get(f"/v1/uploads/{uid}", headers=h2).status_code == 404
