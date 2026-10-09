# livekit-plugins-readaloud

[ReadAloud](https://readaloudai.org) text-to-speech plugin for [LiveKit Agents](https://github.com/livekit/agents).
It streams audio from the ReadAloud API as it is generated, so a voice agent can start speaking within a few hundred
milliseconds, and it can output 8 kHz audio for phone calls. Closing a stream (barge-in) closes the HTTP connection,
which stops generation on the server.

**Maintainer:** this plugin is written and maintained by the author of ReadAloud, the speech API provider.

## Installation

```bash
pip install livekit-plugins-readaloud
export READALOUD_API_KEY=rtts_...
```

Get an API key at [readaloudai.org/developers](https://readaloudai.org/developers). New keys include a small free
allowance.

## Usage

```python
from livekit.agents import AgentSession
from livekit.plugins import readaloud

session = AgentSession(
    # stt=..., llm=...,
    tts=readaloud.TTS(voice="default", sample_rate=24000),   # sample_rate: 24000 | 16000 | 8000
)
```

`readaloud.TTS(api_key=None, base_url="https://api.readaloudai.org", voice="default", speed=1.0, engine="piper",
sample_rate=24000, max_retries=2)`. `api_key` falls back to the `READALOUD_API_KEY` environment variable. `engine` is
`"piper"` (default) or `"kokoro"`. `synthesize()` returns a `ChunkedStream`; `stream()` returns a `SynthesizeStream`
that splits LLM tokens into sentences and synthesizes each with its own streaming request.

## Running the example

[`examples/readaloud_tts_to_wav.py`](examples/readaloud_tts_to_wav.py) synthesizes a sentence and saves it as a WAV
file. It needs only a ReadAloud API key, with no STT, LLM or LiveKit server:

```bash
pip install livekit-plugins-readaloud
export READALOUD_API_KEY=rtts_...
python examples/readaloud_tts_to_wav.py "Thanks for calling. How can I help you today?"
```

## Behaviour

- Capacity responses (HTTP 503 and 429) become a retryable `APIStatusError`, so LiveKit's `APIConnectOptions` retry
  applies on top of the plugin's own pre-audio retries. Set `max_retries=0` to leave retrying to LiveKit.
- Authentication (401), quota (402), bad request and unknown voice (400, 404) errors surface immediately.
- No aligned transcripts: the API returns no word timestamps.

## Compatibility

Tested with `livekit-agents==1.8.5` and Python 3.14; requires `livekit-agents>=1.8,<2`. The tests run against a local
fake of the ReadAloud HTTP protocol (`pip install -e '.[dev]' && pytest`), and the example and plugin were also run
against the live API.

## Changelog

See [CHANGELOG.md](CHANGELOG.md). Licensed under MIT.
