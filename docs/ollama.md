# Local Ollama provider

Ollama is optional and external to this repository. MedPlat never installs Ollama, downloads a
model, or runs `ollama pull`. The provider uses structured JSON over `POST /api/chat` and accepts
only plain HTTP endpoints whose host is `localhost` or a literal loopback address. No API key or
secret is stored.

Defaults are:

- base URL: `http://127.0.0.1:11434`
- timeout: 120 seconds
- temperature: 0
- context size: 8192 tokens
- seed: 42
- maximum output: 2048 tokens
- retries: 2

CLI options override environment variables. Supported environment variables are
`MEDPARSE_OLLAMA_BASE_URL`, `MEDPARSE_OLLAMA_MODEL`, `MEDPARSE_OLLAMA_TIMEOUT_SECONDS`,
`MEDPARSE_OLLAMA_TEMPERATURE`, `MEDPARSE_OLLAMA_CONTEXT_SIZE`, `MEDPARSE_OLLAMA_SEED`,
`MEDPARSE_OLLAMA_MAX_OUTPUT_TOKENS`, and `MEDPARSE_OLLAMA_RETRY_COUNT`.

Install a model only as a separate, explicit operator action. For the proposed initial model the
command is:

```bash
ollama pull qwen2.5:7b
```

Planning and `generate-content --dry-run` do not connect to Ollama. Tests inject a deterministic
mock provider and never create sockets.
