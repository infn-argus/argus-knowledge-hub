"""Synthetic volume for the performance targets (asset-model-revision §19 item 13).

    python scripts/generate_volume.py --workspace volume --assets 50000 --tickets 20000 \
        --documents 5000 --ledger-devices 2000 --token volume-token

Creates a workspace with that many records, relations between them, tickets
on them, documents linked to their types, and a configuration of
`--ledger-devices` devices ingested through the fact ledger (so a full
re-projection has real work to do). Prints the uids to probe with.
Rows are written in batches with executemany; nothing here is realistic
beyond its shape and its size.
"""
from __future__ import annotations

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import insert

from app.auth import hash_token
from app.db import SessionLocal
from app.ledger import engine
from app.models.api_token import ApiToken
from app.models.asset import Asset, Relation
from app.models.document import Document, DocumentRelation, DocumentRevision
from app.models.issue import Issue
from app.models.ledger import TicketLink
from app.models.schema import Schema
from app.models.workspace import Workspace

TYPES = ["Ion Pump", "Vacuum Gauge", "Power Supply", "Camera", "Motor", "Switch", "Server", "Chiller"]
WORDS = ["gun", "linac", "undulator", "dump", "hall", "rack", "vacuum", "rf", "laser", "diagnostic"]


def batched(rows, size=5000):
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="volume")
    ap.add_argument("--assets", type=int, default=50000)
    ap.add_argument("--tickets", type=int, default=20000)
    ap.add_argument("--documents", type=int, default=5000)
    ap.add_argument("--ledger-devices", type=int, default=2000)
    ap.add_argument("--token", default="volume-token")
    args = ap.parse_args()
    rnd = random.Random(42)
    ws = args.workspace
    t0 = time.monotonic()
    db = SessionLocal()
    db.add(Workspace(id=ws, name=f"Volume ({args.assets} records)"))
    db.flush()
    schemas = {}
    for name in TYPES:
        s = Schema(uid=f"{ws}:{name.lower().replace(' ', '-')}", workspace_id=ws, name=name, applies_to="objects")
        db.add(s)
        schemas[name] = s.uid
    db.flush()
    now = datetime.now(timezone.utc)
    assets = []
    for i in range(args.assets):
        kind = TYPES[i % len(TYPES)]
        assets.append({"uid": str(uuid.uuid4()), "workspace_id": ws, "schema_uid": schemas[kind],
                       "key": f"{ws.upper()}-{i:06d}", "name": f"{kind} {rnd.choice(WORDS)}-{i}", "type": kind,
                       "attributes": {"serial": f"SN{i:07d}", "manufacturer": rnd.choice(["Agilent", "Pfeiffer", "Danfysik"]),
                                      "argus_location": f"Rack {rnd.choice('ABCDEFGH')}{rnd.randint(1, 40)}"},
                       "inbound_relations": [], "outbound_relations": [], "is_global": False,
                       "record_status": "Active", "created_at": now, "updated_at": now})
    for chunk in batched(assets):
        db.execute(insert(Asset), chunk)
    uids = [a["uid"] for a in assets]
    n = len(uids)
    # Two outbound relations per record, to records spread across the set.
    relations = [{"workspace_id": ws, "from_asset_uid": uids[i % n], "to_asset_uid": uids[(i * 7 + 1) % n],
                  "relation_type": rnd.choice(["powers", "connected to", "located in", "controls"]),
                  "created_at": now}
                 for i in range(2 * n) if (i * 7 + 1) % n != i % n]
    for chunk in batched(relations):
        db.execute(insert(Relation), chunk)
    tickets = [{"uid": str(uuid.uuid4()), "workspace_id": ws, "asset_uid": rnd.choice(uids),
                "title": f"{rnd.choice(['Fault', 'Noise', 'Leak', 'Trip', 'Drift'])} on {rnd.choice(WORDS)} {i}",
                "description": "synthetic", "state": rnd.choice(["new", "in_progress", "pending", "closed"]),
                "attributes": {}, "labels": [], "version": 1,
                "created_at": now - timedelta(days=rnd.randint(0, 900)), "updated_at": now}
               for i in range(args.tickets)]
    for chunk in batched(tickets):
        db.execute(insert(Issue), chunk)
    # The subject link a ticket gets when it is created through the API.
    links = [{"workspace_id": ws, "ticket_uid": t["uid"], "asset_uid": t["asset_uid"], "role": "subject",
              "certainty": "definite", "origin": "ticket"} for t in tickets]
    for chunk in batched(links):
        db.execute(insert(TicketLink), chunk)
    docs, revs, rels = [], [], []
    for i in range(args.documents):
        uid = str(uuid.uuid4())
        docs.append({"uid": uid, "workspace_id": ws, "code": f"{ws.upper()}-DOC-{i:05d}",
                     "title": f"Procedure {rnd.choice(WORDS)} {i}", "authority_level": "informativo",
                     "confidentiality": "interno", "source": "manual", "is_global": False, "retention_class": "5y",
                     "created_at": now, "updated_at": now})
        revs.append({"uid": f"{uid}-r1", "document_uid": uid, "revision_number": 1, "state": "draft",
                     "body_markdown": "synthetic", "steps": [], "attributes": {}, "created_at": now, "updated_at": now})
        rels.append({"workspace_id": ws, "from_document_uid": uid, "to_type": "schema",
                     "to_uid": schemas[TYPES[i % len(TYPES)]], "relation_type": "applies to", "created_at": now})
    for table, rows in ((Document, docs), (DocumentRevision, revs), (DocumentRelation, rels)):
        for chunk in batched(rows):
            db.execute(insert(table), chunk)
    raw = args.token
    db.add(ApiToken(workspace_id=ws, token_hash=hash_token(raw), restricted_grants=[]))
    db.commit()
    loaded = time.monotonic() - t0

    # A configuration through the ledger, so re-projection has work.
    stream = engine.register_stream(db, f"epik8s:{ws}#values.yaml@main", ws, "epik8s", facility="VOL",
                                    may_create=["IOC", "Control Device", "Equipment Position"])
    engine.activate_policy(db)
    lines = ["beamline: VOL", "epicsConfiguration:", "  iocs:"]
    per_ioc = 50
    for n in range(0, args.ledger_devices, per_ioc):
        lines += [f"    - name: vac-{n // per_ioc:03d}", "      devgroup: vac", "      devices:"]
        lines += [f"        - {{name: SIP{n + k:05d}, channel: {k}}}" for k in range(min(per_ioc, args.ledger_devices - n))]
    t1 = time.monotonic()
    engine.ingest(db, stream.id, revision="v1", content="\n".join(lines).encode(), observed_at=now,
                  parser="epik8s-slice")
    db.commit()
    ingested = time.monotonic() - t1
    print(json.dumps({"workspace": ws, "token": raw, "assets": args.assets, "relations": len(relations),
                      "tickets": args.tickets, "documents": args.documents, "ledger_devices": args.ledger_devices,
                      "bulk_load_s": round(loaded, 1), "ledger_ingest_s": round(ingested, 1),
                      "probe_assets": rnd.sample(uids, 40)}))
    db.close()


if __name__ == "__main__":
    main()
