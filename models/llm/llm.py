"""tokens.bd chat models for Dify, on the SDK's OpenAI-compatible base.

What this adds to the base:

* No settings to type: the endpoint, chat mode, tool calling and, for a model added by id, its
  context window, maximum output and vision come from tokens.bd (``GET /v1/models``).
* Token counts while streaming (``stream_options.include_usage``).
* tokens.bd's errors (balance, plan limits, model not in plan, key limits) as clear Dify errors.
* A free credentials check (``GET /v1/models``) instead of a test chat request.
"""

from __future__ import annotations

from collections.abc import Generator

from dify_plugin import OAICompatLargeLanguageModel
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import AIModelEntity, ModelFeature
from dify_plugin.entities.model.llm import LLMResult
from dify_plugin.entities.model.message import PromptMessage, PromptMessageTool
from dify_plugin.errors.model import CredentialsValidateFailedError, InvokeError

from models._tokensbd import (
    FALLBACK_CONTEXT,
    FALLBACK_MAX_OUTPUT,
    MODELS_PAGE_URL,
    ModelInfo,
    endpoint_of,
    fetch_models,
    model_info,
    request_headers,
    translate_error,
)

# The base reads these from ``credentials``; the user never has to set them.
_BASE_SETTINGS = {
    "mode": "chat",
    "stream_function_calling": "supported",
    "stream_mode_delimiter": "\n\n",
}


class TokensbdLargeLanguageModel(OAICompatLargeLanguageModel):
    def _settings(self, model: str, credentials: dict) -> dict:
        """The credentials with what the base needs filled in for ``model``."""
        info = model_info(model, credentials)
        tools = info.tools if info else None
        extra_headers = {**request_headers(credentials)}
        extra_headers.pop("Authorization", None)  # the base adds it from api_key
        return {
            **credentials,
            **_BASE_SETTINGS,
            "endpoint_url": endpoint_of(credentials),
            "extra_headers": extra_headers,
            # Tools are sent unless tokens.bd says the model takes none; it refuses clearly if so.
            "function_calling_type": "no_call" if tools is False else "tool_call",
        }

    def _invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> LLMResult | Generator:
        settings = self._settings(model, credentials)
        parameters = dict(model_parameters)
        if stream:
            parameters["stream_options"] = {"include_usage": True}
        try:
            return super()._invoke(
                model, settings, prompt_messages, parameters, tools, stop, stream, user
            )
        except Exception as ex:
            raise translate_error(ex) from ex

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        return super().get_num_tokens(model, {**credentials, **_BASE_SETTINGS}, prompt_messages, tools)

    def validate_credentials(self, model: str, credentials: dict) -> None:
        """Checks the key and that it may use ``model``, without running the model."""
        models = fetch_models(credentials, fresh=True)
        if models and model not in models:
            msg = (
                f"tokens.bd has no model '{model}' for this key. Use a model id from "
                f"{MODELS_PAGE_URL} that your plan or wallet covers."
            )
            raise CredentialsValidateFailedError(msg)

    def get_customizable_model_schema(self, model: str, credentials: dict) -> AIModelEntity:
        """A model added by id: its figures come from tokens.bd, not from a form."""
        info = model_info(model, credentials)
        settings = {**credentials, **self._settings(model, credentials)}
        settings["context_size"] = str(
            (info.context_length if info else None) or FALLBACK_CONTEXT
        )
        settings["max_tokens_to_sample"] = str(
            (info.max_output_tokens if info else None) or FALLBACK_MAX_OUTPUT
        )
        settings["vision_support"] = "support" if info and info.image else "not_support"
        settings["video_support"] = "support" if info and info.video else "not_support"

        entity = super().get_customizable_model_schema(model, settings)
        label = str(credentials.get("display_name") or "").strip() or _label(model, info)
        entity.label = I18nObject(en_US=label)
        if settings["function_calling_type"] == "tool_call":
            entity.features = _with(entity.features, ModelFeature.AGENT_THOUGHT)
        for rule in entity.parameter_rules:
            if rule.name == "max_tokens" and rule.max:
                rule.default = min(4096, int(rule.max))
        # tokens.bd prices depend on the plan and currency; its dashboard is the bill. A zero price
        # here would show a wrong cost, so Dify shows none.
        entity.pricing = None
        return entity

    def _transform_invoke_error(self, error: Exception) -> InvokeError:
        """Keeps tokens.bd's own message instead of the SDK's generic one."""
        translated = translate_error(error)
        if isinstance(translated, InvokeError):
            return translated
        return super()._transform_invoke_error(error)


def _label(model: str, info: ModelInfo | None) -> str:
    return info.name if info and info.name and info.name != model else model


def _with(features: list | None, feature: ModelFeature) -> list:
    current = list(features or [])
    if feature not in current:
        current.append(feature)
    return current
