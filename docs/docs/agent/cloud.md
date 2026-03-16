# Cloud Setup (Gemini API)

If Ollama is not running, the agent automatically falls back to the Gemini API.

## Get a free API key

1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Sign in with your Google account
3. Click **Get API key** → **Create API key**
4. Copy the key

## Set the key

```bash
export GEMINI_API_KEY=your_key_here
```

To persist across sessions, add to `~/.zshrc`:
```bash
echo 'export GEMINI_API_KEY=your_key_here' >> ~/.zshrc
source ~/.zshrc
```

## Verify

```bash
analogdata-esp doctor
# GEMINI_API_KEY   ✅ set   ...abc123
```

## Free tier limits

The Gemini API free tier (as of 2025) allows:

- 15 requests per minute
- 1 million tokens per minute
- 1,500 requests per day

For typical ESP-IDF debugging sessions this is more than sufficient.

## Notes

- The Gemini cloud API sends your question and build errors to Google's servers.
- For sensitive or proprietary firmware, use the local Ollama setup instead.
- The model used is `gemma-3-4b-it` — same architecture as the local Gemma model.
