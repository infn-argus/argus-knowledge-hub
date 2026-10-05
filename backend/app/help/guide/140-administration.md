---
title: Administration and the production installation
summary: The administration pages, the production installation (addresses, sign-in, releases), and where operators find the details.
keywords: [administration, admin, settings, workspace identifiers, users, production, deployment, release, version, argo cd, keycloak, kubernetes, backup, disk, operations]
order: 140
---

## The administration pages

For administrators, **Administration** (bottom of the side bar):

| Page | For |
|---|---|
| **Workspaces** | every workspace; **New workspace** |
| **Users** | everyone who has signed in; who is an administrator |
| **Settings** | how workspace identifiers are made from names (prefix, case, separator, length) |
| **Portability** | exports and imports (see *Export and import*) |

## The production installation

| | Address |
|---|---|
| the hub | `https://argus-hub.90.147.174.30.myip.cloud.infn.it` |
| its API | `https://argus-hub-api.90.147.174.30.myip.cloud.infn.it` |
| sign-in (Keycloak, realm `argus`) | `https://keycloak.90.147.174.30.myip.cloud.infn.it` |

- **Sign-in**: the hub's Keycloak (*Keycloak login*) or Google. Keycloak accounts are created by an
  administrator in Keycloak's admin console (*Users*); what they may do in ARGUS is set in ARGUS.
- **New versions**: a release is a version tag (`v1.34.0`). It runs the tests, builds the images and
  deploys them automatically (Argo CD); the version running is recorded in the repository.
- **Your data** lives in the installation's database and its attachments and portability volumes.
  Unused container images are removed from the servers every two days, and finished portability files
  after one day.

Operators' details (the Helm chart, secrets, storage, upgrades) are in the repository's
`k8s/README.md` and `docs/operations.md`.
