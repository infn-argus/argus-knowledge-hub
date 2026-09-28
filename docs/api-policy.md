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
