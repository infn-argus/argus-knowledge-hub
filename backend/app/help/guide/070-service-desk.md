---
title: Service desk (tickets)
summary: Reporting a fault or a request, working tickets through their workflow, the board, watchers and notifications.
keywords: [ticket, tickets, issue, fault, incident, request, task, service desk, workflow, status, assignee, priority, board, watcher, notification, sla]
order: 70
---

A **ticket** is a fault, an incident, a request or a piece of work. It is linked to the equipment it
affects and the documents that help.

## Report a fault or ask for something

1. **+ New → Ticket**.
2. **Title**: one line saying what is wrong ("Ion pump GUNSIP01 current rising").
3. **Type**: an operational incident, a request, a task… The type decides the ticket's workflow.
4. **Description**: what you saw, when, what you already tried. For an incident, say when it happened.
5. **Objects**: *Link an object…* to the equipment affected (the checklist suggests the ones your text
   names). *Link a document…* for a procedure that applies.
6. **Priority** and, if you know it, the **Assignee**. Create the ticket.

## Work a ticket

- **Service desk → All tickets** lists them; **Board** shows them in columns by state; **Search** finds
  them by text and fields.
- Open a ticket to comment, attach files, link more objects or tickets, and move it on: the buttons
  show the moves its workflow allows from where it is, and what each needs (an assignee, a resolution,
  a comment).
- Reporters and assignees **watch** their tickets and are told about changes, as is anyone
  @mentioned in a comment. You are never told about a ticket you may not read.
- A state with a time limit (SLA) escalates a ticket that stays in it too long.

## Workflows

**Service desk → Workflows** shows each ticket type's states (open, active, waiting, done), the moves
between them and what a move needs. Tickets of a type with no workflow use the built-in one: New → In
Progress → Pending → Resolved → Closed.

## On the equipment's side

An asset's page lists its tickets, and a ticket is counted on the unit that was installed when the
incident happened, so a swapped unit keeps its own history.
