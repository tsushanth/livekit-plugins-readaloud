# livekit-plugins-readaloud

[ReadAloud](https://readaloudai.org) text-to-speech plugin for [LiveKit Agents](https://github.com/livekit/agents).
Status: **alpha, unpublished** (see `../docs/STATUS_MATRIX.md`).

```bash
pip install livekit-plugins-readaloud   # not yet on PyPI: install from this directory with `pip install .`
export READALOUD_API_KEY=rtts_...
```

```python
from livekit.agents import AgentSession
from livekit.plugins import readaloud

session = AgentSession(
    # stt=..., llm=...,
    tts=readaloud.TTS(voice="default", sample_rate=24000),   # sample_rate: 24000 | 16000 | 8000
)
```

`readaloud.TTS(api_key=None, base_url="https://api.readaloudai.org", voice="default", speed=1.0, engine="piper",
sample_rate=24000, max_retries=2)`. `synthesize()` returns a `ChunkedStream`; `stream()` returns a `SynthesizeStream`
that splits LLM tokens into sentences and synthesizes each with its own streaming request (sentence-level
pipelining). Closing a stream (barge-in) closes the HTTP connection, which stops generation server-side. Capacity
(503/429) becomes a retryable `APIStatusError`, so LiveKit's `APIConnectOptions` retry applies on top of the plugin's own
pre-audio retries (set `max_retries=0` to leave retrying to LiveKit). No aligned transcripts. Tested with
`livekit-agents==1.8.5`; requires `livekit-agents>=1.8,<2`.

Tests: `pip install -e '.[dev]' && pytest`.
