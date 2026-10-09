"""ReadAloud ``tts.TTS`` implementation for LiveKit Agents.

* ``synthesize(text)`` -> ``ChunkedStream``: one HTTP request, audio pushed to the ``AudioEmitter`` as it arrives.
* ``stream()``         -> ``SynthesizeStream``: LLM tokens are split into sentences (``tokenize.basic``) and each
  sentence is synthesized by its own streaming HTTP request, in order. This is how the public API streams today
  (there is no bidirectional text WebSocket on the native API), so streaming here means sentence-level pipelining,
  not token-level.
* Barge-in: LiveKit closes the stream (``aclose()``/task cancel); that closes the HTTP connection, which
  is ReadAloud's stop signal.
* No aligned transcripts (the API has no word timings): ``aligned_transcript=False``.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Optional

import aiohttp
from livekit.agents import (DEFAULT_API_CONNECT_OPTIONS, APIConnectionError, APIConnectOptions, APIStatusError,
                            APITimeoutError, tokenize, tts, utils)

from ._client import (DEFAULT_BASE_URL, SUPPORTED_FORMATS, AudioStream, ReadAloudAPIError, RequestConfig)

PROVIDER = "ReadAloud"


@dataclass
class _Opts:
    cfg: RequestConfig
    voice: str
    speed: float
    sentence_tokenizer: tokenize.SentenceTokenizer


def _to_api_error(e: ReadAloudAPIError):
    if e.status is not None:
        return APIStatusError(e.message, status_code=e.status, body=e.code, retryable=e.retryable)
    if e.code == "connection":
        return APIConnectionError(e.message, retryable=True)
    return APIConnectionError(e.message, retryable=False)


class TTS(tts.TTS):
    """ReadAloud TTS.

    Args:
        api_key: ReadAloud key (``rtts_...``); falls back to env ``READALOUD_API_KEY``.
        base_url: API origin (default ``https://api.readaloudai.org``).
        voice: voice id (default ``"default"``; ``af_heart``-style Kokoro ids or ``custom:<id>``).
        speed: 0.5-4.0.
        engine: ``"piper"`` (default) or ``"kokoro"``.
        sample_rate: ``24000`` (default), ``16000`` (served via the ElevenLabs-compatible endpoint) or ``8000``
            (telephony; native 8 kHz render). LiveKit frames are always PCM16; this is the rate declared to the framework.
        http_session: optional shared ``aiohttp.ClientSession`` (default: LiveKit's job http session, else a private one).
        max_retries: internal retries (capacity / 5xx / connect) before the first audio byte. LiveKit's own
            ``APIConnectOptions`` retries apply on top; set this to 0 to leave retrying entirely to LiveKit.
    """

    def __init__(self, *, api_key: Optional[str] = None, base_url: str = DEFAULT_BASE_URL, voice: str = "default",
                 speed: float = 1.0, engine: str = "piper", sample_rate: int = 24000,
                 http_session: Optional[aiohttp.ClientSession] = None, max_retries: int = 2,
                 sentence_tokenizer: Optional[tokenize.SentenceTokenizer] = None) -> None:
        if sample_rate not in (8000, 16000, 24000):
            raise ValueError("sample_rate must be 8000, 16000 or 24000")
        super().__init__(capabilities=tts.TTSCapabilities(streaming=True, aligned_transcript=False),
                         sample_rate=sample_rate, num_channels=1)
        fmt = f"pcm_{sample_rate}"
        assert fmt in SUPPORTED_FORMATS
        cfg = RequestConfig(api_key=api_key or os.environ.get("READALOUD_API_KEY", ""), base_url=base_url,
                            engine=engine, output_format=fmt, max_retries=max_retries)
        cfg.validate()
        self._opts = _Opts(cfg, voice, speed, sentence_tokenizer or tokenize.basic.SentenceTokenizer())
        self._session = http_session
        self._own_session: Optional[aiohttp.ClientSession] = None

    @property
    def model(self) -> str:
        return self._opts.cfg.engine

    @property
    def provider(self) -> str:
        return PROVIDER

    def _http(self) -> aiohttp.ClientSession:
        if self._session is not None:
            return self._session
        try:
            return utils.http_context.http_session()   # inside a LiveKit job
        except RuntimeError:
            if self._own_session is None or self._own_session.closed:
                self._own_session = aiohttp.ClientSession()
            return self._own_session

    def update_options(self, *, voice: Optional[str] = None, speed: Optional[float] = None) -> None:
        if voice is not None:
            self._opts.voice = voice
        if speed is not None:
            self._opts.speed = speed

    def synthesize(self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> ChunkedStream:
        return ChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    def stream(self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> SynthesizeStream:
        return SynthesizeStream(tts=self, conn_options=conn_options)

    async def aclose(self) -> None:
        if self._own_session is not None and not self._own_session.closed:
            await self._own_session.close()


async def _pump(tts_: TTS, text: str, output_emitter: tts.AudioEmitter, timeout: float) -> None:
    """One streaming HTTP request -> AudioEmitter. Raises LiveKit API errors."""
    o = tts_._opts
    stream = AudioStream(tts_._http(), o.cfg, text, o.voice, o.speed)
    try:
        async for chunk in stream:
            output_emitter.push(chunk)
    except ReadAloudAPIError as e:
        raise _to_api_error(e) from e
    except asyncio.TimeoutError as e:
        raise APITimeoutError() from e
    finally:
        await stream.aclose()


class ChunkedStream(tts.ChunkedStream):
    def __init__(self, *, tts: TTS, input_text: str, conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts: TTS = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        output_emitter.initialize(request_id=utils.shortuuid(), sample_rate=self._tts.sample_rate, num_channels=1,
                                  mime_type="audio/pcm")
        await _pump(self._tts, self._input_text, output_emitter, self._conn_options.timeout)
        output_emitter.flush()


class SynthesizeStream(tts.SynthesizeStream):
    def __init__(self, *, tts: TTS, conn_options: APIConnectOptions) -> None:
        super().__init__(tts=tts, conn_options=conn_options)
        self._tts: TTS = tts

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        output_emitter.initialize(request_id=utils.shortuuid(), sample_rate=self._tts.sample_rate, num_channels=1,
                                  mime_type="audio/pcm", stream=True)
        output_emitter.start_segment(segment_id=utils.shortuuid())
        sent_stream = self._tts._opts.sentence_tokenizer.stream()

        async def _forward_input() -> None:
            async for data in self._input_ch:
                if isinstance(data, self._FlushSentinel):
                    sent_stream.flush()
                    continue
                sent_stream.push_text(data)
            sent_stream.end_input()

        async def _synthesize() -> None:
            async for ev in sent_stream:
                text = ev.token.strip()
                if not text:
                    continue
                self._mark_started()
                await _pump(self._tts, text, output_emitter, self._conn_options.timeout)
                output_emitter.flush()
            output_emitter.end_segment()

        tasks = [asyncio.create_task(_forward_input()), asyncio.create_task(_synthesize())]
        try:
            await asyncio.gather(*tasks)
        finally:
            await sent_stream.aclose()
            await utils.aio.cancel_and_wait(*tasks)
