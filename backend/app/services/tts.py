"""Google Cloud Text-to-Speech, synthesising straight into Twilio's wire format.

AssemblyAI has no standalone TTS product - it is bundled inside the Voice Agent
API and not exposed separately - so the stt_gemini backend brings its own
voice. Google Cloud is the natural pick here: the project already carries
google-cloud-* credentials and packages.

Synthesis requests MULAW at 8000Hz, which is exactly what Twilio Media Streams
carry, so nothing is resampled on this path either. The audioop-based
resampling this project used to need went away with the Gemini Live bridge.
"""

import logging
import struct
from functools import lru_cache

from google.cloud import texttospeech

logger = logging.getLogger(__name__)

TWILIO_SAMPLE_RATE = 8000


class TextToSpeechNotConfigured(RuntimeError):
    pass


@lru_cache
def get_client() -> texttospeech.TextToSpeechAsyncClient:
    try:
        return texttospeech.TextToSpeechAsyncClient()
    except Exception as exc:  # credentials missing / malformed
        raise TextToSpeechNotConfigured(str(exc)) from exc


def _strip_wav_header(audio: bytes) -> bytes:
    """Return raw samples, dropping a RIFF/WAVE container if one is present.

    Google returns MULAW wrapped in a WAV container. Twilio wants bare mu-law
    bytes - shipping the 44-plus byte header through as audio is heard as a
    click at the start of every utterance.
    """
    if not audio.startswith(b"RIFF"):
        return audio
    offset = 12  # past "RIFF" + size + "WAVE"
    while offset + 8 <= len(audio):
        chunk_id = audio[offset : offset + 4]
        (chunk_size,) = struct.unpack("<I", audio[offset + 4 : offset + 8])
        body = offset + 8
        if chunk_id == b"data":
            return audio[body : body + chunk_size]
        offset = body + chunk_size + (chunk_size % 2)
    logger.warning("WAV container had no data chunk; passing audio through unchanged")
    return audio


async def synthesize_mulaw(text: str, *, voice_name: str = "en-US-Neural2-F") -> bytes:
    """Synthesise text to bare 8kHz mu-law bytes, ready for Twilio."""
    client = get_client()
    response = await client.synthesize_speech(
        input=texttospeech.SynthesisInput(text=text),
        voice=texttospeech.VoiceSelectionParams(language_code="en-US", name=voice_name),
        audio_config=texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MULAW,
            sample_rate_hertz=TWILIO_SAMPLE_RATE,
        ),
    )
    return _strip_wav_header(response.audio_content)
