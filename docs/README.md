# ARGUS design documentation

The documents in this directory play different roles. Read them in this order:

1. [`asset-model-revision.md`](asset-model-revision.md) is the **normative architecture**. It
   defines the production model, governance, migration, and the decision that ARGUS replaces Jira
   and Insight as the system of record for assets, documents, and tickets.
2. [`asset-schema-design.md`](asset-schema-design.md) and
   [`it-model-design.md`](it-model-design.md) are **baseline design and evidence documents**. Their
   measurements and source analysis remain useful, but any model or operational rule that conflicts
   with the normative architecture is superseded.
3. [`knowledge-graph-design.md`](knowledge-graph-design.md) describes the current causal-analysis
   implementation and its migration to the governed relation registry.
4. [`element-panorama.md`](element-panorama.md) records what the source matrices and control
   configurations contain. It is evidence for import rules, not an authority for physical-asset
   identity.
5. [`oidc-dev-setup.md`](oidc-dev-setup.md) is an independent development setup guide.

## Architectural policy

ARGUS will become the system of record for assets, documents, tickets, Positions, Installations,
and their relationships. Jira and Insight are migration sources and temporary read-only archives.
Migration occurs domain by domain, without permanent bidirectional synchronization or a prolonged
dual-write period.

## Terminology used by the current model

- A **Position** is a persistent functional place or role.
- **Equipment** is an individually tracked physical unit.
- An **Installation** records which Equipment occupied which Position over valid time.
- Imported, inferred, resolved, and manual facts enter an append-only ledger. Current attributes
  and asserted relations are projections; shortcut graph edges are derived.
- Control configuration may create or infer Positions and control-plane records. It never creates
  authoritative physical Equipment.

Measured counts in the evidence documents are not acceptance criteria until they have been
recomputed from frozen source revisions using explicit definitions. The baseline manifest required
by [`asset-model-revision.md`](asset-model-revision.md) is authoritative once produced.
