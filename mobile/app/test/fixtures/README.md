# Recorded API responses

These files are real responses of the ARGUS API, recorded from a local instance seeded with the
ledger slice (a configuration revision and an inventory export, one confirmed Installation, one
ticket, a published and a draft document). The widget and repository tests serve them through
`test/fake_server.dart`, so the generated client parses what the server actually sends.

Re-record them when the field contract changes (`backend/openapi/field-client.json`) and keep the
uids in `fake_server.dart` in step.
