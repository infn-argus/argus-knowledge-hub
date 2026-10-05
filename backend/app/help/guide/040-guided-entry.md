---
title: Guided and AI-assisted entry
summary: The checklist beside every form, and Describe it, which fills a form from a sentence, a photo or a file.
keywords: [checklist, describe it, ai, nameplate, photo, datasheet, pdf, suggestion, form, fill, complete from a file, guided entry]
order: 40
---

The forms for a new asset, ticket or document have a side panel with two parts.

## The checklist

Always there, no AI needed. As you type, it shows:

- the steps done so far, and the **Next** question worth answering;
- what is wrong or worth knowing, with a one-click fix where there is one: a key already taken (with a
  link to its record), a serial or inventory number another record holds, a likely duplicate, a
  control-channel name typed as if it were equipment, a missing required attribute;
- for a ticket: when an incident happened, which equipment it affects, similar open tickets;
- for a document: the code it will get, similar titles, the records it mentions.

## Describe it (AI)

Appears when the workspace's AI endpoint is set up (*AI endpoint*).

1. Write what you know, in your own words and any language ("Agilent ion pump VacIon Plus 75, serial
   77120, in the gun area"), or use **Add a photo or file**: a nameplate photo, a PDF datasheet, a Word
   or Excel file, an email.
2. ARGUS shows **suggestions**, each with how sure it is and the words or page it was read from.
3. Press **Use** on the ones you want, or use all of them in empty fields. Nothing you typed is
   overwritten, and nothing is saved until you save the form.

Passwords and keys in the text are removed before anything is sent to the model. For a ticket, possible
causes are shown as *unresolved hypotheses*, never written as findings.

## Complete an existing asset from a file

On an asset's page, **Complete from a file** takes a datasheet, a photo or a note and proposes every
value that differs from the record. The proposals wait in the **Review queue**: nothing on the record
changes until someone accepts them.
