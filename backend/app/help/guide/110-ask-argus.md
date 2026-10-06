---
title: Ask ARGUS
summary: Asking questions in your own words, following up, and letting the assistant propose changes you confirm.
keywords: [ask, ask argus, chat, voice, speak, microphone, hands-free, read aloud, phone, mobile, assistant, ai, question, answer, conversation, propose, proposal, apply, discard, create with ai, help, how to]
order: 110
---

**Ask ARGUS** (side bar) answers questions in your own words, in any language, from your workspace's
own records: equipment, tickets, documents, the text of attached files, and this guide.

## Ask

1. Open **Ask ARGUS** and type a question: "which ion pumps are on the linac?", "what went wrong with
   the gun vacuum before, and how was it fixed?", "how do I export a workspace?".
2. You see each lookup as it runs (*Searching equipment*, *Reading what is written*, *Opening a
   record*…) and then the answer. Every key in the answer opens its record.
3. Ask a **follow-up** in the same conversation ("and which of those are in AC1?"): the earlier turns
   are its context. **New chat** starts afresh; conversations are kept for you only.

An answer built from **no lookups** is marked as such: treat it as unfounded. If it says the records do
not contain something, it tells you what it looked at.

## Let it make changes for you

You can ask it to **create** records, **change** them, or **relate** them ("create a screen station
SCN01 composed of camera … and motor …"). It never changes anything itself:

1. It looks the records up, then **proposes** each change. Every proposal is checked at once: the type
   exists, the record is there, the attributes belong to the type, the relation is allowed. A record it
   proposes to create is called `new:1`, `new:2`… until it exists, so it can be related in the same
   answer.
2. The proposals appear under the answer as **Proposed changes**, with a box to tick each.
3. Press **Apply** (all, or the ones ticked) or **Discard**. Applying goes through the same checks as
   the forms, with **your** permissions, and is recorded in your name.
4. Each line then shows *applied* (with a link to what was made), *failed* (and why), or *discarded*. A
   relation to a record whose creation failed fails with it.

You are offered this only if you could make those changes by hand.

## Ask it how to do something

"How do I import an EPIK8s configuration?", "step by step, how do I move my local workspaces to
production?": it answers from this guide, and can go through it with you one step at a time.

## On the phone (ARGUS Field)

The mobile app has the same assistant: the robot icon at the top of its home screen opens **Ask**.

1. Type a question, or press the **microphone** and say it. When you pause, what was heard is sent as the
   question.
2. The lookups appear as it works, then the answer. Follow-ups continue the conversation; **New
   conversation** starts afresh, and **Earlier conversations** reopens one (also the ones from the web).
3. The **speaker** under an answer reads it aloud.
4. **Hands-free** (the headset icon): each answer is read aloud, then the app listens for the next
   question. It stops when you say nothing, or when you press the headset again.

Speech is recognised and spoken by the phone itself: only the words heard are sent, as a typed
question would be. The first time, the phone asks to allow the microphone.

## When it is unavailable

Ask ARGUS needs the workspace's AI endpoint (*AI endpoint*). Its search of what is written needs the
written knowledge to be indexed there (*Written knowledge for Ask ARGUS*).
