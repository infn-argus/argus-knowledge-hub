---
title: Getting started
summary: What ARGUS is, signing in, choosing a workspace and finding your way around.
keywords: [start, sign in, login, keycloak, google, workspace, navigation, search, cockpit, first steps]
order: 10
---

ARGUS Knowledge Hub keeps, in one place, an accelerator's **equipment** (assets), the **work** done on it
(tickets) and what is **written** about it (documents), linked to each other. Every asset shows its
tickets and the documents that apply to it; every ticket shows its equipment and the procedures that
cover it; every document shows where it applies.

## Signing in

1. Open the hub's address in a browser (in production,
   `https://argus-hub.90.147.174.30.myip.cloud.infn.it`).
2. Choose how to sign in:
   - **Keycloak login** (or *INFN login*): your account in the hub's sign-in service. Its page may also
     offer **Google**, for a Google account.
   - **Sign in with Google**: a Google account.
   - **API token**: for scripts and tools, not for people.
3. If it is your first time, an administrator may still have to give you access (see *Workspaces,
   people and roles*). You are recognised by your **email**, so sign in with the account whose email
   the administrator used.

Two accounts with different emails (an INFN and a Gmail address) are two different people in ARGUS,
each with their own access.

## Choosing a workspace

A **workspace** is one area of work, usually one machine or facility (SPARC, BTF, ELI…). Everything you
see belongs to the workspace you are in.

- With access to one workspace, you go straight into it.
- With several, choose one on the *Choose a workspace* screen. Switch later from the workspace name at
  the top left of the side bar.
- With none, the screen says so. **An administrator with no workspace yet** gets a *Create workspace*
  form there instead: type a name (for example `SPARC`) and press *Create workspace*.

## Finding your way around

The side bar holds the main areas:

| Area | What it is for |
|---|---|
| **Cockpit** | what needs attention now: open tickets, items waiting for review, recent changes |
| **Review queue** | facts that wait for a person: inferred values, proposals, conflicts, installations |
| **Assets** | the equipment: browse and search, types, labels and QR codes, bulk changes, imports' mapping |
| **Service desk** | tickets: list, board, search, workflows |
| **Knowledge base** | documents: list, search, type suggestions |
| **Knowledge graph** | how records are connected; what depends on what |
| **Beam model** | the machine's beam-transport model, linked to its equipment |
| **Ask ARGUS** | ask questions in your own words; it can also propose changes for you to apply |
| **Help** | this guide |

At the bottom of the side bar, for the workspace: **Access** (who has which role), **Members**,
**Imports**, **Icon library**, **Transfer**, **AI endpoint** and **Keys** (how record keys are made);
and **Administration** (workspaces, users, settings, portability) for administrators.

**+ New** (top right) creates a ticket, an asset, a document or a beam model.

**Search everything** with the box at the top, or **Ctrl K** (⌘ K on a Mac): it covers assets, tickets
and documents at once.

## Getting help

- This **Help** page: search it, or open a topic from the list.
- **Ask ARGUS**: ask "how do I…?" and it answers from this guide, step by step, and from your
  workspace's own records.
