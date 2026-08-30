#!/usr/bin/env python3
"""Train a custom "Hey VEYRA" openWakeWord model.

Run this ONCE on your Windows machine after installing the voice extras:

    pip install -e "services/voice[wake-word,audio]"
    pip install pyttsx3 soundfile onnxruntime scikit-learn skl2onnx

Then:

    python scripts/train_hey_veyra_wakeword.py

What it does:
  1. Downloads openWakeWord's feature-extractor models (~50 MB, one-time).
  2. Generates synthetic "Hey VEYRA" audio clips using Windows SAPI5 TTS.
  3. Generates synthetic background-noise clips as negative training data.
  4. Extracts speech-embedding features using openWakeWord's own pipeline.
  5. Trains a logistic-regression classifier and exports it as .onnx.
  6. Saves the model to  models/hey_veyra.onnx  next to this repo root.
  7. Prints the exact line to paste into your .env file.

No PyTorch required. No microphone required. No API key required.

Optional: supply real recordings of your voice saying "Hey VEYRA" with
--extra-clips to improve accuracy beyond the synthetic baseline.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import struct
import sys
import tempfile
import wave

PHRASE = "Hey VEYRA"
SAMPLE_RATE = 16000
N_POSITIVE_TARGET = 200  # synthetic-only; good enough for a working model
REPO_ROOT = pathlib.Path(__file__).parent.parent
DEFAULT_OUT_MODEL = REPO_ROOT / "models" / "hey_veyra.onnx"


# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------

def _load_wav_as_float32(path: pathlib.Path) -> tuple["np.ndarray", int]:
    """Load a WAV file as float32 in [-1, 1] and return (samples, sample_rate)."""
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


# ---------------------------------------------------------------------------
# Step 0 — download openWakeWord feature-extractor models
# ---------------------------------------------------------------------------

def download_feature_extractors() -> tuple[pathlib.Path, pathlib.Path]:
    """Return (melspectrogram.onnx, embedding_model.onnx), downloading if needed."""
    try:
        import openwakeword
    except ImportError:
        sys.exit(
            "openwakeword is not installed.\n"
            "  pip install openwakeword"
        )

    models_dir = pathlib.Path(openwakeword.__file__).parent / "resources" / "models"
    melspec = models_dir / "melspectrogram.onnx"
    embed = models_dir / "embedding_model.onnx"

    if not (melspec.exists() and embed.exists()):
        print("  Downloading openWakeWord feature-extractor models (~50 MB, one-time) ...")
        try:
            openwakeword.utils.download_models()
        except Exception as exc:
            print(f"  download_models() raised: {exc}")

    # Second attempt: trigger implicit download by instantiating a Model
    if not (melspec.exists() and embed.exists()):
        try:
            from openwakeword.model import Model
            Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        except Exception as exc:
            print(f"  Model() instantiation raised: {exc}")

    if not melspec.exists():
        sys.exit(
            f"melspectrogram.onnx not found in {models_dir}.\n"
            "Run:  python -c \"import openwakeword; openwakeword.utils.download_models()\"\n"
            "then re-run this script."
        )
    if not embed.exists():
        sys.exit(
            f"embedding_model.onnx not found in {models_dir}.\n"
            "Run:  python -c \"import openwakeword; openwakeword.utils.download_models()\"\n"
            "then re-run this script."
        )

    print(f"  Feature-extractor models ready: {models_dir}")
    return melspec, embed


# ---------------------------------------------------------------------------
# Step 1 — generate synthetic positive samples
# ---------------------------------------------------------------------------

def generate_positive_samples(out_dir: pathlib.Path, extra_clips: list[str]) -> list[pathlib.Path]:
    try:
        import pyttsx3
    except ImportError:
        sys.exit(
            "pyttsx3 is not installed.\n"
            "  pip install pyttsx3"
        )

    pos_dir = out_dir / "positive"
    pos_dir.mkdir(parents=True, exist_ok=True)

    engine = pyttsx3.init()
    voices = engine.getProperty("voices") or []
    if not voices:
        sys.exit("No SAPI5 voices found — this script must run on Windows.")

    rates = [130, 150, 165, 180, 200, 215, 230]
    volumes = [0.8, 0.9, 1.0]

    paths: list[pathlib.Path] = []
    idx = 0
    for voice in voices:
        for rate in rates:
            for volume in volumes:
                if idx >= N_POSITIVE_TARGET:
                    break
                engine.setProperty("voice", voice.id)
                engine.setProperty("rate", rate)
                engine.setProperty("volume", volume)
                dest = pos_dir / f"synth_{idx:04d}.wav"
                engine.save_to_file(PHRASE, str(dest))
                paths.append(dest)
                idx += 1
            if idx >= N_POSITIVE_TARGET:
                break
        if idx >= N_POSITIVE_TARGET:
            break

    engine.runAndWait()
    print(f"  Synthesized {idx} positive clips.")

    for clip in extra_clips:
        src = pathlib.Path(clip)
        if not src.is_file():
            print(f"  WARNING extra clip not found, skipping: {src}")
            continue
        dest = pos_dir / f"real_{src.name}"
        shutil.copy(src, dest)
        paths.append(dest)
        print(f"  Added real clip: {src.name}")

    return paths


# ---------------------------------------------------------------------------
# Step 2 — generate synthetic negative samples
# ---------------------------------------------------------------------------

def generate_negative_samples(out_dir: pathlib.Path) -> list[pathlib.Path]:
    import random, struct as _struct
    import numpy as np

    neg_dir = out_dir / "negative"
    neg_dir.mkdir(parents=True, exist_ok=True)

    paths: list[pathlib.Path] = []
    rng = random.Random(42)
    n_noise = 200
    dur = 2.0
    n_samp = int(SAMPLE_RATE * dur)

    for i in range(n_noise):
        amp = rng.uniform(0, 600)
        raw = [max(-32768, min(32767, int(rng.gauss(0, amp)))) for _ in range(n_samp)]
        dest = neg_dir / f"noise_{i:04d}.wav"
        _write_wav(dest, _struct.pack(f"<{n_samp}h", *raw))
        paths.append(dest)

    # Distractor phrases (non-wake speech)
    try:
        import pyttsx3
        engine = pyttsx3.init()
        distractors = [
            "open the browser", "set a timer", "what time is it",
            "play some music", "close the window", "hey there", "hello",
            "jarvis", "search for python tutorials", "take a screenshot",
        ]
        for j, phrase in enumerate(distractors):
            dest = neg_dir / f"distractor_{j:04d}.wav"
            engine.save_to_file(phrase, str(dest))
            paths.append(dest)
        engine.runAndWait()
    except Exception:
        pass

    print(f"  Generated {len(paths)} negative/background clips.")
    return paths


# ---------------------------------------------------------------------------
# Step 3 — extract speech-embedding features via openWakeWord's own pipeline
# ---------------------------------------------------------------------------

def extract_features(
    paths: list[pathlib.Path],
    melspec_sess,
    embed_sess,
) -> "np.ndarray":
    """Extract speech-embedding feature vectors from a list of WAV files.

    openWakeWord's pipeline:
      audio (1280 samples / 80 ms) → melspectrogram.onnx → [n_mel_frames, 32]
      stack 76 consecutive mel frames → embedding_model.onnx → [96] embedding

    The embedding model expects [batch, 76, 32, 1], so we collect mel frames
    across chunks and feed sliding 76-frame windows.
    """
    import numpy as np

    chunk = 1280  # 80 ms at 16 kHz

    mel_in_name  = melspec_sess.get_inputs()[0].name
    emb_in_name  = embed_sess.get_inputs()[0].name
    emb_in_shape = embed_sess.get_inputs()[0].shape  # e.g. [None, 76, 32, 1]
    n_frames_needed = int(emb_in_shape[1])           # 76
    n_mel_bins      = int(emb_in_shape[2])           # 32

    feats: list[np.ndarray] = []

    for path in paths:
        try:
            audio, sr = _load_wav_as_float32(path)
        except Exception as exc:
            print(f"  WARNING could not load {path.name}: {exc}")
            continue
        audio = _resample(audio, sr, SAMPLE_RATE)

        # 1. Collect all mel frames for this file
        mel_frames: list[np.ndarray] = []
        for start in range(0, len(audio), chunk):
            seg = audio[start : start + chunk]
            if len(seg) < chunk:
                seg = np.pad(seg, (0, chunk - len(seg)))
            mel = melspec_sess.run(None, {mel_in_name: seg.reshape(1, chunk)})[0]
            # mel shape: [1, frames_per_chunk, 32]  (e.g. [1, 5, 32])
            for frame in mel.squeeze(0):            # each frame is [32]
                mel_frames.append(frame)

        if len(mel_frames) < n_frames_needed:
            continue  # clip too short — skip

        # 2. Sliding windows of n_frames_needed, 50 % overlap
        mel_arr = np.array(mel_frames, dtype=np.float32)  # [total, 32]
        step = max(1, n_frames_needed // 2)
        for i in range(0, len(mel_arr) - n_frames_needed + 1, step):
            window = mel_arr[i : i + n_frames_needed]        # [76, 32]
            inp = window.reshape(1, n_frames_needed, n_mel_bins, 1)  # [1,76,32,1]
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
        sys.exit(
            f"Missing training dependency: {exc}\n"
            "  pip install numpy onnxruntime scikit-learn skl2onnx"
        )

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
    clf = LogisticRegression(max_iter=1000, C=1.0)
    clf.fit(X_s, y)
    acc = clf.score(X_s, y)
    print(f"  Training accuracy: {acc:.1%}")

    out_model.parent.mkdir(parents=True, exist_ok=True)
    _export_onnx(clf, scaler, X.shape[1], out_model)


def _export_onnx(clf, scaler, n_features: int, out_model: pathlib.Path) -> None:
    # Try skl2onnx first (cleanest)
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
        from sklearn.pipeline import Pipeline

        pipe = Pipeline([("scaler", scaler), ("clf", clf)])
        onnx_model = convert_sklearn(
            pipe, initial_types=[("float_input", FloatTensorType([None, n_features]))]
        )
        with open(str(out_model), "wb") as f:
            f.write(onnx_model.SerializeToString())
        print(f"  Exported via skl2onnx: {out_model}")
        return
    except ImportError:
        pass
    except Exception as exc:
        print(f"  skl2onnx export failed ({exc}), trying raw onnx ...")

    # Fallback: build a minimal ONNX graph manually
    try:
        import numpy as np
        import onnx
        from onnx import TensorProto, helper

        w = clf.coef_[0].astype(np.float32)
        b = float(clf.intercept_[0])
        mean = scaler.mean_.astype(np.float32)
        scale = scaler.scale_.astype(np.float32)
        # Bake standardisation into the weights
        w_eff = (w / scale).astype(np.float32)
        b_eff = float(b - float(np.dot(w / scale, mean)))

        X_in = helper.make_tensor_value_info("input", TensorProto.FLOAT, [None, n_features])
        prob_out = helper.make_tensor_value_info("prob", TensorProto.FLOAT, [None, 1])
        W_init = helper.make_tensor("W", TensorProto.FLOAT, [1, n_features], w_eff.tolist())
        B_init = helper.make_tensor("B", TensorProto.FLOAT, [1], [b_eff])
        gemm = helper.make_node("Gemm", ["input", "W", "B"], ["logit"],
                                alpha=1.0, beta=1.0, transB=1)
        sig = helper.make_node("Sigmoid", ["logit"], ["prob"])
        graph = helper.make_graph([gemm, sig], "hey_veyra", [X_in], [prob_out], [W_init, B_init])
        model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
        onnx.checker.check_model(model)
        with open(str(out_model), "wb") as f:
            f.write(model.SerializeToString())
        print(f"  Exported via raw onnx: {out_model}")
    except ImportError:
        sys.exit(
            "Cannot export ONNX model — install skl2onnx or onnx:\n"
            "  pip install skl2onnx\n"
            "then re-run."
        )
    except Exception as exc:
        sys.exit(f"ONNX export failed: {exc}")


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
    print("=== Hey VEYRA wake-word training ===")
    print(f"Output model: {out_model}\n")

    print("Step 0/4 — checking feature-extractor models ...")
    melspec_path, embed_path = download_feature_extractors()

    print("\nStep 1/4 — generating synthetic positive samples ...")
    with tempfile.TemporaryDirectory(prefix="veyra_ww_") as tmp:
        tmp_path = pathlib.Path(tmp)
        pos = generate_positive_samples(tmp_path, args.extra_clips)

        print("\nStep 2/4 — generating synthetic negative samples ...")
        neg = generate_negative_samples(tmp_path)
        for clip in (args.extra_negative_clips or []):
            p = pathlib.Path(clip)
            if p.is_file():
                neg.append(p)

        print("\nStep 3/4 — extracting features ...")
        print("\nStep 4/4 — training + exporting ...")
        train_and_export(pos, neg, melspec_path, embed_path, out_model)

    if out_model.exists():
        print(f"\nDone!  Model saved to: {out_model}")
        print("\nPaste this into your .env file:")
        print(f"  VEYRA_WAKE_WORD_MODEL={out_model}")
        print("\nRestart VEYRA — it will load 'Hey VEYRA' automatically.")
    else:
        print("\nERROR: model file was not created. See output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
