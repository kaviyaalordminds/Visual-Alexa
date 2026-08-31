#!/usr/bin/env python3
"""Record real-voice "Hey VEYRA" samples to improve wake-word accuracy.

Usage:
    python scripts/record_wake_word_samples.py

What it does:
  - Plays a beep cue, then records 2 seconds of audio per clip.
  - Saves clips to  scripts/my_wake_word_clips/
  - After recording, use:
      python scripts/train_hey_veyra_wakeword.py --extra-clips scripts/my_wake_word_clips/*.wav

Requirements: sounddevice, soundfile  (already in .venv)
"""

import pathlib
import sys
import time
import wave
import struct

OUT_DIR = pathlib.Path(__file__).parent / "my_wake_word_clips"
SAMPLE_RATE = 16000
DURATION_SECS = 2.5      # slightly longer to capture the full phrase
N_CLIPS = 25             # 25 clips = much better accuracy than 0 real clips
CHUNK = 1280

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    sys.exit(
        "sounddevice / numpy not installed.\n"
        "  .venv\\Scripts\\pip install sounddevice numpy"
    )

OUT_DIR.mkdir(parents=True, exist_ok=True)


def _beep(freq: int = 880, duration: float = 0.15) -> None:
    """Short audible cue so you know when to speak."""
    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
    tone = (0.4 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    sd.play(tone, SAMPLE_RATE)
    sd.wait()


def _write_wav(path: pathlib.Path, data: np.ndarray) -> None:
    samples_int16 = (data * 32767).clip(-32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples_int16.tobytes())


def main() -> None:
    print("=== Hey VEYRA Real-Voice Recorder ===")
    print(f"Output folder: {OUT_DIR}")
    print(f"Recording {N_CLIPS} clips × {DURATION_SECS}s each.")
    print()
    print("Instructions:")
    print("  - When you hear the BEEP, say 'Hey VEYRA' clearly.")
    print("  - Vary your tone slightly each time (normal, louder, softer, faster, slower).")
    print("  - Sit approx. 30-60 cm from your mic — the typical real-use distance.")
    print()
    input("Press ENTER to start recording...")
    print()

    n_samples = int(SAMPLE_RATE * DURATION_SECS)
    existing = list(OUT_DIR.glob("real_*.wav"))
    start_idx = len(existing)

    for i in range(N_CLIPS):
        clip_idx = start_idx + i
        dest = OUT_DIR / f"real_{clip_idx:04d}.wav"

        print(f"  Clip {i + 1:2d}/{N_CLIPS} — GET READY …", end="", flush=True)
        time.sleep(0.6)
        _beep(880, 0.12)         # high beep = speak now
        print("  SAY IT NOW!", end="", flush=True)

        audio = sd.rec(n_samples, samplerate=SAMPLE_RATE, channels=1, dtype="float32")
        sd.wait()
        audio = audio.flatten()

        _write_wav(dest, audio)
        _beep(440, 0.08)         # low beep = done
        print(f"  ✓ saved {dest.name}")
        time.sleep(0.4)

    print()
    print(f"Done! {N_CLIPS} clips saved to: {OUT_DIR}")
    print()
    print("Next step — retrain the wake-word model with your real voice:")
    print()
    clips_glob = str(OUT_DIR / "real_*.wav")
    print(f"  del models\\hey_veyra.onnx")
    print(f"  .venv\\Scripts\\python.exe scripts\\train_hey_veyra_wakeword.py --extra-clips {clips_glob}")
    print()
    print("Then restart the backend.")


if __name__ == "__main__":
    main()
