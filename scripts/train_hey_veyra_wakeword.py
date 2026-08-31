#!/usr/bin/env python3
"""Train a speaker-independent "Hey VEYRA" openWakeWord model.

Uses Microsoft Edge TTS (edge-tts) with 50+ diverse English voices across
Indian, American, British, Australian, African, Asian accents — so the model
works for ANY speaker, not just the person who ran the script.

Usage:
    pip install edge-tts pyttsx3 soundfile onnxruntime scikit-learn onnx openwakeword
    python scripts/train_hey_veyra_wakeword.py

Optional — add your own real recordings on top:
    python scripts/train_hey_veyra_wakeword.py --extra-clips path/to/*.wav

What it does:
  1. Downloads openWakeWord's feature-extractor models (~50 MB, one-time).
  2. Generates 500+ "Hey VEYRA" clips via Edge TTS across 50 diverse voices.
  3. Applies audio augmentation (speed ×3, volume ×3 variants per clip).
  4. Generates 1000+ negative samples (silence, noise, distractor speech).
  5. Trains a logistic-regression classifier and exports it as .onnx.
  6. Saves the model to  models/hey_veyra.onnx.

No PyTorch. No microphone. No API key. Works offline after first TTS download.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import random
import shutil
import struct
import sys
import tempfile
import wave

PHRASE = "Hey VEYRA"
SAMPLE_RATE = 16000
REPO_ROOT = pathlib.Path(__file__).parent.parent
DEFAULT_OUT_MODEL = REPO_ROOT / "models" / "hey_veyra.onnx"

# ---------------------------------------------------------------------------
# Diverse English voices from Edge TTS — covers every major English accent
# so the model is speaker-independent from the start.
# ---------------------------------------------------------------------------
EDGE_TTS_VOICES = [
    # Indian English (most important for this deployment)
    "en-IN-NeerjaNeural",    # Indian Female
    "en-IN-PrabhatNeural",   # Indian Male
    # American English — many voice types
    "en-US-JennyNeural",
    "en-US-GuyNeural",
    "en-US-AriaNeural",
    "en-US-DavisNeural",
    "en-US-AmberNeural",
    "en-US-AnaNeural",
    "en-US-AshleyNeural",
    "en-US-BrandonNeural",
    "en-US-ChristopherNeural",
    "en-US-CoraNeural",
    "en-US-ElizabethNeural",
    "en-US-EricNeural",
    "en-US-JacobNeural",
    "en-US-JasonNeural",
    "en-US-MichelleNeural",
    "en-US-MonicaNeural",
    "en-US-NancyNeural",
    "en-US-RogerNeural",
    "en-US-SaraNeural",
    "en-US-SteffanNeural",
    "en-US-TonyNeural",
    # British English
    "en-GB-LibbyNeural",
    "en-GB-MaisieNeural",
    "en-GB-RyanNeural",
    "en-GB-SoniaNeural",
    "en-GB-ThomasNeural",
    # Australian English
    "en-AU-NatashaNeural",
    "en-AU-WilliamNeural",
    # Canadian English
    "en-CA-ClaraNeural",
    "en-CA-LiamNeural",
    # Irish English
    "en-IE-ConnorNeural",
    "en-IE-EmilyNeural",
    # New Zealand English
    "en-NZ-MitchellNeural",
    "en-NZ-MollyNeural",
    # Singapore English
    "en-SG-LunaNeural",
    "en-SG-WayneNeural",
    # South African English
    "en-ZA-LeahNeural",
    "en-ZA-LukeNeural",
    # Philippine English
    "en-PH-JamesNeural",
    "en-PH-RosaNeural",
    # Nigerian English
    "en-NG-AbeoNeural",
    "en-NG-EzinneNeural",
    # Kenyan English
    "en-KE-AsiliaNeural",
    "en-KE-ChilembaNeural",
    # Hong Kong English
    "en-HK-SamNeural",
    "en-HK-YanNeural",
    # Tanzania English
    "en-TZ-ElimuNeural",
    "en-TZ-ImaniNeural",
]

# Speed rates to try per voice (simulates fast/slow speakers)
EDGE_RATES = ["-15%", "+0%", "+15%"]

# Distractor phrases for negative samples
DISTRACTORS = [
    "open the browser", "set a timer", "what time is it",
    "play some music", "close the window", "hey there", "hello",
    "hey jarvis", "alexa", "hey google", "ok google", "siri",
    "search for python tutorials", "take a screenshot",
    "turn off the lights", "send a message", "call mom",
    "navigate to home", "remind me", "open settings",
    "volume up", "volume down", "stop", "pause", "resume",
    "hey cortana", "hey alexa", "okay google", "computer",
    "assistant", "hey assistant", "hey there computer",
    "good morning", "good night", "what is the weather",
    "play a song", "read my messages", "start recording",
]


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _load_wav_as_float32(path: pathlib.Path) -> tuple["np.ndarray", int]:
    try:
        import soundfile as sf
        import numpy as np
        data, sr = sf.read(str(path), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        return data.astype(np.float32), sr
    except Exception:
        pass

    import numpy as np
    import array as _array
    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        sampwidth = wf.getsampwidth()
    if sampwidth == 2:
        raw = _array.array("h")
        raw.frombytes(frames)
        data = np.array(raw, dtype=np.float32) / 32768.0
    else:
        raw = _array.array("B", frames)
        data = (np.array(raw, dtype=np.float32) - 128.0) / 128.0
    return data, sr


def _resample(audio: "np.ndarray", orig_sr: int, target_sr: int) -> "np.ndarray":
    import numpy as np
    if orig_sr == target_sr:
        return audio
    n = int(len(audio) * target_sr / orig_sr)
    indices = np.linspace(0, len(audio) - 1, n)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


def _write_wav(path: pathlib.Path, samples: bytes, sr: int = SAMPLE_RATE) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples)


def _float32_to_wav_bytes(audio: "np.ndarray") -> bytes:
    import numpy as np
    samples = (audio * 32767).clip(-32768, 32767).astype(np.int16)
    return struct.pack(f"<{len(samples)}h", *samples)


def _augment_speed(audio: "np.ndarray", factor: float) -> "np.ndarray":
    """Time-stretch by resampling (changes speed and pitch together).
    factor < 1.0 = slower, factor > 1.0 = faster."""
    import numpy as np
    n_new = int(len(audio) / factor)
    if n_new <= 0:
        return audio
    indices = np.linspace(0, len(audio) - 1, n_new)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


# ---------------------------------------------------------------------------
# Step 0 — download openWakeWord feature-extractor models
# ---------------------------------------------------------------------------

def download_feature_extractors() -> tuple[pathlib.Path, pathlib.Path]:
    try:
        import openwakeword
    except ImportError:
        sys.exit("openwakeword is not installed.\n  pip install openwakeword")

    models_dir = pathlib.Path(openwakeword.__file__).parent / "resources" / "models"
    melspec = models_dir / "melspectrogram.onnx"
    embed = models_dir / "embedding_model.onnx"

    if not (melspec.exists() and embed.exists()):
        print("  Downloading openWakeWord feature-extractor models (~50 MB, one-time) ...")
        try:
            openwakeword.utils.download_models()
        except Exception as exc:
            print(f"  download_models() raised: {exc}")

    if not (melspec.exists() and embed.exists()):
        try:
            from openwakeword.model import Model
            Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        except Exception as exc:
            print(f"  Model() instantiation raised: {exc}")

    if not melspec.exists():
        sys.exit(f"melspectrogram.onnx not found in {models_dir}.")
    if not embed.exists():
        sys.exit(f"embedding_model.onnx not found in {models_dir}.")

    print(f"  Feature-extractor models ready: {models_dir}")
    return melspec, embed


# ---------------------------------------------------------------------------
# Step 1 — generate positive samples via Edge TTS (speaker-independent)
# ---------------------------------------------------------------------------

async def _edge_tts_generate(voice: str, phrase: str, rate: str, dest: pathlib.Path) -> bool:
    """Generate one TTS clip via Edge TTS. Returns True on success."""
    try:
        import edge_tts
        communicate = edge_tts.Communicate(phrase, voice, rate=rate)
        mp3_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_bytes += chunk["data"]
        if not mp3_bytes:
            return False
        # Try PyAV (av) decoder — standalone Python binding for libavcodec
        try:
            import av
            import io
            import numpy as np

            container = av.open(io.BytesIO(mp3_bytes))
            resampler = av.AudioResampler(format="flt", layout="mono", rate=SAMPLE_RATE)
            samples = []
            for frame in container.decode(audio=0):
                for rf in resampler.resample(frame):
                    samples.append(rf.to_ndarray())
            if samples:
                audio = np.concatenate(samples, axis=1).flatten().astype(np.float32)
                _write_wav(dest, _float32_to_wav_bytes(audio))
                return True
        except Exception:
            pass

        # Try pydub fallback
        try:
            from pydub import AudioSegment
            import io
            seg = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
            seg = seg.set_frame_rate(SAMPLE_RATE).set_channels(1).set_sample_width(2)
            seg.export(str(dest), format="wav")
            return True
        except Exception:
            pass

        return False

    except Exception:
        return False


async def _generate_all_edge_tts(pos_dir: pathlib.Path) -> list[pathlib.Path]:
    """Generate all Edge TTS samples. Returns list of created WAV paths."""
    import edge_tts

    paths: list[pathlib.Path] = []
    idx = 0
    total_voices = len(EDGE_TTS_VOICES)

    print(f"  Generating clips from {total_voices} diverse English voices × {len(EDGE_RATES)} speeds ...")

    for vi, voice in enumerate(EDGE_TTS_VOICES):
        for rate in EDGE_RATES:
            dest = pos_dir / f"edge_{idx:04d}.wav"
            ok = await _edge_tts_generate(voice, PHRASE, rate, dest)
            if ok and dest.exists() and dest.stat().st_size > 500:
                paths.append(dest)
                idx += 1
            else:
                # Clean up failed file
                if dest.exists():
                    dest.unlink()
        # Small progress every 10 voices
        if (vi + 1) % 10 == 0:
            print(f"    ... {vi + 1}/{total_voices} voices done, {idx} clips so far")

    print(f"  Edge TTS: {idx} clips generated from diverse voices.")
    return paths


def _generate_edge_tts_with_fallback(pos_dir: pathlib.Path) -> list[pathlib.Path]:
    """Synchronous wrapper for the async Edge TTS generation."""
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        print("  WARNING: edge-tts not installed — skipping diverse voice generation.")
        print("  Run: pip install edge-tts")
        return []

    # Check if pydub is available for mp3 decode
    has_pydub = False
    try:
        import pydub  # noqa: F401
        has_pydub = True
    except ImportError:
        pass

    if not has_pydub:
        print("  Installing pydub for mp3 decoding ...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pydub", "-q"],
            capture_output=True
        )
        try:
            import pydub  # noqa: F401
            has_pydub = True
        except ImportError:
            print("  pydub install failed — will try soundfile mp3 fallback.")

    return asyncio.run(_generate_all_edge_tts(pos_dir))


def _apply_augmentation(src_paths: list[pathlib.Path], pos_dir: pathlib.Path) -> list[pathlib.Path]:
    """Create augmented variants of each clip: volume × speed variations."""
    import numpy as np
    rng = random.Random(123)
    new_paths: list[pathlib.Path] = []
    aug_idx = 0

    speed_factors = [0.88, 0.94, 1.06, 1.12]   # slower and faster
    volume_scales = [0.7, 0.85]                  # quieter variants

    for src in src_paths:
        try:
            audio, sr = _load_wav_as_float32(src)
            audio = _resample(audio, sr, SAMPLE_RATE)
        except Exception:
            continue

        # Speed augmentations
        for factor in speed_factors:
            aug = _augment_speed(audio, factor)
            aug_clipped = aug.clip(-1.0, 1.0)
            dest = pos_dir / f"aug_spd_{aug_idx:05d}.wav"
            _write_wav(dest, _float32_to_wav_bytes(aug_clipped))
            new_paths.append(dest)
            aug_idx += 1

        # Volume augmentations (no speed change)
        for vol in volume_scales:
            aug = (audio * vol).clip(-1.0, 1.0)
            dest = pos_dir / f"aug_vol_{aug_idx:05d}.wav"
            _write_wav(dest, _float32_to_wav_bytes(aug))
            new_paths.append(dest)
            aug_idx += 1

    print(f"  Augmentation: {aug_idx} extra clips created (speed + volume variants).")
    return new_paths


def generate_positive_samples(
    out_dir: pathlib.Path,
    extra_clips: list[str],
) -> list[pathlib.Path]:
    pos_dir = out_dir / "positive"
    pos_dir.mkdir(parents=True, exist_ok=True)

    # 1. Edge TTS diverse voices (speaker-independent)
    edge_paths = _generate_edge_tts_with_fallback(pos_dir)

    # 2. SAPI5 fallback (Windows voices) for additional coverage
    sapi_paths: list[pathlib.Path] = []
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        rates = [130, 160, 190, 220]
        volumes = [0.85, 1.0]
        idx = 0
        for voice in voices:
            for rate in rates:
                for volume in volumes:
                    engine.setProperty("voice", voice.id)
                    engine.setProperty("rate", rate)
                    engine.setProperty("volume", volume)
                    dest = pos_dir / f"sapi_{idx:04d}.wav"
                    engine.save_to_file(PHRASE, str(dest))
                    sapi_paths.append(dest)
                    idx += 1
        engine.runAndWait()
        print(f"  SAPI5 fallback: {idx} additional clips.")
    except Exception:
        pass

    all_base = edge_paths + sapi_paths
    if not all_base:
        sys.exit(
            "No positive samples could be generated.\n"
            "Ensure edge-tts is installed:  pip install edge-tts"
        )

    # 3. Audio augmentation — more diversity from existing clips
    aug_paths = _apply_augmentation(all_base, pos_dir)

    # 4. Extra real-voice clips from --extra-clips
    real_paths: list[pathlib.Path] = []
    for clip in extra_clips:
        src = pathlib.Path(clip)
        if not src.is_file():
            print(f"  WARNING extra clip not found, skipping: {src}")
            continue
        dest = pos_dir / f"real_{src.name}"
        shutil.copy(src, dest)
        real_paths.append(dest)
        print(f"  Added real clip: {src.name}")

    all_paths = all_base + aug_paths + real_paths
    print(f"  Total positive clips: {len(all_paths)}")
    return all_paths


# ---------------------------------------------------------------------------
# Step 2 — generate negative samples
# ---------------------------------------------------------------------------

def generate_negative_samples(out_dir: pathlib.Path) -> list[pathlib.Path]:
    """Generate diverse negative training samples.

    Four categories:
    1. Near-silence (low-amplitude room noise)
    2. White / coloured / pink noise at varied amplitudes
    3. Distractor TTS phrases (Edge TTS diverse voices)
    4. SAPI5 distractor phrases (Windows voices)
    """
    import numpy as np
    rng = random.Random(42)

    neg_dir = out_dir / "negative"
    neg_dir.mkdir(parents=True, exist_ok=True)
    paths: list[pathlib.Path] = []
    dur = 2.0
    n_samp = int(SAMPLE_RATE * dur)

    # --- near-silence (35% of budget) ---
    n_silence = 350
    for i in range(n_silence):
        amp = rng.uniform(3, 25)
        raw = [max(-32768, min(32767, int(rng.gauss(0, amp)))) for _ in range(n_samp)]
        dest = neg_dir / f"silence_{i:04d}.wav"
        _write_wav(dest, struct.pack(f"<{n_samp}h", *raw))
        paths.append(dest)

    # --- white/coloured noise (40% of budget) ---
    n_noise = 450
    for i in range(n_noise):
        amp = rng.uniform(150, 4000)
        raw = [max(-32768, min(32767, int(rng.gauss(0, amp)))) for _ in range(n_samp)]
        dest = neg_dir / f"noise_{i:04d}.wav"
        _write_wav(dest, struct.pack(f"<{n_samp}h", *raw))
        paths.append(dest)

    # --- distractor phrases via Edge TTS (25% of budget) ---
    distractor_paths: list[pathlib.Path] = []
    try:
        import edge_tts  # noqa: F401
        # Use a subset of voices for distractors
        distractor_voices = EDGE_TTS_VOICES[::4]  # every 4th voice = ~12 voices
        distractor_idx = 0
        for phrase in DISTRACTORS:
            voice = distractor_voices[distractor_idx % len(distractor_voices)]
            dest = neg_dir / f"distractor_{distractor_idx:04d}.wav"
            ok = asyncio.run(_edge_tts_generate(voice, phrase, "+0%", dest))
            if ok and dest.exists() and dest.stat().st_size > 200:
                distractor_paths.append(dest)
            elif dest.exists():
                dest.unlink()
            distractor_idx += 1
        paths.extend(distractor_paths)
        print(f"  Distractor phrases: {len(distractor_paths)} clips.")
    except Exception as exc:
        print(f"  Edge TTS distractor generation skipped: {exc}")

    # --- SAPI5 distractor phrases ---
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        sapi_dist_idx = 0
        for voice in voices[:2]:
            for phrase in DISTRACTORS[:15]:
                engine.setProperty("voice", voice.id)
                dest = neg_dir / f"sapi_dist_{sapi_dist_idx:04d}.wav"
                engine.save_to_file(phrase, str(dest))
                paths.append(dest)
                sapi_dist_idx += 1
        engine.runAndWait()
    except Exception:
        pass

    print(f"  Total negative clips: {len(paths)}")
    return paths


# ---------------------------------------------------------------------------
# Step 3 — extract speech-embedding features
# ---------------------------------------------------------------------------

def extract_features(
    paths: list[pathlib.Path],
    melspec_sess,
    embed_sess,
) -> "np.ndarray":
    import numpy as np

    chunk = 1280
    mel_in_name  = melspec_sess.get_inputs()[0].name
    emb_in_name  = embed_sess.get_inputs()[0].name
    emb_in_shape = embed_sess.get_inputs()[0].shape
    n_frames_needed = int(emb_in_shape[1])
    n_mel_bins      = int(emb_in_shape[2])

    feats: list[np.ndarray] = []

    for path in paths:
        try:
            audio, sr = _load_wav_as_float32(path)
        except Exception as exc:
            print(f"  WARNING could not load {path.name}: {exc}")
            continue
        audio = _resample(audio, sr, SAMPLE_RATE)

        mel_frames: list[np.ndarray] = []
        for start in range(0, len(audio), chunk):
            seg = audio[start : start + chunk]
            if len(seg) < chunk:
                seg = np.pad(seg, (0, chunk - len(seg)))
            mel_raw = melspec_sess.run(None, {mel_in_name: seg.reshape(1, chunk)})[0]
            mel_flat = mel_raw.flatten().astype(np.float32)
            n_frames_chunk = mel_flat.size // n_mel_bins
            for fi in range(n_frames_chunk):
                frame = mel_flat[fi * n_mel_bins : (fi + 1) * n_mel_bins].copy()
                mel_frames.append(frame)

        if len(mel_frames) < n_frames_needed:
            shortage = n_frames_needed - len(mel_frames) + 1
            for _ in range(shortage):
                mel_frames.append(np.zeros(n_mel_bins, dtype=np.float32))

        mel_arr = np.array(mel_frames, dtype=np.float32)
        step = max(1, n_frames_needed // 2)
        for i in range(0, len(mel_arr) - n_frames_needed + 1, step):
            window = mel_arr[i : i + n_frames_needed]
            inp = window.reshape(1, n_frames_needed, n_mel_bins, 1)
            emb = embed_sess.run(None, {emb_in_name: inp})[0].flatten()
            feats.append(emb)

    if not feats:
        sys.exit("No features could be extracted — check that audio files are valid WAV.")

    return np.array(feats, dtype=np.float32)


# ---------------------------------------------------------------------------
# Step 4 — train classifier + export ONNX
# ---------------------------------------------------------------------------

def train_and_export(
    pos_paths: list[pathlib.Path],
    neg_paths: list[pathlib.Path],
    melspec_path: pathlib.Path,
    embed_path: pathlib.Path,
    out_model: pathlib.Path,
) -> None:
    try:
        import numpy as np
        import onnxruntime as ort
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        sys.exit(f"Missing training dependency: {exc}\n  pip install numpy onnxruntime scikit-learn")

    melspec_sess = ort.InferenceSession(str(melspec_path))
    embed_sess = ort.InferenceSession(str(embed_path))

    print("  Extracting positive features ...")
    X_pos = extract_features(pos_paths, melspec_sess, embed_sess)
    print("  Extracting negative features ...")
    X_neg = extract_features(neg_paths, melspec_sess, embed_sess)

    X = np.vstack([X_pos, X_neg])
    y = np.concatenate([np.ones(len(X_pos)), np.zeros(len(X_neg))])

    scaler = StandardScaler()
    X_s = scaler.fit_transform(X)

    print(f"  Training logistic regression ({len(X_pos)} pos, {len(X_neg)} neg features) ...")
    clf = LogisticRegression(max_iter=2000, C=0.5, class_weight="balanced")
    clf.fit(X_s, y)
    acc = clf.score(X_s, y)
    print(f"  Training accuracy: {acc:.1%}")

    out_model.parent.mkdir(parents=True, exist_ok=True)
    _export_onnx(clf, scaler, X.shape[1], out_model)


def _export_onnx(clf, scaler, n_features: int, out_model: pathlib.Path) -> None:
    try:
        import numpy as np
        import onnx
        from onnx import TensorProto, helper
    except ImportError:
        sys.exit("Cannot export ONNX model — install onnx:\n  pip install onnx")

    N_FRAMES = 16

    w = clf.coef_[0].astype(np.float32)
    b = float(clf.intercept_[0])
    mean = scaler.mean_.astype(np.float32)
    scale = scaler.scale_.astype(np.float32)

    w_eff = (w / scale).astype(np.float32)
    b_eff = float(b - float(np.dot(w / scale, mean)))

    X_in    = helper.make_tensor_value_info("input",  TensorProto.FLOAT, [None, N_FRAMES, n_features])
    prob_out = helper.make_tensor_value_info("output", TensorProto.FLOAT, [None, 1])

    shape_flat = helper.make_tensor("shape_flat", TensorProto.INT64, [2], [-1, n_features])
    node_flat  = helper.make_node("Reshape", ["input", "shape_flat"], ["flat"])

    W_init  = helper.make_tensor("W", TensorProto.FLOAT, [1, n_features], w_eff.tolist())
    B_init  = helper.make_tensor("B", TensorProto.FLOAT, [1], [b_eff])
    node_mm = helper.make_node("Gemm", ["flat", "W", "B"], ["logit"],
                                alpha=1.0, beta=1.0, transB=1)

    shape_3d  = helper.make_tensor("shape_3d", TensorProto.INT64, [3], [-1, N_FRAMES, 1])
    node_3d   = helper.make_node("Reshape", ["logit", "shape_3d"], ["logit_3d"])

    # ReduceMean: wake word must score consistently across the whole window,
    # not just spike in one frame (ReduceMax caused confidence=1.0 on ambient audio).
    node_max = helper.make_node("ReduceMean", ["logit_3d"], ["max_logit"],
                                 axes=[1], keepdims=0)

    node_sig = helper.make_node("Sigmoid", ["max_logit"], ["output"])

    graph = helper.make_graph(
        [node_flat, node_mm, node_3d, node_max, node_sig],
        "hey_veyra",
        [X_in], [prob_out],
        [shape_flat, W_init, B_init, shape_3d],
    )
    try:
        onnx_model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
        onnx.checker.check_model(onnx_model)
    except Exception as exc:
        sys.exit(f"ONNX graph validation failed: {exc}")

    out_model.parent.mkdir(parents=True, exist_ok=True)
    with open(str(out_model), "wb") as f:
        f.write(onnx_model.SerializeToString())
    print(f"  Exported ONNX model: {out_model}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(DEFAULT_OUT_MODEL),
                        help="Output .onnx path (default: models/hey_veyra.onnx).")
    parser.add_argument("--extra-clips", nargs="*", default=[], metavar="WAV",
                        help="Real recordings of 'Hey VEYRA' to mix in as positive samples.")
    parser.add_argument("--extra-negative-clips", nargs="*", default=[], metavar="WAV",
                        help="Real background-noise WAV clips to add as negative samples.")
    args = parser.parse_args()

    out_model = pathlib.Path(args.out).expanduser().resolve()
    print("=== Hey VEYRA wake-word training (speaker-independent) ===")
    print(f"Output model: {out_model}")
    print(f"Positive voices: {len(EDGE_TTS_VOICES)} diverse English accents × {len(EDGE_RATES)} speeds + augmentation")
    print()

    print("Step 0/4 — checking feature-extractor models ...")
    melspec_path, embed_path = download_feature_extractors()

    print("\nStep 1/4 — generating diverse positive samples ...")
    with tempfile.TemporaryDirectory(prefix="veyra_ww_") as tmp:
        tmp_path = pathlib.Path(tmp)
        pos = generate_positive_samples(tmp_path, args.extra_clips)

        print("\nStep 2/4 — generating negative samples ...")
        neg = generate_negative_samples(tmp_path)
        for clip in (args.extra_negative_clips or []):
            p = pathlib.Path(clip)
            if p.is_file():
                neg.append(p)

        print("\nStep 3/4 — extracting features ...")
        print("Step 4/4 — training + exporting ...")
        train_and_export(pos, neg, melspec_path, embed_path, out_model)

    if out_model.exists():
        print(f"\nDone!  Model saved to: {out_model}")
        print("\nPaste this into your .env file:")
        print(f"  VEYRA_WAKE_WORD_MODEL={out_model}")
        print("  VEYRA_WAKE_WORD_THRESHOLD=0.55")
        print("\nRestart VEYRA — anyone can now say 'Hey VEYRA' to activate it.")
    else:
        print("\nERROR: model file was not created. See output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
