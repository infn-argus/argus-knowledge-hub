# ARGUS Field (Flutter)

The field client of ARGUS, for work next to the equipment. The design is
[`docs/flutter-app-design.md`](../docs/flutter-app-design.md). Its normative rules are in
[`docs/asset-model-revision.md`](../docs/asset-model-revision.md) §24.

This is phase **M1, the read-only client**. It does the following:

- **Sign-in:**
  - OIDC with PKCE through the system browser on Android and iOS;
  - a token in development and staging builds only;
  - after sign-in, it registers the device (`POST /v1/devices`) and asks for the workspace.
- **Finding a record:**
  - scan a QR code, DataMatrix or barcode, or type the label;
  - or search by key, name, serial, ticket or document.
- **Reading:**
  - Equipment and Positions, with what is installed there now and its history, open tickets and
    applicable documents;
  - ticket details;
  - documents, where the state (draft, not approved, superseded, review overdue) is shown before
    the content.
- **Links:** universal links (`/asset`, `/position`, `/installation`, `/document`, `/ticket`,
  `/review`, `/lookup`) open the same record as in the web application.
- **Revocation and updates:**
  - a revoked device (401 `revoked`) is signed out and its session wiped;
  - a client too old for the server (426 `client_too_old`) stops at an update screen.

Capture, tickets, replacement and offline work are phases M2–M4 (§15 of the design).

## Layout

```text
mobile/
├── app/                   the Flutter application (package argus_field)
│   ├── lib/core/          configuration, session storage, the problem shape, the label parser
│   ├── lib/data/          ApiService (the only HTTP door) and the repositories
│   ├── lib/domain/        the models the screens use
│   ├── lib/features/      auth, home, scan, records, tickets, documents, diagnostics
│   ├── lib/app/           providers (Riverpod), router (go_router), theme
│   └── test/              unit and widget tests; fixtures recorded from a real API
├── packages/argus_api/    the generated Dart client (do not edit)
└── tool/generate_api.sh   regenerates it from backend/openapi/field-client.json
```

## The API contract

The server publishes two contract files, both committed:
- `backend/openapi/openapi.json`, the whole API;
- `backend/openapi/field-client.json`, the operations this client may call.

Regenerate both with:

```bash
cd backend && python -m app.contract
```

The backend test `tests/test_field_client.py` fails when the committed contract no longer matches
the API. After a contract change, regenerate the Dart client. This needs Java; the generator jar is
downloaded to `mobile/.tool/` the first time:

```bash
mobile/tool/generate_api.sh
```

Some untyped responses (hub contexts, search, the link resolver, devices, installations) are
decoded by `ApiService.json`, because the generator cannot deserialize an untyped value.

## Running

Configuration is set at build time with `--dart-define`; it is never typed by the user:

| Define | Default | Meaning |
|---|---|---|
| `ARGUS_ENV` | `development` | `production` removes the token sign-in |
| `ARGUS_API_BASE` | `http://localhost:8000` | the API, without `/v1` |
| `ARGUS_LINK_HOST` | `localhost` | the only host whose links a scanned label may open |
| `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_REDIRECT` | the Keycloak development realm, `argus-mobile`, `it.infn.argus.field:/oauthredirect` | sign-in |
| `ARGUS_APP_VERSION` | `0.1.0` | sent as `X-ARGUS-Client: flutter/<version>/<platform>` |

```bash
cd mobile/app
flutter pub get
flutter analyze
flutter test
# a device or emulator
flutter run --dart-define=ARGUS_API_BASE=http://10.0.2.2:8000
# the browser (development only: token sign-in, no camera on most desktops)
flutter run -d chrome --dart-define=ARGUS_API_BASE=http://localhost:8000
```

For a token, use `python backend/scripts/create_token.py <workspace> <name>`.

Android builds take the link host as a Gradle property, for the App Links intent filter:
`flutter build apk --dart-define=ARGUS_LINK_HOST=argus.example.org -PargusLinkHost=argus.example.org`.

## Before a release

The following are not in this repository yet (design §12):
- the signing configuration;
- the iOS associated-domains entitlement (`applinks:<host>`);
- the `assetlinks.json` and `apple-app-site-association` files served by the web host;
- the minimum iOS version required by `mobile_scanner`;
- distribution through the approved channel (U19).
