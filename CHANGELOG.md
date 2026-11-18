# Changelog

## 0.2.0 - 2026-11-14
- Public naming: `engine` now takes `"live"` (default) or `"studio"`, the two ReadAloud tiers, and the default voice id sent to the compatible endpoint is `readaloud-default`. The values accepted before 0.2.0 are no longer accepted by this package: change `engine=` to `"live"` or `"studio"`.
- Package description and keywords no longer name how voices are made; they list voice name, language, dialect and tier only.

## 0.1.1 - 2026-10-09
- Added a single-file example (`examples/readaloud_tts_to_wav.py`) that needs only a ReadAloud API key.
- README rewritten: install, usage in an `AgentSession`, running the example, compatibility.
- Verified against the live ReadAloud API with livekit-agents 1.8.5.

## 0.1.0 - 2026-10-09
- First release: `readaloud.TTS` plugin with `synthesize()` and sentence-level `stream()`, two voice tiers, 24 kHz / 16 kHz / 8 kHz output, retries before the first audio byte, cancellation on barge-in.
