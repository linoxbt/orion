"""DTMF tone generation, straight into Twilio's wire format.

A real provider line answers with a menu before a human ever does, and pressing
a key is the only way through most of them. The call is already inside a
bidirectional Media Stream, so the tones are synthesised here and pushed as
ordinary audio frames - redirecting the call to a <Play digits=""> TwiML verb
would tear the stream down mid-call.

A DTMF digit is just two sine waves summed: a row frequency and a column one.
Encoding to G.711 mu-law is done in-process rather than via stdlib audioop,
which is deprecated and gone in 3.13 - keeping this pure Python is what lets
the project move off its 3.12 pin later.
"""

import math

SAMPLE_RATE = 8000  # Twilio's native rate
TONE_MS = 120       # comfortably above the 40ms minimum receivers accept
GAP_MS = 80         # silence between digits, so they aren't read as one tone
AMPLITUDE = 8000    # per component; the sum stays well clear of int16 clipping

# Row frequency, column frequency. The A-D column is rare but valid, and some
# enterprise IVRs still use it.
_TONES: dict[str, tuple[int, int]] = {
    "1": (697, 1209), "2": (697, 1336), "3": (697, 1477), "A": (697, 1633),
    "4": (770, 1209), "5": (770, 1336), "6": (770, 1477), "B": (770, 1633),
    "7": (852, 1209), "8": (852, 1336), "9": (852, 1477), "C": (852, 1633),
    "*": (941, 1209), "0": (941, 1336), "#": (941, 1477), "D": (941, 1633),
}

VALID_KEYS = frozenset(_TONES) | {",", "w"}  # , and w mean "pause"


# G.711 segment ends, on the 14-bit scale the codec actually works in.
_SEG_END = (0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF)


def linear_to_ulaw(sample: int) -> int:
    """One signed 16-bit PCM sample -> one G.711 mu-law byte.

    Follows the Sun/sox reference implementation, including the >> 2 down to
    14 bits that the codec is defined on. Skipping that shift produces output
    that is correct across most of the range and wrong near full scale, which
    is the kind of bug that survives a casual listen and then mangles a loud
    tone - test_dtmf.py checks all 65536 inputs against the reference.
    """
    sample >>= 2  # 16-bit -> 14-bit

    if sample < 0:
        sample = -sample
        mask = 0x7F
    else:
        mask = 0xFF

    if sample > 8159:  # clip
        sample = 8159
    sample += 33  # bias, 0x84 on the 14-bit scale

    segment = next((i for i, end in enumerate(_SEG_END) if sample <= end), 8)
    if segment >= 8:
        return 0x7F ^ mask
    return ((segment << 4) | ((sample >> (segment + 1)) & 0x0F)) ^ mask


def _tone(low: int, high: int, duration_ms: int) -> bytes:
    samples = int(SAMPLE_RATE * duration_ms / 1000)
    out = bytearray(samples)
    for n in range(samples):
        t = n / SAMPLE_RATE
        value = int(
            AMPLITUDE * math.sin(2 * math.pi * low * t)
            + AMPLITUDE * math.sin(2 * math.pi * high * t)
        )
        out[n] = linear_to_ulaw(value)
    return bytes(out)


def _silence(duration_ms: int) -> bytes:
    # 0xFF is mu-law digital zero, not 0x00 - sending 0x00 is full-scale noise.
    return b"\xff" * int(SAMPLE_RATE * duration_ms / 1000)


def keys_to_mulaw(keys: str) -> bytes:
    """Render a key sequence as 8kHz mu-law audio, ready for Twilio.

    "," and "w" insert a half-second pause, which menus that speak over
    themselves often need. Unknown characters are skipped rather than raising -
    a malformed tool argument must not tear down a live call.
    """
    audio = bytearray()
    for key in keys.strip().upper():
        if key in (",", "W"):
            audio += _silence(500)
            continue
        pair = _TONES.get(key)
        if pair is None:
            continue
        audio += _tone(*pair, TONE_MS)
        audio += _silence(GAP_MS)
    return bytes(audio)
