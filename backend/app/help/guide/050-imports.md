---
title: Importing data
summary: Bringing equipment, tickets and documents in from EPIK8s, Jira, Confluence, Git and Markdown; re-running imports; mapping imported records.
keywords: [import, imports, epik8s, values.yaml, jira, insight, confluence, git, markdown, re-run, merge strategy, mapping, catalogue mapping, channels, hardware, infer elements]
order: 50
---

Imports read another system into the workspace you are in. They do not delete records: a re-import
updates what the source says, and what a person changed since the previous run is decided by the **merge
strategy** (by default, the person's value is kept).

## Where

The workspace's **Imports** page (bottom of the side bar) lists saved import configurations and past
runs. **New** starts one. Choose the source:

| Source | What it brings |
|---|---|
| **EPIK8s control** | a beamline's control configuration (`values.yaml`): IOCs, devices, services, and optionally the equipment they drive |
| **Jira objects** | Jira Insight / Assets objects |
| **Jira tickets** | Jira issues, as tickets |
| **Confluence** | a Confluence space's pages, as documents |
| **Git** | files from a Git repository |
| **Markdown** | Markdown files, as documents |

A configuration is saved with a name and can be **run again** whenever the source changes; each run
records what it read (for Git sources, the commit).

## Import an EPIK8s configuration, step by step

1. **Imports → New → EPIK8s control**.
2. **Configuration name**: for example `epik8s-btf`.
3. **Provider** (GitHub or GitLab), **Repository URL** (for example
   `https://baltig.infn.it/lnf-da-control/epik8s-btf.git`), **Branch** (`main`) and the path of the
   values file (`deploy/values.yaml`). **Personal access token**: only for a private repository; leave
   it blank for a public one.
4. Options:
   - **Infer equipment and lattice elements (rules)**: also make what the channels drive, which the file
     never lists: magnets and their supplies, ion pumps, cameras, BPMs, screens, mirrors… They are
     marked *inferred*; a person's later edits are kept on the next run under the default merge strategy
     (check the strategy before re-running).
   - **Infer controllers**: the controller box each IOC talks to.
   - **Link to units already in the inventory**: link a channel to equipment the inventory already
     holds instead of inferring a twin (as proposals under *Channels ↔ hardware*).
   - **Ask the AI about channels the rules don't recognise**: its answers are proposals in the Review
     queue.
   - **IT workspace for converters, servers and their ports**: optionally, a shared workspace where the
     serial converters and servers the hostnames name are made, once for all beamlines.
5. Save and run. The run page shows progress, then the counts and any warnings.

Notes:
- The workspace gets the catalogue's types automatically the first time.
- A file that is an **overlay** (such as `values-linac.yaml`, with no `beamline:` of its own) takes the
  beamline and its templates' defaults from the `values.yaml` beside it. Import the main file and the
  overlay as two configurations.

## After an import

- **Review queue**: inferred facts, AI proposals and conflicts wait there for a decision.
- **Assets → Channels ↔ hardware**: proposed links between control channels and inventory units.
- **Assets → Map imported records**: records imported as they were in Insight are mapped onto the
  workspace's types, with a plan per source type that a person reviews before it is applied.

## Merge strategy

When an import meets a value a person changed since the previous run, the strategy decides: keep the
person's value (default), take the source's, or take whichever is newer.

## Check an import before running it again

1. Confirm the destination workspace and the saved configuration.
2. Read the previous run's counts and warnings.
3. Open a few representative records and their **Provenance**.
4. Look at the inferred facts, conflicts and proposed hardware links waiting in the **Review queue**.
5. Check the **merge strategy**, especially after people edited imported values.

Re-run the saved configuration to update the same source. Something that disappeared from the source has not
necessarily been removed or retired at the facility: find out before you change it by hand.
