# Voice Hardware Setup — Wake Word, STT, TTS

## Quick start (2 things only)

Everything is picked and wired for you already — best defaults, all the
code, all the config. There are exactly two things only you can do
(this sandbox's network policy blocks Hugging Face, the one real host
these files live on, so an agent session cannot fetch them on your
behalf):

1. **Download one voice file** — click both of these on your own
   machine, save them in the *same folder*:
   - Model: https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx?download=true
   - Config: https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json?download=true
2. **Set 3 lines in `.env`** (copy exactly, replacing the path with
   wherever you saved the file):
   ```
   VEYRA_WAKE_WORD_PROVIDER=openwakeword
   VEYRA_STT_PROVIDER=whisper_cpp
   VEYRA_TTS_PROVIDER=piper
   VEYRA_PIPER_VOICE_MODEL_PATH=C:\VEYRA\models\en_US-lessac-medium.onnx
   ```

That's it — wake word (`hey_jarvis`, see below for why) and speech-to-
text need no download at all; they fetch/load automatically the first
time you start the backend. Everything below is detail/reference, not
more steps.

## Reference: what's real and why these choices

Real, local, offline providers exist for wake-word detection
(openWakeWord), speech-to-text (whisper.cpp via `pywhispercpp`), and
text-to-speech (Piper) — `services/voice/voice/providers/real.py`. None
of them call a cloud API or need an API key; all audio stays on your
machine.

`services/local-api/app/services/voice/pipeline.py`'s
`VoiceHardwarePipeline` is the real glue: it listens continuously for
the wake word, records one bounded utterance after a wake, transcribes
it, feeds the text into the already-real `VoiceConversationManager`
(the same task pipeline every other VEYRA interface uses), and speaks
the response back. See `docs/architecture/runtime.md` for how that
manager fits into the rest of VEYRA.

## 1. Install the real packages

```bash
cd services/voice
pip install -e ".[wake-word,stt,tts,audio]"
```

Each extra is independent — install only what you need. `audio`
(`sounddevice`) needs a real microphone/speaker; on Windows its wheel
bundles PortAudio, so no separate system install is required there. On
Linux, `sounddevice` additionally needs the `libportaudio2` system
package (`apt-get install -y libportaudio2`).

## 2. Wake word — pick a bundled phrase

openWakeWord ships small pretrained models inside the package itself —
no download needed for these:

| `VEYRA_WAKE_WORD_MODEL` | Phrase |
|---|---|
| `hey_jarvis` (default) | "Hey Jarvis" |
| `alexa` | "Alexa" |
| `hey_mycroft` | "Hey Mycroft" |
| `hey_rhasspy` | "Hey Rhasspy" |

**A custom "Hey VEYRA" model is real future work, not shipped here** —
openWakeWord's own training notebook
(https://github.com/dscripka/openWakeWord, "Custom Verification
Models") walks through training one from a small set of recorded/
synthesized samples of the phrase. Once you have a `.onnx` file, point
`VEYRA_WAKE_WORD_MODEL` at its path instead of a bundled name (the code
already accepts either — see `OpenWakeWordDetector`).

## 3. Speech-to-text — whisper.cpp model

`VEYRA_WHISPER_MODEL` accepts either a known shorthand
(`tiny.en`/`base.en`/`small.en`/`medium.en`/... — see
`WhisperSTTProvider`'s docstring for the full list) which
`pywhispercpp` downloads automatically on first use, or a direct path
to a `.bin` ggml model file you already have. `base.en` is a reasonable
default (fast, English-only, ~140MB download on first use).
`VEYRA_WHISPER_MODELS_DIR` optionally sets where downloaded models are
cached.

## 4. Text-to-speech — a real Piper voice file

Piper voices are large binary files, never bundled with this repo.
Download one from the official voices repository:
https://huggingface.co/rhasspy/piper-voices/tree/main (browse by
language, e.g. `en/en_US/lessac/medium/` for a natural US English
voice) — you need both the `.onnx` file and its matching `.onnx.json`
config file, saved next to each other. Point
`VEYRA_PIPER_VOICE_MODEL_PATH` at the `.onnx` file's path.

## 5. `.env` example

```
VEYRA_WAKE_WORD_PROVIDER=openwakeword
VEYRA_WAKE_WORD_MODEL=hey_jarvis

VEYRA_STT_PROVIDER=whisper_cpp
VEYRA_WHISPER_MODEL=base.en

VEYRA_TTS_PROVIDER=piper
VEYRA_PIPER_VOICE_MODEL_PATH=C:\VEYRA\models\en_US-lessac-medium.onnx
```

All three must be set (provider + whatever model/path each needs) for
the hardware pipeline to actually start listening — a partial
configuration is reported honestly (`DEGRADED`/`ERROR` in `GET
/system`'s `voice` field) but the always-on wake-word loop only starts
once wake-word, STT, and TTS have all loaded successfully.

## 6. Verifying it worked

1. Start the backend (`docs/development/runbook.md`). Look for a
   `[VOICE] CONNECTED — ...` line in the startup log, or check `GET
   /system`'s `voice` field and its `details.voice` reason — it names
   exactly which components loaded and why, never a bare "yes/no".
2. Say the wake phrase, then a command, near your microphone. A real
   utterance gets recorded (up to 12s, ending early after ~0.7s of
   silence), transcribed, run through the normal task pipeline, and
   spoken back — check the Local API log for `[VOICE] Wake word
   detected...` and the desktop app's Task Panel for the resulting
   task.
3. If nothing happens: `GET /system`'s `voice.details` reason tells you
   exactly what's missing (a package, a model file, or no audio
   hardware/PortAudio found) — never a silent failure.

## What this repo's own dev/CI sandbox cannot verify

No real microphone/speaker or PortAudio system library exists in this
repository's own development/CI environment — `sounddevice`'s real
`AudioInput`/`AudioOutput` classes were written and reviewed carefully
but could not be exercised against real hardware here. Wake-word
detection, VAD, and the STT/TTS synthesis-and-transcription round trip
were all live-verified for real during development (see
`tests/unit/test_real_voice_providers.py` and
`tests/integration/test_voice_hardware_pipeline.py`) — only the actual
"is a microphone plugged in" step needs verification on your machine.
