"""Foundational example: synthesize a sentence with the ReadAloud TTS plugin for LiveKit Agents and save it as a WAV file.

Needs only a ReadAloud API key (no STT, LLM or LiveKit server):

    export READALOUD_API_KEY=rtts_...
    python examples/readaloud_tts_to_wav.py "Thanks for calling. How can I help you today?"

The output is written to readaloud_example.wav (mono, 16-bit, 24 kHz).
"""
import asyncio
import os
import sys
import wave

import aiohttp
from livekit.plugins import readaloud

OUTPUT = "readaloud_example.wav"


async def main(text: str) -> None:
    async with aiohttp.ClientSession() as session:
        tts = readaloud.TTS(
            api_key=os.environ["READALOUD_API_KEY"],
            http_session=session,
            voice="default",
            sample_rate=24000,  # 24000 | 16000 | 8000
        )
        async with tts.synthesize(text) as stream:
            frame = await stream.collect()  # one combined rtc.AudioFrame

    with wave.open(OUTPUT, "wb") as f:
        f.setnchannels(frame.num_channels)
        f.setsampwidth(2)
        f.setframerate(frame.sample_rate)
        f.writeframes(bytes(frame.data))
    print(f"wrote {OUTPUT} ({frame.duration:.2f} s at {frame.sample_rate} Hz)")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "Thanks for calling. How can I help you today?"))
