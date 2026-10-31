# Catalogue sources

The shared catalogue's Vendor and Product Model records come from two Git repositories, each pinned to a
reviewed revision (docs/catalogue-collections.md):

- `infn-argus/argus-catalogue` — ARGUS-native collections: manufacturers, accelerator equipment, and the
  ARGUS metadata of IT models (CC0-1.0);
- `infn-argus/devicetype-library` — the fork of the NetBox Device Type Library, for IT devices.

This directory will hold the lock file that pins them (stage R3). Until then it is empty: the draft collections
that were here were examples, not checked against manufacturer documentation, and were removed.

    python -m app.catalogue validate                     # the collections in ARGUS_CATALOGUE_DIR (default: here)
    python -m app.catalogue validate --against <dir>     # and against the previous release
