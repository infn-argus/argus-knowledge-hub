---
title: AI settings
summary: Connecting an AI endpoint, choosing models, the output-token limit, indexing written knowledge, and evaluating models for guided entry.
keywords: [ai, ai endpoint, llm, model, embedding, vision, token limit, output-token limit, reasoning model, qwen, index, knowledge index, evaluation, golden dataset, profile, candidate, activate]
order: 120
---

The AI features (Describe it, Ask ARGUS, type suggestions, AI help with imports) use an
OpenAI-compatible endpoint chosen per workspace, on the workspace's **AI endpoint** page. Until it is
configured and checked, they are simply not offered.

## Connect an endpoint

1. **AI endpoint** (bottom of the side bar).
2. **Endpoint URL** (for example `https://ai-gateway.example.infn.it/v1`) and the API key, if it needs
   one. The key is stored encrypted and never shown again.
3. **Model** for questions and forms; optionally an **Embedding model** (for searching what is written),
   a **Vision model** (for nameplate photos), and speech models.
4. **Output-token limit**: leave it empty for no limit. Set a number only for a gateway that bills or
   throttles by token; too small a limit leaves a reasoning model (Qwen, DeepSeek…) no room to answer.
5. Tick **Offer AI features in this workspace**, save, then press **Check endpoint**: features turn on only once
   the check passes.

Documents marked *riservato* are sent to the model only if you allow it here.

## Written knowledge for Ask ARGUS

For Ask ARGUS to search documents, tickets, comments and attached files by meaning, they are indexed
with the embedding model: under **Written knowledge for Ask ARGUS** on the same page, **Build the index**
(later **Update the index**, which embeds again only what changed).

## Models for guided entry

**Models for guided entry** lets you try a model before *Describe it* uses it:

1. **Add candidate**: the model's name (and for assets, a vision model).
2. **Evaluate** it on the golden dataset: accuracy per field and per language, whether injected
   instructions or secrets got through, and speed.
3. **Activate** it with a reason, if it passes. **Suspend** goes back to the endpoint's default model.

An evaluation where every field comes back *missing*, with no errors, means the model gave no answer at
all (for example a token limit too small for a reasoning model), not that it answered badly.
