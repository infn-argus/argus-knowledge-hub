# ARGUS API: versions and deprecation

This is the policy asked for in asset-model-revision §19 item 8. The API
publishes it at `GET /v1/meta/api`, together with the endpoints deprecated
now.

## Versions

- The major version is in the path: `/v1/…`. Every response also names it
  in the `X-ARGUS-API-Version` header.
- Within a version, changes are **additive only**: new endpoints, new
  optional request fields, new response fields, and new values where a
  client is told to expect more (states, kinds, record types). Clients
  must ignore fields they do not know.
- Removing or renaming an endpoint, a field or an accepted value, or
  changing a field's meaning or type, needs a new major version.

## Deprecation

- An endpoint is deprecated by adding it to `DEPRECATIONS` in
  `backend/app/services/api_policy.py`. That entry is the whole
  announcement: it gives the date, the sunset and the successor.
- From then on, each response from it carries these headers:
  - `Deprecation: @<unix time>` (RFC 9745);
  - `Sunset: <HTTP date>` (RFC 8594);
  - `Link: <successor>; rel="successor-version"`.
- The sunset is at least **180 days** after the deprecation. A test fails
  the build otherwise.
- After its sunset, the endpoint answers **410 Gone** and names its
  successor.

## External identifiers

Jira issue keys, Jira URLs (browse, board and search links), Insight
object keys and objectIds stay resolvable for as long as ARGUS runs:

- `GET /v1/lookup/{identifier}` returns the record an identifier became,
  following merges, or where it can still be read if it was never
  migrated;
- `POST /v1/lookup/batch` with `{"identifiers": [...]}` resolves up to
  1000 at once, in order, for an integration that re-points its stored
  references.

Both answer only with what the caller may see: a restricted record the
caller cannot read is reported as not migrated.

## The committed contract

`backend/openapi/openapi.json` is the whole API. `backend/openapi/field-client.json` is the subset
the field client calls, with stable operation names. Both are written by
`python -m app.contract`, run from `backend/`, and committed. A test fails when the API and the
committed files differ, so a contract change is always a reviewed diff. The Dart client in
`mobile/packages/argus_api` is generated from the subset (`mobile/tool/generate_api.sh`).

## Clients and devices

- **Client header:** every client may send `X-ARGUS-Client: <name>/<version>/<platform>`. It is
  required only in practice, not by the API.
- **Minimum version:** when a client is older than the minimum for its name, the API answers
  **426** with `{"code": "client_too_old", "minimum": "<version>"}`. The minimum for `flutter` is
  `ARGUS_MIN_FLUTTER_VERSION`, 0.1.0 by default.
- **Device registry:**
  - `POST /v1/devices` registers an installation of the field client. Registering the same
    installation again returns the same device.
  - `GET /v1/devices` lists your devices, or every device for an administrator.
  - `POST /v1/devices/{id}/revoke` with a reason revokes one.
- **Revoked devices:** a request carrying `X-ARGUS-Device` of a revoked device answers **401**
  `{"code": "revoked"}`. The client then wipes what it keeps.

## Universal links

`GET /v1/links/resolve?path=<path or https URL>` says which record a link opens:
- the kinds are asset, position, installation, document, ticket, review and lookup;
- it answers the record's kind, uid and web path.

A missing record and one the caller may not see give the same 404.

For `/lookup/<value>`, the lookup tries the following in order:
1. an external key (Jira, Insight, a former key);
2. a serial, an inventory number or a MAC that the caller can see.

A value held by more than one record answers **409** `{"code": "ambiguous", "candidates": [...]}`,
and nothing is opened.

The web application serves the same paths (`/asset/<uid>` and so on) and redirects them through
the resolver.

## Errors: one problem shape

Every error keeps its `detail`, as before, and also carries a top-level `problem`:

```json
{"detail": "...", "problem": {"error": "a person-readable sentence", "code": "stale",
  "invariant": "I-INS-1", "field": "attr:serial", "current": {"version": 42}, "review_item": "…"}}
```

