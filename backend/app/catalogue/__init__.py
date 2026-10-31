"""Catalogue collections: the reusable Vendor and Product Model records, kept in Git (docs/catalogue-collections.md).

A template package (app/packages) defines the Product Model and Vendor *types*; a collection holds the
*records* — the manufacturers and their models — that the shared catalogue workspace installs. This module reads
and checks them (`loader`, `validate`); nothing here writes to the database.

    python -m app.catalogue validate [<collection dir> …] [--against <previous catalogue dir>]
    python -m app.catalogue list
"""
