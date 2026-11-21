"""Shared tokens.bd helpers: the endpoint, the model list, and error messages.

tokens.bd is an OpenAI-compatible gateway (https://tokens.bd/v1). This module holds what the
provider and the LLM model share:

* the request settings the SDK's OpenAI-compatible base reads from ``credentials``;
* ``GET /v1/models`` for the key, which proves the key works without running a model and tells
  each model's context window, maximum output and capabilities;
* turning tokens.bd's error bodies (``{"error": {"code", "message"}}``) into Dify errors that say
  what to do.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from dataclasses import dataclass
from typing import Any

import requests
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeAuthorizationError,
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
    InvokeRateLimitError,
    InvokeServerUnavailableError,
)

PLUGIN_VERSION = "0.1.0"
DEFAULT_ENDPOINT = "https://tokens.bd/v1"
USER_AGENT = f"dify-plugin-tokensbd/{PLUGIN_VERSION}"
DASHBOARD_URL = "https://tokens.bd/dashboard"
MODELS_PAGE_URL = "https://tokens.bd/models"

# Used when tokens.bd does not report a figure for a model.
FALLBACK_CONTEXT = 128_000
FALLBACK_MAX_OUTPUT = 8_192

_CATALOG_TTL_SECONDS = 300
_TIMEOUT = (10, 30)


def endpoint_of(credentials: dict) -> str:
    """The API base URL: the one in the settings, else tokens.bd. Always ends without a slash."""
    raw = str(credentials.get("endpoint_url") or "").strip() or DEFAULT_ENDPOINT
    raw = raw.rstrip("/")
    for suffix in ("/chat/completions", "/models"):
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]
    return raw


def request_headers(credentials: dict) -> dict[str, str]:
    """Headers for every tokens.bd call. The User-Agent tells tokens.bd the call came from Dify."""
    headers = {"User-Agent": USER_AGENT, "X-Title": "Dify"}
    api_key = str(credentials.get("api_key") or "").strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


@dataclass(frozen=True)
class ModelInfo:
    """What tokens.bd says about one model in ``GET /v1/models``."""

    id: str
    name: str
    context_length: int | None
    max_output_tokens: int | None
    tools: bool | None
    image: bool | None
    video: bool | None

    @staticmethod
    def from_entry(entry: dict[str, Any]) -> ModelInfo:
        capabilities = entry.get("capabilities") or {}
        modalities = entry.get("input_modalities") or []

        def flag(key: str) -> bool | None:
            if isinstance(capabilities.get(key), bool):
                return capabilities[key]
            if modalities:
                return key in modalities if key != "tools" else None
            return None

        def positive(value: Any) -> int | None:
            return value if isinstance(value, int) and value > 0 else None

        model_id = str(entry.get("id") or "")
        return ModelInfo(
            id=model_id,
            name=str(entry.get("name") or model_id),
            context_length=positive(entry.get("context_length")),
            max_output_tokens=positive(entry.get("max_output_tokens")),
            tools=flag("tools"),
            image=flag("image"),
            video=flag("video"),
        )


_catalog_cache: dict[str, tuple[float, dict[str, ModelInfo]]] = {}
_catalog_lock = threading.Lock()


def _cache_key(credentials: dict) -> str:
    secret = str(credentials.get("api_key") or "")
    digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]
    return f"{endpoint_of(credentials)}|{digest}"


def fetch_models(credentials: dict, *, fresh: bool = False) -> dict[str, ModelInfo]:
    """The models this key may use, by id. Cached for 5 minutes per key.

    Raises ``CredentialsValidateFailedError`` with a readable message when tokens.bd refuses the
    key or cannot be reached.
    """
    key = _cache_key(credentials)
    now = time.monotonic()
    if not fresh:
        with _catalog_lock:
            cached = _catalog_cache.get(key)
        if cached and now - cached[0] < _CATALOG_TTL_SECONDS:
            return cached[1]

    if not str(credentials.get("api_key") or "").strip():
        raise CredentialsValidateFailedError(
            f"Enter your tokens.bd API key. Create one at {DASHBOARD_URL}/keys."
        )
    url = f"{endpoint_of(credentials)}/models"
    try:
        response = requests.get(url, headers=request_headers(credentials), timeout=_TIMEOUT)
    except requests.RequestException as ex:
        raise CredentialsValidateFailedError(
            f"Could not reach {endpoint_of(credentials)}. Check the API base URL and that this "
            f"Dify server can reach the internet. ({ex.__class__.__name__})"
        ) from ex

    with response:
        if response.status_code != 200:
            error = error_from_response(response.status_code, response.text)
            raise CredentialsValidateFailedError(str(error))
        try:
            entries = response.json().get("data") or []
        except (ValueError, AttributeError) as ex:
            raise CredentialsValidateFailedError(
                f"{url} did not answer like tokens.bd. Check the API base URL."
            ) from ex

    models = {
        info.id: info
        for info in (ModelInfo.from_entry(e) for e in entries if isinstance(e, dict))
        if info.id
    }
    with _catalog_lock:
        _catalog_cache[key] = (now, models)
    return models


def model_info(model: str, credentials: dict) -> ModelInfo | None:
    """tokens.bd's figures for ``model``, or None when they cannot be read right now."""
    try:
        return fetch_models(credentials).get(model)
    except CredentialsValidateFailedError:
        return None