Clients decide from `code`, never from the text. The codes are:
- `invalid`, `unauthenticated`, `forbidden`, `not_found`, `conflict`, `gone`;
- `stale`, `invariant`, `too_large`, `client_too_old`, `revoked`, `ambiguous`;
- `idempotency_mismatch`, `in_progress`, `rate_limited`, `server_error`.

The other keys appear only when they apply. A validation error names the `field`.

## Retries: idempotency keys

Any `POST`, `PUT`, `PATCH` or `DELETE` may carry `Idempotency-Key: <uuid>`. The key is kept per
workspace and per principal. Reuse it for every retry of the same command.

| Situation | Answer |
|---|---|
| The same key and the same request | The stored answer, with `Idempotent-Replayed: true`; nothing runs again |
| The same key and a different request | 422 `idempotency_mismatch` |
| The first request is still running | 409 `in_progress` with `Retry-After` |

Server errors, 401, 426 and 429 are not stored, so a retry of those runs again. Keys expire after
the offline retention (`ARGUS_OFFLINE_RETENTION_DAYS`, 7 by default) plus seven days;
`python -m app.ledger escalate` removes expired ones.

## Edits: record versions

Single-record reads return an `ETag`:
- for an asset, the latest ledger event that touched it (also returned as `version` in the body);
- for a ticket, its `version`;
- for a document, the current revision and its state.

An edit may send the version it read as `If-Match`: `PUT /v1/assets/{uid}`, `PUT /v1/issues/{uid}`
and `POST /v1/issues/{uid}/transition`. If the record has changed since then:

| What changed since the version sent | Answer |
|---|---|
| Nothing the edit touches | The edit is applied |
| A field the edit touches | 409 `stale`, with the current values |
| A protected field the edit touches (serial, inventory number, IP, MAC, FQDN, safety class, `acts on`, and the policy's protected predicates) | 409 `stale` with a `review_item`; the edit waits in the review queue as a `stale_command` and is not applied |

A person closes a `stale_command` review item with
`POST /v1/ledger/review/stale/{id}/close`, `{"outcome": "applied" | "dismissed"}`.

`POST /v1/installations/replace` is the guided replacement (flutter-app-design §8).
- `dry_run: true` returns the checks and the consequences, and writes nothing.
- A submission answers 200 `applied`, or 202 `proposed` with a `review_item`. A
  `discrepancy_item` is added when the scanned outgoing unit is not the recorded one.
- An approver decides a proposal with `POST /v1/ledger/review/replacements/{id}/confirm` or
  `/reject`.
- `GET /v1/ledger/review/mine` lists the review items routed to the caller, with the decisions
  the field client may take on each.

`POST /v1/installations/swap` accepts `seen_installation_uid`, which is `null` for an empty
Position, and `evidence`. If the Position's current Installation is no longer the one the person
saw, nothing is ended or started, and the replacement becomes a review item with the evidence.

## Files: resumable uploads

1. `POST /v1/uploads` with `{filename, content_type, size, sha256}`. It is refused before any byte
   is sent if it is too large (413 `too_large`, with `limit`) or of a type not accepted.
2. `PUT /v1/uploads/{uid}?offset=N` sends the next piece, at most 8 MB, as the raw body. A piece
   at another offset gets 409 with `current.offset`. `GET /v1/uploads/{uid}` says where to resume.
3. `POST /v1/uploads/{uid}/complete` verifies the size and the SHA-256. On a mismatch the bytes are
   discarded and the client starts again. EXIF GPS is removed from JPEG, PNG and WebP images.
4. `POST /v1/uploads/{uid}/attach/ticket/{issue_uid}` or `.../attach/asset/{asset_uid}` attaches
   the file. Attaching the same upload again does nothing.

The limits are set per environment until decision U23:
- `ARGUS_UPLOAD_MAX_IMAGE`, 25 MB by default;
- `ARGUS_UPLOAD_MAX_VIDEO`, 200 MB by default;
- `ARGUS_UPLOAD_MAX_OTHER`, 50 MB by default;
- `ARGUS_UPLOAD_TYPES`, the accepted types.

Unfinished uploads expire like idempotency keys.
