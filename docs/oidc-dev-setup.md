# A local Keycloak, for testing multi-workspace users before INFN's own IdP exists

*What this stands up, what it deliberately does and doesn't simulate about GODiVA, six test
users covering the permission model, and what's still needed before this is a login button
rather than a curl recipe.*

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
the second exists purely so a token can be fetched by curl, for the CI/no-browser case, until §5's
frontend flow exists), and the six users below. Nothing else in the stack requires it: a PAT login
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

## 5. What this doesn't give you yet

- **No login button.** `webapp/src/auth/TokenGate.tsx` signs in through Firebase's own SDK
  (`signInWithPopup`, `GoogleAuthProvider`) — hardcoded to one Firebase project, not a generic
  OIDC/Authorization-Code redirect. Standing up Keycloak doesn't make it appear in the browser;
  that needs its own client-side work (an OIDC library such as `keycloak-js` or `oidc-client-ts`,
  a redirect + PKCE + callback route, and a decision about whether it replaces the Firebase path or
  sits beside it) — a separate, sizeable piece I haven't built and didn't want to start without
  you weighing in on that decision.
- **No group-based provisioning**, for the reason in §2: that is a directory sync, not an OIDC
  claim, and no directory is standing behind this Keycloak.
- **`RoleBinding`s are hand-seeded**, standing in for whatever will eventually create them —
  an admin, an import, or a future GODiVA-group sync.

## 6. Pointing this at the real thing, later

Nothing above is Keycloak-specific in the backend. Swapping in a real identity provider — INFN's
Keycloak, GODiVA-fed or not — is `OIDC_ISSUER`, `OIDC_JWKS_URI` and `OIDC_AUDIENCE` pointed at it
instead, in whichever environment is being deployed. Everything downstream — `_resolve_oidc_user`,
`RoleBinding`, `Membership`, the permission checks — reads only the decoded claims and doesn't
know or care which provider signed them.
