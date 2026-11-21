# Privacy policy: tokens.bd plugin for Dify

This plugin connects Dify to the tokens.bd API (`https://tokens.bd/v1`). It stores nothing itself.

## What the plugin sends, and where

Everything goes to tokens.bd over HTTPS, and nowhere else.

- **Your API key.** It is sent on every request to identify your account. Dify stores it encrypted in your Dify workspace. The plugin never logs it or returns it in an error.
- **Your requests.** The messages, any images or files attached, tool definitions, the model ID and generation settings, for each request a Dify app makes. tokens.bd forwards them to the provider of the model you chose (for example Anthropic, OpenAI or Google) to get the answer.
- **The plugin's name and version.** They are sent in the `User-Agent` header (`dify-plugin-tokensbd/<version>`). tokens.bd uses it to record that your API key is used from Dify, which appears in its own usage reports.

The plugin also reads, with your key, the list of models available to you (`GET /v1/models`).

## What tokens.bd keeps

tokens.bd meters each request for billing: the model, token counts, cost, latency and status, linked to your account and key. It does not archive your prompts or the answers. Its privacy policy covers how long records are kept and your rights:

- https://tokens.bd/privacy
- https://tokens.bd/security

The model providers that tokens.bd forwards requests to handle them under their own terms.

## Personal data

The plugin collects no personal data of its own. Whatever personal data your Dify users put in their messages is sent to tokens.bd and the model provider as part of the request.

## Contact

Questions about this policy: https://tokens.bd/contact or https://github.com/mdbadsha/dify-plugin-tokensbd/issues
