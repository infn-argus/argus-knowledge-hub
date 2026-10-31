# Catalogue collections

The reusable Vendor and Product Model records, reviewed in Git and installed into the shared catalogue
workspace. The format, the rules and how a release is installed: docs/catalogue-collections.md.

    python -m app.catalogue validate                     # every collection here, together
    python -m app.catalogue validate --against <dir>     # and against the previous release (a checkout of the last tag)

These first collections are **drafts (0.x)**: a few representative entries, to be revised once the read-only
inventory of the production catalogue has run. They hold no site data: no serial numbers, positions, prices or
people.
