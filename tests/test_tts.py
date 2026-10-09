import asyncio
import os
import sys

import aiohttp
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from fake_readaloud import KEY, FakeReadAloud  # noqa: E402

from livekit.agents import APIConnectOptions, APIStatusError, tts as lk_tts  # noqa: E402
from livekit.plugins import readaloud  # noqa: E402

FAST = APIConnectOptions(max_retry=0, retry_interval=0, timeout=5)


@pytest.fixture
async def server():
    s = await FakeReadAloud().start()
    yield s
    await s.stop()


@pytest.fixture
async def session():
    async with aiohttp.ClientSession() as s:
        yield s


def make(server, session, **kw):
    kw.setdefault("api_key", KEY)
    kw.setdefault("max_retries", 0)
    return readaloud.TTS(base_url=server.url, http_session=session, **kw)


def test_is_a_livekit_tts_with_declared_capabilities():
    t = readaloud.TTS(api_key="k")
    assert isinstance(t, lk_tts.TTS)
    assert t.capabilities.streaming and not t.capabilities.aligned_transcript
    assert (t.sample_rate, t.num_channels, t.provider, t.model) == (24000, 1, "ReadAloud", "piper")


async def test_synthesize_chunked_stream(server, session):
    t = make(server, session)
    async with t.synthesize("hello world", conn_options=FAST) as s:
        frame = await s.collect()
    assert frame.sample_rate == 24000 and frame.num_channels == 1
    assert frame.duration > 0.1
    r = server.requests[0]
    assert r["native"] and r["body"]["format"] == "pcm_24000" and r["body"]["engine"] == "piper"


@pytest.mark.parametrize("rate,fmt,native", [(8000, "pcm_8000", True), (16000, "pcm_16000", False)])
async def test_sample_rates(server, session, rate, fmt, native):
    t = make(server, session, sample_rate=rate)
    async with t.synthesize("hi", conn_options=FAST) as s:
        frame = await s.collect()
    assert frame.sample_rate == rate
    assert server.requests[0]["format"] == fmt and server.requests[0]["native"] is native


async def test_synthesize_stream_sentence_pipelining(server, session):
    t = make(server, session)
    s = t.stream(conn_options=FAST)
    for tok in ["Hello there. ", "How are ", "you today? ", "Fine."]:
        s.push_text(tok)
    s.end_input()
    frames = []
    async for ev in s:
        frames.append(ev.frame)
    await s.aclose()
    texts = [r["body"]["text"] for r in server.requests]
    # livekit's basic tokenizer merges sentences shorter than min_sentence_len (20 chars)
    assert texts == ["Hello there. How are you today?", "Fine."]
    assert sum(f.duration for f in frames) > 0.3


async def test_internal_capacity_retry(server, session):
    server.capacity_left = 2
    t = make(server, session, max_retries=3)
    t._opts.cfg.backoff_base = 0.01
    async with t.synthesize("CAPACITY2 hi", conn_options=FAST) as s:
        frame = await s.collect()
    assert frame.duration > 0 and len(server.requests) == 3


async def test_capacity_surfaces_as_retryable_api_error_and_livekit_retries(server, session):
    server.capacity_left = 1
    t = make(server, session, max_retries=0)       # leave retrying to LiveKit
    errors = []
    t.on("error", lambda e: errors.append(e))
    opts = APIConnectOptions(max_retry=2, retry_interval=0, timeout=5)
    async with t.synthesize("CAPACITY2 hi", conn_options=opts) as s:
        frame = await s.collect()
    assert frame.duration > 0 and len(server.requests) == 2
    assert errors and errors[0].recoverable and errors[0].error.status_code == 503


async def test_auth_error_not_retryable(server, session):
    t = make(server, session, api_key="bad")
    with pytest.raises(APIStatusError) as ei:
        async with t.synthesize("hi", conn_options=APIConnectOptions(max_retry=3, retry_interval=0, timeout=5)) as s:
            await s.collect()
    assert ei.value.status_code == 401 and not ei.value.retryable and len(server.requests) == 0


async def test_quota_error(server, session):
    t = make(server, session)
    with pytest.raises(APIStatusError) as ei:
        async with t.synthesize("QUOTA", conn_options=FAST) as s:
            await s.collect()
    assert ei.value.status_code == 402 and not ei.value.retryable


async def test_barge_in_closes_connection(server, session):
    t = make(server, session)
    s = t.stream(conn_options=FAST)
    s.push_text("SLOW")
    s.end_input()
    it = s.__aiter__()
    await asyncio.wait_for(it.__anext__(), 5)       # audio is flowing
    await s.aclose()                                  # what LiveKit does on interruption
    await asyncio.wait_for(server.disconnected.wait(), 3)
    assert server.completed == 0


def test_requires_key(monkeypatch):
    monkeypatch.delenv("READALOUD_API_KEY", raising=False)
    with pytest.raises(ValueError):
        readaloud.TTS()


def test_client_copy_in_sync_with_pipecat_package():
    here = os.path.dirname(__file__)
    a = open(os.path.join(here, "..", "livekit", "plugins", "readaloud", "_client.py")).read()
    b = os.path.join(here, "..", "..", "pipecat-readaloud", "src", "pipecat_readaloud", "_client.py")
    if os.path.exists(b):
        assert a == open(b).read()
