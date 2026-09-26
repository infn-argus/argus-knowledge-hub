# ARGUS design documentation

The documents in this directory play different roles. Read them in this order:

1. [`asset-model-revision.md`](asset-model-revision.md) is the **normative architecture**. It
   defines the production model, governance, migration, and the decision that ARGUS replaces Jira
   and Insight as the system of record for assets, documents, and tickets. §23 defines the
   **AI Intake**, the governed path for LLM-assisted data entry.
2. [`asset-schema-design.md`](asset-schema-design.md) and
   [`it-model-design.md`](it-model-design.md) are **baseline design and evidence documents**. Their
   measurements and source analysis remain useful, but any model or operational rule that conflicts
   with the normative architecture is superseded. Each has a section on what AI extraction may
   propose for its records (AS §16, IT §6.1).
3. [`knowledge-graph-design.md`](knowledge-graph-design.md) describes the current causal-analysis
   implementation and its migration to the governed relation registry. §3.1 separates graph
   consequences from AI hypotheses.
4. [`element-panorama.md`](element-panorama.md) records what the source matrices and control
   configurations contain. It is evidence for import rules, not an authority for physical-asset
   identity. §4.1 covers AI-supported extraction from matrices and photographs.
5. [`flutter-app-design.md`](flutter-app-design.md) is the product and engineering design of the
   **Flutter field client**:
   - the split with the web application;
   - architecture, offline synchronization, security and deep links;
   - distribution, testing and rollout.

   Its rules are normative in `asset-model-revision.md` §24.
6. [`oidc-dev-setup.md`](oidc-dev-setup.md) is an independent development setup guide:
   - §6.1 lists the authorization tests for AI retrieval and proposal creation;
   - §6.2 lists those for the mobile client.

[`operations.md`](operations.md) and [`api-policy.md`](api-policy.md) document what is built and
how to run it.

## Architectural policy

ARGUS will become the system of record for assets, documents, tickets, Positions, Installations,
and their relationships. Jira and Insight are migration sources and temporary read-only archives.
Migration occurs domain by domain, without permanent bidirectional synchronization or a prolonged
dual-write period.

A Flutter field client is a first-class companion to the web application, for work next to
the equipment. It uses the same API and rules, and it does not replace the web application.
Governance, bulk work and document control stay web-first.

AI-assisted data entry is a first-class, optional capability:

> The LLM may propose facts, classifications, relationships, matches, and drafts. Only
> deterministic validation, ARGUS authority policy, and authorized human decisions make them
> authoritative.

## Architecture in one picture

```text
 Web application (React)              Flutter field client (Android, iOS)
 desk work: governance, bulk,         field work: scan, lookup, capture, inspections,
 document control, reconciliation     replacements, incidents, assigned reviews, offline drafts
            │  generated TS client               │  generated Dart client · pending commands
            └───────────────┬────────────────────┘
                            ▼
 ARGUS API /v1 (versioned OpenAPI): authN/authZ · idempotency · record versions
            │
            ├── AI Intake: extract, classify, normalize, suggest
            │   (requesting user's permissions; untrusted content; server-side only)
            │        ▼
            │   validation, identity resolution, registry, policy and permission checks
            │        ▼
            │   reviewable proposals with evidence and confidence
            ▼
 claims (people, importers, AI) ─▶ append-only fact ledger ◀─ decisions (people, declared policies)
                                            │
                                            ▼
                    current-state projection (attributes, asserted relations, status)
                                            │
                                            ▼
                    derived relations · confirmed and investigative graph views · analysis
```

**Nothing writes the projection directly:**
- **AI Intake** submits AI claims to the same ledger as the importers and people.
- **The field client** sends the same requests as the web application.
- **Offline work** is a pending command until the server accepts it.

An authorized decision, or a declared deterministic policy, decides what becomes authoritative
(`asset-model-revision.md` §23, §24).

## Terminology used by the current model

- A **Position** is a persistent functional place or role.
- **Equipment** is an individually tracked physical unit.
- An **Installation** records which Equipment occupied which Position over valid time.
- Imported, inferred, resolved, manual, and AI-proposed facts enter an append-only ledger. Current
  attributes and asserted relations are projections; shortcut graph edges are derived.
- Control configuration may create or infer Positions and control-plane records. It never creates
  authoritative physical Equipment. Neither does the AI Intake: it proposes, and people confirm.
- A **pending command** is work a client captured, usually offline. It is not a fact until the
  server accepts it.
- An **AI proposal** is an AI claim with its evidence, method (`ai_extracted`, `ai_resolved`,
  `ai_classified`, `ai_inferred`), confidence and model provenance. An **AI draft** is text a
  person edits before saving; it is never a claim by itself.

Measured counts in the evidence documents are not acceptance criteria until they have been
recomputed from frozen source revisions using explicit definitions. The baseline manifest required
by [`asset-model-revision.md`](asset-model-revision.md) is authoritative once produced.
