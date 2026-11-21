# tokens.bd for Dify

**Author:** mdbadsha · **Type:** model provider · **Source:** https://github.com/mdbadsha/dify-plugin-tokensbd

Use Claude, GPT, Gemini, DeepSeek, Qwen, GLM, Kimi and more in Dify through one [tokens.bd](https://tokens.bd) API key. tokens.bd is an OpenAI-compatible gateway with plan or pay-as-you-go billing in USD or BDT.

## Features

- **Ready to use.** `auto` and `best-value` are listed as soon as the key is saved. tokens.bd keeps them pointed at a good current model.
- **Any model by its ID, with nothing else to fill in.** Add a model from [tokens.bd/models](https://tokens.bd/models) by its ID. The plugin reads its context window, maximum output, vision and tool support from tokens.bd, so you don't type them.
- **Agents and tools.** Tool calls and streamed tool calls work for models that support them.
- **Clear errors.** An empty balance, a plan limit, a model outside your plan or a key limit each comes back with what to do and a request ID for support.
- **Free key check.** Saving the key lists your models instead of running one, so it costs nothing.

## Setup

1. Create an API key at [tokens.bd/dashboard/keys](https://tokens.bd/dashboard/keys). You need a plan or a wallet balance to use models.
2. In Dify, open **Plugins**, find **tokens.bd** in the Marketplace and install it.
3. Open **Settings > Model Provider > tokens.bd**, paste the key and save. Leave **API Base URL** empty to use `https://tokens.bd/v1`.

Requirements: the Dify server must be able to reach `https://tokens.bd` over HTTPS. The plugin works on Dify Cloud and on self-hosted Dify.

## Usage

- Pick `auto` or `best-value` in any LLM node, chat app or agent.
- To use a specific model, click **Add Model** on the tokens.bd card. Enter the model ID, for example `anthropic/claude-opus-5-5`, and the same API key, then save. The display name is optional.
- Usage and costs show in your tokens.bd dashboard under the key you used. Dify shows no prices, because they depend on your plan and currency.

## Privacy

The plugin sends your prompts, files and the model ID to tokens.bd. tokens.bd forwards them to the model's provider. See [PRIVACY.md](PRIVACY.md) and the [tokens.bd privacy policy](https://tokens.bd/privacy).

## Support

Open an issue at https://github.com/mdbadsha/dify-plugin-tokensbd/issues, or contact tokens.bd support from [tokens.bd/contact](https://tokens.bd/contact). Never post your API key.
