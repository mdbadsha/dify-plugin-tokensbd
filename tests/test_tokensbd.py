"""Unit tests with the network mocked: what the plugin sends, reads and says."""

from __future__ import annotations

import json
from unittest import mock

import pytest
import requests
from dify_plugin.entities.model import ModelFeature, ModelPropertyKey
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeAuthorizationError,
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
    InvokeRateLimitError,
    InvokeServerUnavailableError,
)

from models import _tokensbd as tb
from models.llm.llm import TokensbdLargeLanguageModel
from provider.tokensbd import TokensbdModelProvider

CREDS = {"api_key": "tok_test_123"}

CATALOG = {
    "object": "list",
    "data": [
        {
            "id": "anthropic/claude-opus-5-5",
            "name": "Claude Opus 5.5",
            "context_length": 1_000_000,
            "max_output_tokens": 64_000,
            "input_modalities": ["text", "image", "pdf"],
            "capabilities": {"image": True, "pdf": True, "tools": True},
        },
        {
            "id": "z-ai/glm-5.1",
            "name": "GLM-5.1",
            "context_length": 200_000,
            "input_modalities": ["text"],
            "capabilities": {"tools": False},
        },
        {"id": "auto", "name": "auto"},
    ],
}


def response(status: int, body: object) -> mock.MagicMock:
    r = mock.MagicMock(spec=requests.Response)
    r.status_code = status
    r.text = json.dumps(body) if not isinstance(body, str) else body
    r.json.side_effect = lambda: json.loads(r.text)
    r.__enter__.return_value = r
    r.__exit__.return_value = False
    return r


def gateway_error(status: int, code: str, message: str) -> mock.MagicMock:
    return response(
        status, {"error": {"message": message, "code": code, "request_id": "req_42", "type": "x"}}
    )


@pytest.fixture(autouse=True)
def clear_cache():
    tb._catalog_cache.clear()
    yield
    tb._catalog_cache.clear()


def llm() -> TokensbdLargeLanguageModel:
    return TokensbdLargeLanguageModel(model_schemas=[])


# --- endpoint and headers -------------------------------------------------------------------


def test_endpoint_defaults_to_tokens_bd_and_is_normalised():
    assert tb.endpoint_of({}) == "https://tokens.bd/v1"
    assert tb.endpoint_of({"endpoint_url": "  "}) == "https://tokens.bd/v1"
    assert tb.endpoint_of({"endpoint_url": "https://tokens.bd/v1/"}) == "https://tokens.bd/v1"
    assert (
        tb.endpoint_of({"endpoint_url": "https://tokens.bd/v1/chat/completions"})
        == "https://tokens.bd/v1"
    )


def test_headers_name_the_plugin_and_carry_the_key():
    headers = tb.request_headers(CREDS)
    assert headers["User-Agent"].startswith("dify-plugin-tokensbd/")
    assert headers["Authorization"] == "Bearer tok_test_123"
    assert "Authorization" not in tb.request_headers({})


# --- the model list ---------------------------------------------------------------------------


def test_reads_models_once_and_caches_them_per_key():
    with mock.patch.object(tb.requests, "get", return_value=response(200, CATALOG)) as get:
        models = tb.fetch_models(CREDS)
        tb.fetch_models(CREDS)
    assert get.call_count == 1
    url = get.call_args.args[0]
    assert url == "https://tokens.bd/v1/models"
    assert get.call_args.kwargs["timeout"]
    opus = models["anthropic/claude-opus-5-5"]
    assert (opus.context_length, opus.max_output_tokens, opus.tools, opus.image) == (
        1_000_000,
        64_000,
        True,
        True,
    )
    glm = models["z-ai/glm-5.1"]
    assert (glm.tools, glm.image, glm.max_output_tokens) == (False, False, None)
    assert models["auto"].tools is None


def test_a_refused_key_explains_itself_and_never_shows_the_key():
    with mock.patch.object(
        tb.requests,
        "get",
        return_value=gateway_error(401, "invalid_api_key", "Invalid API key."),
    ):
        with pytest.raises(CredentialsValidateFailedError) as ex:
            tb.fetch_models(CREDS)
    text = str(ex.value)
    assert "Invalid API key." in text and "dashboard/keys" in text and "invalid_api_key" in text
    assert "tok_test_123" not in text


def test_an_unreachable_endpoint_and_a_missing_key_are_explained():
    with mock.patch.object(tb.requests, "get", side_effect=requests.ConnectionError("boom")):
        with pytest.raises(CredentialsValidateFailedError, match="Could not reach"):
            tb.fetch_models(CREDS)
    with pytest.raises(CredentialsValidateFailedError, match="Enter your tokens.bd API key"):
        tb.fetch_models({})


