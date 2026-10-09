# Changelog

## 0.1.1 - 2026-10-09
- Added a single-file example (`examples/readaloud_tts_to_wav.py`) that needs only a ReadAloud API key.
- README rewritten: install, usage in an `AgentSession`, running the example, compatibility.
- Verified against the live ReadAloud API with livekit-agents 1.8.5.

## 0.1.0 - 2026-10-09
- First release: `readaloud.TTS` plugin with `synthesize()` and sentence-level `stream()`, Piper and Kokoro voices, 24 kHz / 16 kHz / 8 kHz output, retries before the first audio byte, cancellation on barge-in.
