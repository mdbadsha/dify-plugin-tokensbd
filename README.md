# tokens.bd for Dify

**Author:** mdbadsha · **Type:** model provider · **Source:** https://github.com/mdbadsha/dify-plugin-tokensbd

Use Claude, GPT, Gemini, DeepSeek, Qwen, GLM, Kimi and more in Dify through one [tokens.bd](https://tokens.bd) API key. tokens.bd is an OpenAI-compatible gateway with plan or pay-as-you-go billing in USD or BDT.

## Features

- **Any model by its ID, with nothing else to fill in.** Add a model from [tokens.bd/models](https://tokens.bd/models) by its ID. The plugin reads its context window, maximum output, vision and tool support from tokens.bd, so you don't type them.
- **Checked when you add it.** If your plan or wallet doesn't cover the model, or the ID is wrong, Dify says so when you save, not on the first request.
- **Agents and tools.** Tool calls and streamed tool calls work for models that support them.
- **Clear errors.** An empty balance, a plan limit, a model outside your plan or a key limit each comes back with what to do and a request ID for support.
- **Free key check.** Adding a model checks the key by listing your models, not by running one, so it costs nothing.

## Setup

1. Create an API key at [tokens.bd/dashboard/keys](https://tokens.bd/dashboard/keys). You need a plan or a wallet balance to use models.
2. In Dify, open **Plugins**, find **tokens.bd** in the Marketplace and install it.
3. Open **Settings > Model Provider > tokens.bd** and click **Add Model**.
4. Enter a model ID from [tokens.bd/models](https://tokens.bd/models), for example `anthropic/claude-opus-5-5`, and your API key, then save. Leave **API Base URL** empty to use `https://tokens.bd/v1`. The display name is optional.

Add each model you want to use the same way.

Requirements: the Dify server must be able to reach `https://tokens.bd` over HTTPS. The plugin works on Dify Cloud and on self-hosted Dify.

## Usage

- Pick a model you added in any LLM node, chat app or agent. Vision and tools are on for the models that support them.
- Usage and costs show in your tokens.bd dashboard under the key you used. Dify shows no prices, because they depend on your plan and currency.

## Privacy

The plugin sends your prompts, files and the model ID to tokens.bd. tokens.bd forwards them to the model's provider. See [PRIVACY.md](PRIVACY.md) and the [tokens.bd privacy policy](https://tokens.bd/privacy).

## Support

Open an issue at https://github.com/mdbadsha/dify-plugin-tokensbd/issues, or contact tokens.bd support from [tokens.bd/contact](https://tokens.bd/contact). Never post your API key.