# --- errors -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "code", "kind", "advice"),
    [
        (401, "invalid_api_key", InvokeAuthorizationError, "dashboard/keys"),
        (402, "insufficient_credits", InvokeAuthorizationError, "dashboard/billing"),
        (403, "model_not_allowed_on_key", InvokeBadRequestError, "dashboard/keys"),
        (404, "model_not_found", InvokeBadRequestError, "tokens.bd/models"),
        (429, "window_exhausted", InvokeRateLimitError, "dashboard/usage"),
        (400, "context_length_exceeded", InvokeBadRequestError, "Shorten"),
        (503, "upstream_unavailable", InvokeServerUnavailableError, None),
    ],
)
def test_gateway_errors_become_clear_dify_errors(status, code, kind, advice):
    error = tb.error_from_response(status, gateway_error(status, code, "The message.").text)
    assert isinstance(error, kind)
    text = str(error)
    assert text.startswith("tokens.bd: The message.")
    assert f"code {code}, request req_42" in text
    if advice:
        assert advice in text


def test_the_sdks_generic_error_is_translated_and_others_pass_through():
    body = gateway_error(402, "no_funding", "No plan or balance.").text
    generic = InvokeError(f"API request failed with status code 402: {body}")
    translated = tb.translate_error(generic)
    assert isinstance(translated, InvokeAuthorizationError)
    assert "No plan or balance." in str(translated)
    assert isinstance(tb.translate_error(requests.Timeout()), InvokeConnectionError)
    other = ValueError("x")
    assert tb.translate_error(other) is other
    assert "HTTP 500" in str(tb.error_from_response(500, ""))


# --- the provider and the model ---------------------------------------------------------------


def test_the_provider_checks_the_key_without_running_a_model():
    provider = TokensbdModelProvider(mock.MagicMock(), mock.MagicMock())
    with mock.patch.object(tb.requests, "get", return_value=response(200, CATALOG)) as get, \
            mock.patch.object(tb.requests, "post") as post:
        provider.validate_provider_credentials(CREDS)
    assert get.called and not post.called


def test_adding_a_model_checks_the_key_may_use_it():
    with mock.patch.object(tb.requests, "get", return_value=response(200, CATALOG)):
        llm().validate_credentials("anthropic/claude-opus-5-5", CREDS)
        with pytest.raises(CredentialsValidateFailedError, match="no model 'nope/x'"):
            llm().validate_credentials("nope/x", CREDS)


def test_requests_carry_the_settings_the_base_needs():
    with mock.patch.object(tb.requests, "get", return_value=response(200, CATALOG)):
        settings = llm()._settings("z-ai/glm-5.1", CREDS)
        tools_on = llm()._settings("anthropic/claude-opus-5-5", CREDS)
    assert settings["endpoint_url"] == "https://tokens.bd/v1"
    assert settings["mode"] == "chat"
    assert settings["function_calling_type"] == "no_call"
    assert tools_on["function_calling_type"] == "tool_call"
    assert settings["extra_headers"]["User-Agent"].startswith("dify-plugin-tokensbd/")
    assert "Authorization" not in settings["extra_headers"]
    assert settings["api_key"] == "tok_test_123"


def test_streaming_asks_for_token_counts_and_errors_are_translated():
    model = llm()
    body = gateway_error(429, "window_exhausted", "Weekly limit reached.").text
    failure = InvokeError(f"API request failed with status code 429: {body}")
    with mock.patch.object(tb.requests, "get", return_value=response(200, CATALOG)), \
            mock.patch(
                "dify_plugin.OAICompatLargeLanguageModel._invoke", side_effect=failure
            ) as base:
        with pytest.raises(InvokeRateLimitError, match="Weekly limit reached"):
            model._invoke("auto", CREDS, [], {"temperature": 0.2}, stream=True)
    sent_parameters = base.call_args.args[3]
    assert sent_parameters == {"temperature": 0.2, "stream_options": {"include_usage": True}}


def test_a_model_added_by_id_takes_its_figures_from_tokens_bd():
    with mock.patch.object(tb.requests, "get", return_value=response(200, CATALOG)):
        opus = llm().get_customizable_model_schema("anthropic/claude-opus-5-5", CREDS)
        glm = llm().get_customizable_model_schema(
            "z-ai/glm-5.1", {**CREDS, "display_name": "GLM for docs"}
        )
    assert opus.model_properties[ModelPropertyKey.CONTEXT_SIZE] == 1_000_000
    assert opus.label.en_us == "Claude Opus 5.5"
    assert ModelFeature.VISION in opus.features
    assert ModelFeature.MULTI_TOOL_CALL in opus.features
    assert ModelFeature.AGENT_THOUGHT in opus.features
    assert opus.pricing is None
    max_tokens = next(r for r in opus.parameter_rules if r.name == "max_tokens")
    assert (max_tokens.max, max_tokens.default) == (64_000, 4096)

    assert glm.label.en_us == "GLM for docs"
    assert ModelFeature.VISION not in glm.features
    assert ModelFeature.MULTI_TOOL_CALL not in glm.features
    glm_max = next(r for r in glm.parameter_rules if r.name == "max_tokens")
    assert glm_max.max == tb.FALLBACK_MAX_OUTPUT


def test_a_model_added_by_id_still_works_when_tokens_bd_cannot_be_read():
    with mock.patch.object(tb.requests, "get", side_effect=requests.ConnectionError("down")):
        entity = llm().get_customizable_model_schema("some/model", CREDS)
    assert entity.model_properties[ModelPropertyKey.CONTEXT_SIZE] == tb.FALLBACK_CONTEXT
    assert entity.label.en_us == "some/model"
