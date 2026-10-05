---
title: Workspaces, people and roles
summary: Creating workspaces, adding people, giving roles, groups, API tokens and access reviews.
keywords: [workspace, create workspace, users, people, roles, permissions, admin, administrator, members, groups, access, tokens, keys, access review, grant, revoke]
order: 20
---

ARGUS decides who may do what. The sign-in service only says who you are; your rights are given in
ARGUS, per workspace, through **roles**. The full reference is `docs/roles.md`.

## Who can do what

- An **administrator** can do everything, in every workspace, and is the only one who can create
  workspaces and manage people.
- Everyone else gets **roles in a workspace**. A role allows actions (read, create, modify, delete,
  approve) on objects, tickets and documents. A person can hold **several roles**, and they add up.
- A role can be given to a **group** instead of a person: everyone in the group gets it.

| Role | In short |
|---|---|
| Viewer | sees everything, changes nothing |
| Reporter | sees everything, raises tickets |
| Agent | works the ticket queue |
| Approver | approves and publishes controlled documents |
| Contributor | creates and edits, never deletes |
| Curator | full control of the content, also types, global values and imports |
| Owner | as curator, plus giving access to others |

Domain roles (inventory steward, IT steward, beamline operator, service-desk agent, document
controller, safety investigator, procurement officer, auditor) can be installed from the *Access
reviews* page.

## Create a workspace

You need to be an administrator.

1. Open **Administration → Workspaces** and press **New workspace** (or, with no workspace yet, use the
   form on the *Choose a workspace* screen).
2. Type its **Name** (for example `SPARC`). The **Workspace id** is proposed from it, following the rule
   in *Administration → Settings*; it is used in URLs and record keys and cannot be changed later.
3. Create it. You are its first member with full rights. Give others access next.

## Give a person or a group a role

1. The person signs in once, so ARGUS knows them. (An administrator can also add someone before their
   first sign-in, by email: `argus_admin.py user add <email>`; their first sign-in claims that account.)
2. Open the workspace, then **Access** (bottom of the side bar). *Granted roles* lists who holds what.
3. Grant a role: choose **Person** or **Group**, pick who, pick the **Role**, and grant it. Grant more
   roles the same way: they add up.
4. To take a role away, remove that line from *Granted roles*.

**Members** is the older, per-person way of giving access: *Invite by email* works only for someone who
has signed in once. Prefer roles on *Access*.

People who sign in with the hub's own Keycloak also need a login there: an administrator creates it in
Keycloak's admin console (*Users → Add user*, then *Credentials → Set password*, temporary).

## Make someone an administrator

**Administration → Users**, find the person, and switch **Admin** on. Use it sparingly: an
administrator sees and can change everything. The very first administrators of a new installation are
set by whoever runs it (`ARGUS_BOOTSTRAP_ADMINS`).

## Groups

Groups come from the directory. **Access → Directory** shows where they come from and when they were
last synchronised. Give a role to a group on **Access**, like to a person.

## API tokens (for scripts)

A script or another tool signs in with an **API token** instead of a person. An administrator makes one
for a workspace with `argus_admin.py workspace token <workspace>` (in production, in the API pod). The
token is **shown once**: copy it then and keep it like a password. It acts in its own workspace only.

(The **Keys** page is something else: the pattern new records' keys are made from, such as
`SPARC-000123`.)

## Access reviews

The **Access reviews** page (linked from *Access*) takes a signed snapshot of everyone who has access to
the workspace: people, groups, API tokens, what is open to everyone, and the administrators, with what
changed *since the previous review*.

1. Start a review.
2. Read the changes; remove access that is no longer needed (on *Access*).
3. **Sign** it, with a comment. It is complete once enough different people have signed.

The same page installs the **Roles per domain**.
