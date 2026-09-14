"""Talking to an OpenAI-compatible endpoint.

Deliberately generic: INFN runs several AI gateways and a workspace points
at whichever one it is entitled to use, so nothing here knows about a
particular provider. The endpoint is whatever answers `/v1/models` and
`/v1/chat/completions`.

Checking one is not the same as pinging it. Three separate things fail in
practice — the host is unreachable, the key is rejected, or the model name
is not one this endpoint serves — and the third passes a naive health
check and then fails on first use, so it is checked explicitly.
"""
from dataclasses import dataclass
from typing import Optional

import requests

TIMEOUT_SECONDS = 30
# Long enough for a real classification over a page of text.
COMPLETION_TIMEOUT_SECONDS = 120


@dataclass
class Endpoint:
    base_url: str
    model: str
    embedding_model: Optional[str] = None
    vision_model: Optional[str] = None
    api_key: Optional[str] = None

    @property
    def root(self) -> str:
        return self.base_url.rstrip("/")

    def headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class LLMError(RuntimeError):
    """Something the caller should show a person, not a stack trace."""


def list_models(endpoint: Endpoint) -> list[str]:
    try:
        resp = requests.get(
            f"{endpoint.root}/models", headers=endpoint.headers(), timeout=TIMEOUT_SECONDS
        )
    except requests.RequestException as e:
        raise LLMError(f"Could not reach {endpoint.root}: {e}") from e

    if resp.status_code in (401, 403):
        raise LLMError("The endpoint rejected the API key.")
    if resp.status_code >= 400:
        raise LLMError(f"The endpoint answered {resp.status_code} listing its models.")
    try:
        return [m.get("id") for m in resp.json().get("data", []) if m.get("id")]
    except ValueError as e:
        raise LLMError("The endpoint's model list was not JSON — is this an OpenAI-compatible API?") from e


def check(endpoint: Endpoint) -> tuple[bool, Optional[str], list[str]]:
    """Whether this endpoint can actually serve what it was configured with.

    Returns (ok, error, models). The model names are checked against what
    the endpoint lists, because a wrong one passes every other test and
    then fails on the first real request.
    """
    try:
        models = list_models(endpoint)
    except LLMError as e:
        return False, str(e), []

    if endpoint.model not in models:
        available = ", ".join(models[:8]) or "none"
        return (
            False,
            f"This endpoint does not serve “{endpoint.model}”. It offers: {available}.",
            models,
        )
    if endpoint.embedding_model and endpoint.embedding_model not in models:
        return (
            False,
            f"This endpoint does not serve the embedding model “{endpoint.embedding_model}”.",
            models,
        )
    if endpoint.vision_model and endpoint.vision_model not in models:
        return (
            False,
            f"This endpoint does not serve the vision model “{endpoint.vision_model}”.",
            models,
        )

    # Listing models often needs no key even where using one does, so the
    # key is only really tested by asking for something.
    try:
        resp = requests.post(
            f"{endpoint.root}/chat/completions",
            headers=endpoint.headers(),
            json={
                "model": endpoint.model,
                "messages": [{"role": "user", "content": "Reply with: ok"}],
                "max_tokens": 5,
            },
            timeout=COMPLETION_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        return False, f"Could not reach {endpoint.root}: {e}", models

    if resp.status_code in (401, 403):
        return False, "The endpoint rejected the API key.", models
    if resp.status_code >= 400:
        detail = (resp.text or "")[:200]
        return False, f"The endpoint answered {resp.status_code}: {detail}", models
    return True, None, models


def complete(endpoint: Endpoint, system: str, user: str, max_tokens: int = 512) -> str:
    try:
        resp = requests.post(
            f"{endpoint.root}/chat/completions",
            headers=endpoint.headers(),
            json={
                "model": endpoint.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": max_tokens,
                # Classification should not wander between runs.
                "temperature": 0,
            },
            timeout=COMPLETION_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise LLMError(f"Could not reach {endpoint.root}: {e}") from e
    if resp.status_code >= 400:
        raise LLMError(f"The endpoint answered {resp.status_code}: {(resp.text or '')[:200]}")
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError) as e:
        raise LLMError("The endpoint's reply was not in the expected shape.") from e


def converse(endpoint: Endpoint, messages: list[dict], tools: Optional[list[dict]] = None,
             max_tokens: int = 1200) -> dict:
    """One turn of a tool-calling conversation; returns the assistant message.

    Unlike `complete`, the caller owns the message list, because a tool
    call and its result have to be appended in the exact shape the model
    sent them or the next turn is rejected.
    """
    payload: dict = {
        "model": endpoint.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    try:
        resp = requests.post(
            f"{endpoint.root}/chat/completions",
            headers=endpoint.headers(),
            json=payload,
            timeout=COMPLETION_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise LLMError(f"Could not reach {endpoint.root}: {e}") from e
    if resp.status_code >= 400:
        detail = (resp.text or "")[:300]
        # Worth naming: a model that does not do tool calling fails here,
        # and "400 Bad Request" alone sends somebody looking at the network.
        if "tool" in detail.lower():
            raise LLMError(
                f"The endpoint refused a tool-calling request — “{endpoint.model}” may not "
                f"support tools. It answered {resp.status_code}: {detail}"
            )
        raise LLMError(f"The endpoint answered {resp.status_code}: {detail}")
    try:
        return resp.json()["choices"][0]["message"]
    except (ValueError, KeyError, IndexError) as e:
        raise LLMError("The endpoint's reply was not in the expected shape.") from e


def embed(endpoint: Endpoint, texts: list[str]) -> list[list[float]]:
    """Vectors for a batch of texts, in the order given."""
    if not endpoint.embedding_model:
        raise LLMError("No embedding model is configured for this endpoint.")
    if not texts:
        return []
    try:
        resp = requests.post(
            f"{endpoint.root}/embeddings",
            headers=endpoint.headers(),
            json={"model": endpoint.embedding_model, "input": texts},
            timeout=COMPLETION_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise LLMError(f"Could not reach {endpoint.root}: {e}") from e
    if resp.status_code >= 400:
        raise LLMError(f"The endpoint answered {resp.status_code}: {(resp.text or '')[:200]}")
    try:
        data = sorted(resp.json()["data"], key=lambda row: row.get("index", 0))
        return [row["embedding"] for row in data]
    except (ValueError, KeyError) as e:
        raise LLMError("The endpoint's embeddings reply was not in the expected shape.") from e


def look(endpoint: Endpoint, image: bytes, mime_type: str, system: str, user: str,
         max_tokens: int = 800) -> str:
    """Ask the vision model about a picture.

    A separate model from `complete`'s, because they usually are: the chat
    model a workspace picks for text answers "not a multimodal model" when
    shown an image, and finding that out at the point of use rather than at
    configuration time is exactly what the check exists to prevent.
    """
    if not endpoint.vision_model:
        raise LLMError("No vision model is configured for this endpoint.")
    import base64

    encoded = base64.b64encode(image).decode("ascii")
    try:
        resp = requests.post(
            f"{endpoint.root}/chat/completions",
            headers=endpoint.headers(),
            json={
                "model": endpoint.vision_model,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                            },
                        ],
                    },
                ],
                "max_tokens": max_tokens,
                "temperature": 0,
            },
            timeout=COMPLETION_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise LLMError(f"Could not reach {endpoint.root}: {e}") from e
    if resp.status_code >= 400:
        raise LLMError(f"The endpoint answered {resp.status_code}: {(resp.text or '')[:200]}")
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError) as e:
        raise LLMError("The endpoint's reply was not in the expected shape.") from e
