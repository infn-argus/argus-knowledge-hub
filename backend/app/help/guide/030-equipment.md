---
title: Equipment (assets)
summary: Registering equipment and positions, types and attributes, relations, labels and QR codes, history and provenance, bulk changes.
keywords: [asset, assets, equipment, object, record, type, schema, attribute, relation, label, qr code, history, provenance, bulk change, catalogue, position, installation, spare, lifecycle, custody]
order: 30
---

An **asset** (also *object* or *record*) is a piece of equipment, a place in the machine where equipment
goes (a *position*), or anything else worth tracking: a rack, a cable run, a software service. Every
asset has a **type**, which decides its **attributes**.

## Find equipment

- **Assets → Browse & search**: filter by type, text and attributes.
- The **search box** at the top (Ctrl K / ⌘ K) finds assets, tickets and documents together.
- **Ask ARGUS** answers in your own words ("which ion pumps are in the gun area?").

## Register a new asset

1. **+ New → Asset**.
2. **Type**: start typing what it is (`ion pump`, `power supply`…) and pick the type. The type decides
   which attributes the form asks for.
3. **Name**, and the **Attributes** you know: manufacturer, model, serial number, inventory number…
   The **key** is made for you from the workspace's pattern (*Keys*), unless you type one.
4. Save.

The side panel helps while you type: the **Checklist** says what is missing or wrong (a key already
taken, a serial number another record holds, a likely duplicate) and what to answer next. With an AI
endpoint configured, **Describe it** fills the form from a sentence, a nameplate photo or a datasheet
(see *Guided and AI-assisted entry*).

## An asset's page

| Part | What it holds |
|---|---|
| **Attributes** | the typed values; a value maintained from a source shows where it came from |
| **Relations** | links to other records: what powers it, what it is part of, where it is installed… |
| **Comments** | notes from people |
| **Attachments** | files: datasheets, photos, drawings |
| **History** | every change, who made it and when |
| **Labels** | printed labels and QR codes |
| **Provenance** | for each value, the source and the decisions behind it |
| **Lifecycle & custody** | state (in use, spare, under repair…), custodian, location, with their history |

It also lists the asset's **tickets** and the **documents** that apply to it (its own, its model's and
its type's).

## Relate two assets

On the asset's **Relations**, add a relation, choose its kind (for example *powers*, *part of*,
*composed of*, *acts on*) and the other record (*Target asset…*). ARGUS refuses a relation its rules
forbid (wrong kinds of record at either end, too many of one kind, a loop) and says why.

A relation that a source or an installation maintains is marked as such: change its source, not the
relation.

## Types and the catalogue

**Assets → Type catalogue** shows every type you can use: where it sits in the tree, what it means, its
attributes (own and inherited), the names imports know it by, and how many records it has. Types are
shared between workspaces through a *catalogue* workspace; a workspace's own types sit under them.

## Labels and QR codes

**Assets → Labels & QR codes** prints labels for many assets at once. A QR code opens the asset's page;
**Scan a code** on an asset's page links a label already on the equipment.

## Change many at once

**Assets → Bulk changes** sets an attribute on, or retires, many records at once. It always shows a
preview first; above 100 records a second person approves it; it is applied, and can be undone, as one
batch.

## Positions, installations and spares

A **position** is a place in the machine (a slot in the lattice, a rack position); **equipment** is the
unit installed there. Installing, swapping or removing a unit keeps the position's history: "what was
installed here on 3 March" has an answer. Spares show which positions they fit.

## Global values and equipment classes

- **Assets → Global values**: shared lists (statuses, priorities…) used by many types.
- **Assets → Equipment classes**: the classes of equipment with no type of its own (*Other Equipment*),
  and when one deserves a type.