# --- errors ---------------------------------------------------------------------------------

_SDK_STATUS = re.compile(r"status code (\d{3})\s*:\s*(.*)", re.S)

_ADVICE: dict[str, str] = {
    "missing_api_key": f"Enter your tokens.bd API key in the provider settings ({DASHBOARD_URL}/keys).",
    "invalid_api_key": f"Check the API key in the provider settings, or create a new one at {DASHBOARD_URL}/keys.",
    "key_inactive": f"This key is turned off. Turn it on or use another key at {DASHBOARD_URL}/keys.",
    "key_expired": f"This key has expired. Create a new one at {DASHBOARD_URL}/keys.",
    "insufficient_credits": f"Top up your wallet or choose a plan at {DASHBOARD_URL}/billing.",
    "no_funding": f"Choose a plan or top up your wallet at {DASHBOARD_URL}/billing.",
    "outstanding_debt": f"Settle the balance owed at {DASHBOARD_URL}/billing.",
    "monthly_spend_cap_exceeded": f"This key reached its monthly cap. Raise it at {DASHBOARD_URL}/keys.",
    "model_not_allowed_on_key": f"This key may not use this model. Change its model list at {DASHBOARD_URL}/keys.",
    "tier_permission_denied": f"This model is not in your plan. See {MODELS_PAGE_URL}.",
    "model_not_found": f"tokens.bd has no model with this id. Pick one from {MODELS_PAGE_URL}.",
    "model_not_available": f"This model is not available right now. Pick another from {MODELS_PAGE_URL}.",
    "window_exhausted": f"A usage limit of your plan is reached. See when it resets at {DASHBOARD_URL}/usage.",
    "model_limit_reached": f"This model's limit in your plan is reached. See {DASHBOARD_URL}/usage.",
    "free_limit_reached": f"The free requests for this model are used up. See {DASHBOARD_URL}/usage.",
    "context_length_exceeded": "The conversation is longer than this model accepts. Shorten it or pick a model with a larger context window.",
    "capability_not_supported": "This model does not accept this kind of input (for example images or tools). Pick a model that does.",
}

_AUTH = {"missing_api_key", "invalid_api_key", "key_inactive", "key_expired", "account_suspended", "ip_blocked", "forbidden"}
_BILLING = {"insufficient_credits", "no_funding", "outstanding_debt", "member_cap_reached", "bonus_model_not_allowed", "monthly_spend_cap_exceeded"}


def _parse_body(body: str) -> tuple[str | None, str | None, str | None]:
    """(code, message, request id) from a tokens.bd error body; Nones when it is not one."""
    try:
        data = json.loads(body)
    except (TypeError, ValueError):
        return None, None, None
    if not isinstance(data, dict):
        return None, None, None
    error = data.get("error")
    if isinstance(error, dict):
        code = error.get("code") or error.get("type")
        message = error.get("message")
        request_id = error.get("request_id") or data.get("request_id")
        return (
            str(code) if code else None,
            str(message) if message else None,
            str(request_id) if request_id else None,
        )
    return None, None, None


def error_from_response(status: int, body: str) -> InvokeError:
    """A Dify error for a tokens.bd error response, saying what happened and what to do."""
    code, message, request_id = _parse_body(body)
    text = message or (body.strip()[:300] if body and body.strip() else f"HTTP {status}")
    advice = _ADVICE.get(code or "")
    parts = [f"tokens.bd: {text}"]
    if advice and advice not in text:
        parts.append(advice)
    if code:
        parts.append(f"(code {code}")
        parts[-1] += f", request {request_id})" if request_id else ")"
    description = " ".join(parts)

    if status == 401 or (code in _AUTH):
        return InvokeAuthorizationError(description)
    if status == 402 or code in _BILLING:
        return InvokeAuthorizationError(description)
    if status == 429:
        return InvokeRateLimitError(description)
    if status in (400, 403, 404, 413, 422):
        return InvokeBadRequestError(description)
    if status in (502, 503, 504) or status >= 500:
        return InvokeServerUnavailableError(description)
    return InvokeError(description)


def translate_error(error: Exception) -> Exception:
    """Turns the SDK's generic "API request failed with status code N: body" into a clear error."""
    if isinstance(error, InvokeError):
        match = _SDK_STATUS.search(str(error))
        if match:
            return error_from_response(int(match.group(1)), match.group(2))
        return error
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return error_from_response(error.response.status_code, error.response.text)
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return InvokeConnectionError(
            f"tokens.bd could not be reached ({error.__class__.__name__}). Try again shortly."
        )
    return error
