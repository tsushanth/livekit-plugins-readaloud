"""ReadAloud TTS plugin for LiveKit Agents."""
from livekit.agents import Plugin

from ._client import ReadAloudAPIError
from .tts import TTS, ChunkedStream, SynthesizeStream
from .version import __version__

__all__ = ["TTS", "ChunkedStream", "SynthesizeStream", "ReadAloudAPIError", "__version__"]


class ReadAloudPlugin(Plugin):
    def __init__(self) -> None:
        super().__init__(__name__, __version__, __package__ or "livekit.plugins.readaloud")


Plugin.register_plugin(ReadAloudPlugin())

# Hide the module internals from pdoc / autocompletion
_module = dir()
NOT_IN_ALL = [m for m in _module if m not in __all__]
__pdoc__ = {n: False for n in NOT_IN_ALL}
