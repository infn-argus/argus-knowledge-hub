---
title: The beam model
summary: The machine's beam-transport model: importing it from MAD-X and other codes, editing it, and linking its components to the equipment.
keywords: [beam model, lattice, mad-x, madx, tfs, elegant, bmad, xsuite, accelerator toolbox, optics, aperture, beam path, component, element, asset sync, binding]
order: 100
---

The **beam model** describes how the beam travels: beam systems and beams, paths of components (open
lines and rings, with branches and merges), each component's definition, apertures, alignment and
datasets such as optics. It is independent of any simulation code, and linked to the real equipment.

## Bring a model in

1. **+ New → Beam model**.
2. Upload a file: the canonical `*.beam.json`, or a MAD-X, TFS, Elegant, Bmad, Xsuite or Accelerator
   Toolbox file (converted on the way in). Or start one from scratch in the editor.
3. ARGUS checks it and says how complete it is, level by level (topology, lattice, geometry, optics,
   physical, integrated) and what is missing for the next level.

## Look at and edit a model

**Beam model** (side bar) lists the models. Open one to see its paths, components and their positions
along the beam. The editor changes the model, its definitions and datasets, boundaries along paths,
alignment, state mappings and value provenance; saving keeps a new revision.

## Link components to equipment

From a model, open its **asset synchronisation**:

1. ARGUS proposes which physical asset implements each component, from names, aliases, type, beamline,
   position, order and neighbours, each with a confidence and the evidence.
2. Confirm, correct or reject each proposal. A confirmed link makes the asset installed at that
   position.
3. Confirmed links are kept on later synchronisations; only new or changed components are proposed
   again.
