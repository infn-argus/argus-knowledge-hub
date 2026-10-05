---
title: The review queue
summary: Deciding on inferred facts, AI proposals, conflicts between sources and proposed installations.
keywords: [review, review queue, confirm, correct, reject, proposal, inferred, conflict, installation, decision, provisional]
order: 60
---

Some facts reach ARGUS without a person behind them: inferred by an import, proposed by the AI, or two
sources that disagree. They wait in the **Review queue** (side bar) until someone decides.

## What waits there

| Kind | Example |
|---|---|
| **Inferred or proposed facts** | an import inferred a power supply for a magnet channel; the AI proposed a unit type |
| **AI proposals** | values read from a datasheet with *Complete from a file* |
| **Conflicts** | Insight and the control configuration give different values for the same field |
| **Installations** | a unit appears at a position and someone must confirm it is installed there |

A record made only from proposals shows as **Provisional** until it is accepted.

## Decide

For each item: **Confirm** it as it is, **Correct** it (give the right value), or reject it. Each item
shows where it came from, its evidence and how sure the source was. Decisions are recorded in the
record's provenance.

Items have an age in working days; overdue ones are escalated to the backup steward, then to the
governance group.
