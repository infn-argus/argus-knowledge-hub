---
title: The knowledge graph
summary: Seeing how records are connected, what stops if something fails, and what could cause a fault.
keywords: [graph, knowledge graph, connections, relations, impact, what depends, root cause, causes, failure, blast radius, single point of failure]
order: 90
---

The **Knowledge graph** (side bar) shows records and their relations: what powers what, what is part of
what, which IOC acts on which equipment, which documents apply.

## Explore

1. Open **Knowledge graph** and pick a record (or open it from a record's page).
2. **Centre here** on any record to move around. *Inbound* and *Outbound* show the two directions of a
   relation.
3. Choose the **layers** (control, power, cooling, vacuum, timing…) to follow only those kinds of
   relation.

## What stops if it fails?

Pick a record and ask **What stops if it fails?**: ARGUS follows the relations the way a failure
travels (a power supply stops its magnet; an IOC that stops leaves its devices unread, but still
working) and lists what is affected and how it is reached.

## It misbehaves: find causes

For a fault, use **It misbehaves: find causes**: add what misbehaves and, if you know, what still works.
ARGUS walks back to the records that could explain all of it, most likely first.

Ask ARGUS can do both in words: "what depends on the chiller CHL01?", "the gun vacuum and the RF both
tripped: what could cause it?".
