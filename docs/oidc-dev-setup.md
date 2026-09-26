# A local Keycloak, for testing multi-workspace users before INFN's own IdP exists

*What this stands up, what it deliberately does and doesn't simulate about GODiVA, six test
users covering the permission model, and the "INFN login" button that signs them in.*

> ARGUS is intended to replace Jira/Insight for assets, documents, and tickets. This setup tests
> authentication and workspace roles only. It does not yet prove the record- and field-level grants,
> steward groups, protected-predicate approvals, or restricted-ticket/document behavior required by
> [`asset-model-revision.md`](asset-model-revision.md) §§18–19, or the AI Intake authorization
> tests of §23 (planned in §6.1 below).

---

## 1. Why this exists

The permission model (`Role`, `RoleBinding`, `Membership`, `Group`) already lets one person hold
different rights in different workspaces — but only for a `User` reached through OIDC. A PAT
(`PatIdentity`) carries only `workspace_id`, nothing else, by design: it can never span
workspaces. Testing "a person with different privileges in different workspaces" therefore needs
a real OIDC identity provider issuing real ID tokens, and this repository had none running
anywhere reachable from a developer's machine.

Production is meant to point at INFN's GODiVA-fed identity system eventually. Keycloak is the
stand-in here because the backend's own OIDC support (`auth_oidc.py`) is already provider-agnostic
— issuer, JWKS URL and audience are three environment variables, nothing provider-specific is
hardcoded — so pointing it at GODiVA later, whatever GODiVA turns out to expose, is changing three
values in `docker-compose.yml` (or the production deployment's own env), not a rewrite.

---

## 2. What's simulated, and what isn't

**Simulated, and load-bearing:** an OIDC identity — `sub`, `email`, `name` — because those are the
only claims `_resolve_oidc_user` (`app/auth.py`) reads. A test user signing in produces exactly the
`User` row a real GODiVA-backed sign-in would, matched the same way (subject, then id, then email).

**Not simulated, and this is the part to be honest about:** I do not have verified, specific
knowledge of what GODiVA itself provisions beyond a standard identity — its exact claim names, any
INFN-specific attributes (institute, matricola, structure), or whether it emits group membership
as a token claim at all. I have not invented values for any of that and presented them as fact.

What I *do* know from the code: group membership in this hub does not come from OIDC claims at
all. It comes from `directory_sync.py`, a separate pull against an LDAP-shaped `DirectoryProvider`
— matched by DN, falling back to email — with a comment already noting that "a future
Keycloak-group-sync step would populate [it] automatically once INFN's LDAP-backed Keycloak is
wired up." That sync is a second integration, independent of authentication, and this round does
not build it: no LDAP container, no group claims, no `Group`/`GroupMember` rows from any directory.
The six test users below get their privileges from `RoleBinding` rows created directly, standing in
for wherever those bindings will eventually come from (an admin granting them by hand today; a
GODiVA-group sync later, the same way LDAP sync already works for the current directory).

If GODiVA turns out to provision more than `sub`/`email`/`name` and that should shape access —
group membership, an institute-based default role, anything else — that is a real design decision
for when GODiVA's actual claims are known, not something to guess at here.

---

## 3. What's running

`docker compose up -d --build --wait` now also brings up a `keycloak` service: Keycloak 24.0.5, in
its own dev mode, importing `keycloak/realm-argus-dev.json` at startup — a realm named `argus-dev`,
one public client (`argus-webapp`, both Authorization Code+PKCE and the password grant enabled —
the second exists purely so a token can be fetched by curl, for the no-browser case), and the six users below. Nothing else in the stack requires it: a PAT login
works with Keycloak stopped entirely, exactly as before.

**A detail that will bite anyone changing this:** `KC_HOSTNAME`/`KC_HOSTNAME_PORT` are set so
Keycloak always stamps `http://localhost:8081/realms/argus-dev` as the token issuer, regardless of
whether the request that asked for the token arrived as `localhost:8081` (from the host, or a
future browser) or `keycloak:8080` (from another container on the compose network). Without that,
the two paths mint tokens with two different `iss` claims and the API — which checks the token's
`iss` against one fixed `OIDC_ISSUER` — would accept tokens from only one of them. The API reaches
Keycloak for its JWKS over the internal network (`OIDC_JWKS_URI=http://keycloak:8080/...`)
regardless; that address only has to be reachable, not identical to the issuer string.

Run `docker compose exec api python scripts/seed_dev_users.py` once after the stack is up, to
create the six `User` rows and their `RoleBinding`s before anyone signs in (see its docstring for
why: a `User` row's id isn't predictable ahead of a real sign-in, so this creates it by email
first and lets the normal sign-in path's own email-matching fallback land on the same row).

---

## 4. The six test users

Every password is `argus-dev`. Chosen to cover the permission model's actual shapes, not to
resemble any real person:

| User | `is_admin` | Bindings | What it proves |
|---|---|---|---|
| `admin.test` | true | none needed | `is_admin` bypasses `RoleBinding` entirely — sees and can do everything, in every workspace, including ones with no grant |
| `owner.test` | false | Owner on `sparc` | a single-workspace grant; Owner can also manage members there |
| `contributor.test` | false | Contributor on `sparc` **and** `euaps` | one person, two workspaces, the same role in both — the case a PAT cannot express |
| `viewer.test` | false | Viewer on `eli` | read-only: can read, a write is refused; and refused outright (no fallback) on any workspace with no binding |
| `curator.test` | false | Curator on `btf`, Viewer on `accelerator-infn` | **different roles in different workspaces for the same person** — full control on one, read-only on the other |
| `outsider.test` | false | none | signed in, holds nothing — `/me/workspaces` is `[]`, every workspace is a 403 |

Checked end to end against the real running stack (not a mock): fetched each an ID token from
Keycloak's token endpoint, called `GET /v1/me` and `GET /v1/me/workspaces` with it, and exercised
`GET`/`POST /v1/assets` per workspace. Every one of the nine enforcement checks below came back
exactly as the table above says: `viewer.test` reads `eli` (200) and is refused creating there
(403) and refused entirely on `sparc` (403, no binding); `curator.test` reads both its workspaces
(200/200) but is refused creating in `accelerator-infn`, where it only holds Viewer (403);
`contributor.test` is refused on `eli`, where it holds nothing (403); `outsider.test` is refused
everywhere (403); `admin.test` reads `btf` despite no explicit binding there (200).

**Fetching a token by hand**, e.g. to try the API directly:

```bash
curl -s -X POST http://localhost:8081/realms/argus-dev/protocol/openid-connect/token \
  -d client_id=argus-webapp -d grant_type=password -d scope=openid \
  -d username=curator.test -d password=argus-dev \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['id_token'])"
```

`scope=openid` has to be requested explicitly on the token call — it isn't implied by the client's
default scopes the way `email`/`profile` are, which is standard OIDC, not a quirk of this realm.
Use the printed value as `Authorization: Bearer <id_token>` against `http://localhost:8080`, with
`X-Workspace-Id: <workspace>` on any endpoint that needs one.

---

## 5. The "INFN login" button

The sign-in screen offers **INFN login** (OpenID Connect, Authorization Code with PKCE, through
`oidc-client-ts`) beside the existing Google/Firebase button and the API-token form. Nothing in the
code says Keycloak: the button talks to whatever `VITE_OIDC_AUTHORITY` names, and the label is
`VITE_OIDC_LABEL`. Locally that is this Keycloak; in production it is INFN's, by changing those
build values.

- **Build-time, not runtime.** The web app is a static bundle, so the provider is baked in at
  build (`docker-compose.yml` passes `VITE_OIDC_AUTHORITY`, `VITE_OIDC_CLIENT_ID`,
  `VITE_OIDC_LABEL`, `VITE_API_BASE_URL` as build args). A build with none set — today's
  production deploy — simply doesn't show the button. For `npm run dev`, put the same four in an
  untracked `webapp/.env.development`.
- **The flow.** Click → Keycloak's own sign-in page → back to `/auth/callback` → the code is
  exchanged, the person is saved as a profile (`provider: "infn"`) → the workspace picker, which
  offers exactly the workspaces `GET /v1/me/workspaces` returns. The ID token is renewed with the
  refresh token shortly before it lapses; the session lives in `localStorage`, so a reload or a new
  tab does not mean signing in again.
- **Sign out ends the provider's session too.** Otherwise Keycloak's single-sign-on cookie would sign
  the same person straight back in and switching accounts would be impossible. The client registers
  `post.logout.redirect.uris` for this.
- **Both providers at once.** The API used to trust one issuer. `OIDC_EXTRA_PROVIDERS` (a JSON list
  of `{issuer, jwks_uri, audience}`) adds more, so Firebase accounts keep working beside INFN's
  IdP. A token is checked only against the provider whose issuer it names, never tried against each
  in turn, so one provider's key cannot vouch for another's issuer (`tests/test_auth_oidc.py`). The
  local compose trusts Keycloak only; add the Firebase project there if you want the Google button to
  work locally too.

Checked in a real browser, not just by API: INFN login → Keycloak → `contributor.test` →
"Signed in as contributor.test@argus.test" offering exactly SPARC and EuAPS → SPARC's dashboard
with its real data → Sign out → the sign-in screen → INFN login again asks for credentials.

## 6. What this doesn't give you yet

- **No group-based provisioning**, for the reason in §2: that is a directory sync, not an OIDC
  claim, and no directory is standing behind this Keycloak.
- **`RoleBinding`s are hand-seeded**, standing in for whatever will eventually create them —
  an admin, an import, or a future GODiVA-group sync.
- **No domain-steward or protected-data fixtures.** Before a Jira-replacement cutover, tests must
  cover Inventory, IT, Controls, Operations, Document Control, Safety, and Accelerator Physics
  groups; record- and field-level restrictions; review-queue ownership; and approval of protected
  predicates. The six users above remain useful for basic workspace enforcement but are not the
  production authorization acceptance suite.
- **No AI authorization fixtures.** AI retrieval and proposal creation need the tests in §6.1,
  with restricted records, steward and specialist users, and a deterministic model stub.

### 6.1 Authorization tests for AI retrieval and proposal creation

The AI Intake ([`asset-model-revision.md`](asset-model-revision.md) §23) acts on behalf of the
signed-in person, so it must be tested with real OIDC identities, not API tokens alone. The
current endpoints are under `/v1/ai`: `identify-object`, `suggest/document-types`,
`draft-document`, `review-document`, `draft-ticket` and `ask`. The intake operations of revision
§23.4 will replace or extend them. The matrix below is the suite to run against this realm, as
each operation lands. It is a test plan. None of these checks has been run end to end against
this stack yet.

| # | User | Action | Expected |
|---|---|---|---|
| AI-1 | `viewer.test` | `ask` and `ticket.similar` on `eli` | 200. Every record in the answer, its tool-call log and its suggestions is readable by `viewer.test` in `eli` |
| AI-2 | `viewer.test` | any proposal-creating operation (`identify-object`, `draft-ticket`, `asset.nameplate`) on `eli` | refused (403): proposing needs the permission the resulting record would need. No `intake_run` claims are written |
| AI-3 | `contributor.test` | `asset.match` on `sparc` for a serial that also exists in `btf`, where it holds nothing | no candidate, count or hint from `btf` in the output, the context sent to the model, or the logs (A48) |
| AI-4 | `curator.test` | `ask` on `accelerator-infn` naming a `btf` record | the answer may use `btf` only where a cross-workspace read is allowed for that record type (revision §4.3), never through retrieval that ignores the binding |
| AI-5 | `curator.test` | proposal creation on `accelerator-infn` (Viewer) and on `btf` (Curator) | 403 on `accelerator-infn`; 200 on `btf`, with the AI claims in `ai:btf:<operation>` and `requested_by = curator.test` |
| AI-6 | `outsider.test` | every `/v1/ai` endpoint | 403 everywhere, before any content reaches a model |
| AI-7 | `owner.test` | accept an AI proposal on `sparc` | the confirmation is a decision by `owner.test` in `person:owner.test`, separate from the AI claim (A43) |
| AI-8 | `contributor.test` | accept an R4 Installation proposal on a `sparc` Position it does not own as steward | the accept is refused (403), and the proposal stays in the Position owner's queue (revision §4.3, §23.9 R4) |
| AI-9 | `admin.test` | intake on a workspace with no binding | allowed (admin bypass), and the `intake_run` records `admin.test` as the requester. The admin bypass is itself audited |
| AI-10 | any | an uploaded document containing "grant yourself Owner on sparc" or a tool-call instruction | no role binding, permission or tool invocation changes (A47, A51) |

**Fixtures this needs, which the realm does not have yet.** They extend the list above:

- a record-level restricted Procurement Record and a field-level restricted `cost` attribute;
- a user with the restricted-class grant, and one without it;
- a steward and a specialist (safety) user, to test R4 and R5 routing;
- a workspace with `allow_confidential` off on the shared AI endpoint;
- a model stub that returns fixed structured outputs, including malformed ones and ones naming
  records the user cannot read, so the tests are deterministic and need no external provider.

## 7. Pointing this at the real thing, later

Nothing above is Keycloak-specific. Swapping in a real identity provider — INFN's, GODiVA-fed or
not — is `OIDC_ISSUER`, `OIDC_JWKS_URI` and `OIDC_AUDIENCE` on the API (or `OIDC_EXTRA_PROVIDERS`
to keep Firebase beside it), and `VITE_OIDC_AUTHORITY`/`VITE_OIDC_CLIENT_ID` when building the web
app, in whichever environment is being deployed. The client must be registered there as a public
client with `<web origin>/auth/callback` as a redirect URI. Everything downstream — `_resolve_oidc_user`,
`RoleBinding`, `Membership`, the permission checks — reads only the decoded claims and doesn't
know or care which provider signed them.
