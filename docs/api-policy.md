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
