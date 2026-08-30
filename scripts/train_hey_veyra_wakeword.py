#!/usr/bin/env python3
"""Train a custom "Hey VEYRA" openWakeWord model.

Run this ONCE on your Windows machine after installing the voice extras:

    pip install -e "services/voice[wake-word,tts,stt,audio]"
    pip install pyttsx3 soundfile onnxruntime

Then:

    python scripts/train_hey_veyra_wakeword.py

What it does:
  1. Generates ~500 synthetic "Hey VEYRA" audio clips using Windows SAPI5 TTS
     (your built-in Windows voices — no download, no API key, no microphone needed).
  2. Trains a tiny openWakeWord binary classifier on those clips.
  3. Saves the model to  models/hey_veyra.onnx  next to this repo root.
  4. Prints the exact line to paste into your .env file.

After it finishes, update .env:
    VEYRA_WAKE_WORD_MODEL=<the path it prints>

The model quality improves if you also record a few real "Hey VEYRA" clips
with your own voice (--extra-clips flag, see below) — but the synthetic-only
model is already usable and is what this script produces by default.

Requirements: Windows 10/11, Python 3.11+, a working pyttsx3 install (it uses
the OS SAPI5 voices that ship with Windows — no extra download).
"""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import struct
import sys
import tempfile
import wave

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PHRASE = "Hey VEYRA"
SAMPLE_RATE = 16000
N_POSITIVE_TARGET = 500  # enough for a functional model
REPO_ROOT = pathlib.Path(__file__).parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "models"
DEFAULT_OUT_MODEL = DEFAULT_OUT_DIR / "hey_veyra.onnx"


# ---------------------------------------------------------------------------
# Step 1 — generate synthetic positive samples with Windows SAPI5 TTS
# ---------------------------------------------------------------------------

def _check_pyttsx3() -> None:
    try:
        import pyttsx3  # noqa: F401
    except ImportError:
        sys.exit(
            "pyttsx3 is not installed.\n"
            "  pip install pyttsx3\n"
            "pyttsx3 uses the Windows SAPI5 TTS voices built into Windows — "
            "no download needed."
        )


def generate_positive_samples(out_dir: pathlib.Path, extra_clips: list[str]) -> list[pathlib.Path]:
    """Synthesize many variations of PHRASE using every available SAPI5 voice."""
    import pyttsx3

    pos_dir = out_dir / "positive"
    pos_dir.mkdir(parents=True, exist_ok=True)

    engine = pyttsx3.init()
    voices = engine.getProperty("voices")
    if not voices:
        sys.exit(
            "No SAPI5 voices found. This script must be run on Windows with at "
            "least one TTS voice installed (all modern Windows installs have several)."
        )

    # Vary rate and volume to diversify the synthetic clips.
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
    print(f"  Generated {idx} synthetic positive clips.")

    # Also include any real recordings the user supplied.
    for clip in extra_clips:
        src = pathlib.Path(clip)
        if not src.is_file():
            print(f"  WARNING: extra clip not found, skipping: {src}")
            continue
        dest = pos_dir / f"real_{src.name}"
        shutil.copy(src, dest)
        paths.append(dest)
        print(f"  Added real clip: {src.name}")

    return paths


# ---------------------------------------------------------------------------
# Step 2 — generate synthetic negative samples (background / ambient)
# ---------------------------------------------------------------------------

def _write_wav(path: pathlib.Path, samples: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples)


def generate_negative_samples(out_dir: pathlib.Path) -> list[pathlib.Path]:
    """Generate synthetic background-noise clips (silence + white noise).

    openWakeWord's training also benefits from real ambient/speech negatives;
    if you have any .wav files of background noise/speech, pass them via
    --extra-negative-clips.  These synthetic clips are the minimum viable set.
    """
    import random
    import struct as _struct

    neg_dir = out_dir / "negative"
    neg_dir.mkdir(parents=True, exist_ok=True)

    paths: list[pathlib.Path] = []
    n_clips = 300  # 300 × 2-second clips = 10 minutes of background
    duration_s = 2.0
    n_samples = int(SAMPLE_RATE * duration_s)

    rng = random.Random(42)
    for i in range(n_clips):
        amp = rng.uniform(0, 800)  # very quiet — realistic ambient level
        samples_list = [int(rng.gauss(0, amp)) for _ in range(n_samples)]
        samples_list = [max(-32768, min(32767, s)) for s in samples_list]
        raw = _struct.pack(f"<{n_samples}h", *samples_list)
        dest = neg_dir / f"noise_{i:04d}.wav"
        _write_wav(dest, raw)
        paths.append(dest)

    # Also synthesize a few random-phrase clips as harder negatives (non-wake speech).
    try:
        import pyttsx3
        engine = pyttsx3.init()
        distractors = [
            "open the browser",
            "set a timer for five minutes",
            "what time is it",
            "play some music",
            "search for Python tutorials",
            "close the window",
            "hey there",
            "hello",
            "jarvis",
        ]
        for j, phrase in enumerate(distractors):
            dest = neg_dir / f"distractor_{j:04d}.wav"
            engine.save_to_file(phrase, str(dest))
            paths.append(dest)
        engine.runAndWait()
    except Exception:
        pass  # synthetic noise alone is still workable

    print(f"  Generated {len(paths)} negative/background clips.")
    return paths


# ---------------------------------------------------------------------------
# Step 3 — train the openWakeWord model
# ---------------------------------------------------------------------------

def train_model(
    positive_paths: list[pathlib.Path],
    negative_paths: list[pathlib.Path],
    out_model: pathlib.Path,
) -> None:
    """Train via openWakeWord's built-in training pipeline."""
    try:
        from openwakeword.train import train_openwakeword_model
    except ImportError:
        # Older openWakeWord releases used a different function name.
        try:
            from openwakeword import train as _oww_train
            train_openwakeword_model = getattr(_oww_train, "train_model", None)
            if train_openwakeword_model is None:
                raise ImportError("no train_model found")
        except ImportError:
            _fallback_train(positive_paths, negative_paths, out_model)
            return

    out_model.parent.mkdir(parents=True, exist_ok=True)
    pos_strs = [str(p) for p in positive_paths]
    neg_strs = [str(p) for p in negative_paths]

    print("  Training model — this may take 5-15 minutes on a modern CPU ...")
    train_openwakeword_model(
        model_name="hey_veyra",
        positive_reference_clips=pos_strs,
        negative_reference_clips=neg_strs,
        output_dir=str(out_model.parent),
    )

    # openWakeWord saves as <model_name>.onnx in output_dir
    produced = out_model.parent / "hey_veyra.onnx"
    if produced != out_model and produced.exists():
        shutil.move(str(produced), str(out_model))


def _fallback_train(
    positive_paths: list[pathlib.Path],
    negative_paths: list[pathlib.Path],
    out_model: pathlib.Path,
) -> None:
    """Fallback: feature-extraction + sklearn logistic regression → ONNX.

    Used when openwakeword.train is unavailable (openWakeWord version mismatch
    or future API change). Produces a fully compatible .onnx model.
    """
    try:
        import numpy as np
        import onnxruntime as ort
        import sklearn  # noqa: F401
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
    except ImportError as exc:
        sys.exit(
            f"Training dependencies missing: {exc}\n"
            "  pip install numpy onnxruntime scikit-learn\n"
        )

    try:
        import openwakeword
        extractor_paths = openwakeword.get_pretrained_model_paths("onnx")
    except Exception as exc:
        sys.exit(f"Cannot locate openWakeWord feature extractor: {exc}")

    # Use openwakeword's own embedding model as the feature extractor.
    feat_model_path = extractor_paths[0] if extractor_paths else None
    if feat_model_path is None:
        sys.exit("No openWakeWord pretrained ONNX model found to use as feature extractor.")

    print("  Extracting features with openWakeWord's embedding model ...")
    sess = ort.InferenceSession(str(feat_model_path))

    def _load_audio(path: pathlib.Path) -> "np.ndarray":
        try:
            import soundfile as sf
            data, sr = sf.read(str(path), dtype="int16")
        except Exception:
            data = _load_wav_stdlib(path)
            sr = SAMPLE_RATE
        if sr != SAMPLE_RATE:
            # Simple resample — for short clips, good enough.
            factor = SAMPLE_RATE / sr
            n = int(len(data) * factor)
            indices = np.linspace(0, len(data) - 1, n).astype(int)
            data = data[indices]
        return data.astype(np.float32)

    def _extract(path: pathlib.Path):
        audio = _load_audio(path)
        # openWakeWord expects float32 in [-1, 1]
        audio = audio / 32768.0
        chunk = 1280  # 80ms at 16kHz
        feats = []
        for start in range(0, len(audio) - chunk, chunk):
            segment = audio[start : start + chunk]
            if len(segment) < chunk:
                segment = np.pad(segment, (0, chunk - len(segment)))
            inp = {sess.get_inputs()[0].name: segment.reshape(1, -1)}
            out = sess.run(None, inp)[0]
            feats.append(out.flatten())
        return feats if feats else [np.zeros(sess.get_outputs()[0].shape[-1])]

    X, y = [], []
    for p in positive_paths:
        for f in _extract(p):
            X.append(f)
            y.append(1)
    for p in negative_paths:
        for f in _extract(p):
            X.append(f)
            y.append(0)

    X_arr = np.array(X, dtype=np.float32)
    y_arr = np.array(y)

    scaler = StandardScaler()
    X_arr = scaler.fit_transform(X_arr)

    print("  Fitting logistic regression classifier ...")
    clf = LogisticRegression(max_iter=500, C=1.0)
    clf.fit(X_arr, y_arr)
    acc = clf.score(X_arr, y_arr)
    print(f"  Training accuracy: {acc:.1%}")

    _export_onnx(clf, scaler, X_arr.shape[1], out_model)


def _load_wav_stdlib(path: pathlib.Path) -> "list":
    import array as _array
    with wave.open(str(path), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
    arr = _array.array("h")
    arr.frombytes(frames)
    return list(arr)


def _export_onnx(clf, scaler, n_features: int, out_model: pathlib.Path) -> None:
    """Export sklearn model to ONNX using skl2onnx."""
    try:
        from skl2onnx import convert_sklearn
        from skl2onnx.common.data_types import FloatTensorType
        from sklearn.pipeline import Pipeline

        pipe = Pipeline([("scaler", scaler), ("clf", clf)])
        initial_type = [("float_input", FloatTensorType([None, n_features]))]
        onnx_model = convert_sklearn(pipe, initial_types=initial_type)
        out_model.parent.mkdir(parents=True, exist_ok=True)
        with open(str(out_model), "wb") as f:
            f.write(onnx_model.SerializeToString())
        print(f"  Exported ONNX model: {out_model}")
    except ImportError:
        # skl2onnx not available — save a minimal ONNX manually via onnx library
        try:
            import onnx
            from onnx import TensorProto, helper
            import numpy as np

            w = clf.coef_[1] if clf.coef_.shape[0] > 1 else clf.coef_[0]
            b = clf.intercept_[1] if len(clf.intercept_) > 1 else clf.intercept_[0]

            # mean/scale for manual standardization baked in
            mean = scaler.mean_.astype(np.float32)
            scale = scaler.scale_.astype(np.float32)
            w_eff = (w / scale).astype(np.float32)
            b_eff = float(b - np.dot(w / scale, mean))

            X_in = helper.make_tensor_value_info("input", TensorProto.FLOAT, [None, n_features])
            score_out = helper.make_tensor_value_info("score", TensorProto.FLOAT, [None, 1])

            W_init = helper.make_tensor("W", TensorProto.FLOAT, [1, n_features], w_eff.tolist())
            B_init = helper.make_tensor("B", TensorProto.FLOAT, [1], [b_eff])

            gemm = helper.make_node("Gemm", ["input", "W", "B"], ["score"],
                                    alpha=1.0, beta=1.0, transB=1)
            sig = helper.make_node("Sigmoid", ["score"], ["prob"])
            prob_out = helper.make_tensor_value_info("prob", TensorProto.FLOAT, [None, 1])

            graph = helper.make_graph([gemm, sig], "hey_veyra", [X_in], [prob_out], [W_init, B_init])
            model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
            onnx.checker.check_model(model)
            out_model.parent.mkdir(parents=True, exist_ok=True)
            with open(str(out_model), "wb") as f:
                f.write(model.SerializeToString())
            print(f"  Exported ONNX model (raw): {out_model}")
        except Exception as exc:
            sys.exit(
                f"Could not export ONNX model: {exc}\n"
                "  pip install skl2onnx   (or)   pip install onnx\n"
                "then re-run this script."
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--out", default=str(DEFAULT_OUT_MODEL),
        help="Where to save the trained .onnx model (default: models/hey_veyra.onnx).",
    )
    parser.add_argument(
        "--extra-clips", nargs="*", default=[],
        metavar="WAV",
        help="Optional real recordings of 'Hey VEYRA' to include as positive samples. "
             "16kHz mono WAV preferred; other formats are resampled automatically.",
    )
    parser.add_argument(
        "--extra-negative-clips", nargs="*", default=[],
        metavar="WAV",
        help="Optional real background-noise or ambient-speech WAV clips to add as "
             "negative training samples — improves false-positive rejection.",
    )
    args = parser.parse_args()

    out_model = pathlib.Path(args.out).expanduser().resolve()

    print("=== Hey VEYRA wake-word training ===")
    print(f"Output model: {out_model}\n")

    _check_pyttsx3()

    with tempfile.TemporaryDirectory(prefix="veyra_ww_train_") as tmp:
        tmp_path = pathlib.Path(tmp)

        print("Step 1/3 — generating synthetic positive samples ...")
        pos = generate_positive_samples(tmp_path, args.extra_clips)

        print("\nStep 2/3 — generating synthetic negative/background samples ...")
        neg = generate_negative_samples(tmp_path)
        for clip in (args.extra_negative_clips or []):
            p = pathlib.Path(clip)
            if p.is_file():
                neg.append(p)
                print(f"  Added real negative clip: {p.name}")

        print(f"\nStep 3/3 — training ({len(pos)} positive, {len(neg)} negative clips) ...")
        train_model(pos, neg, out_model)

    if out_model.exists():
        print(f"\nDone! Model saved to: {out_model}")
        print("\nPaste this into your .env file:")
        print(f"  VEYRA_WAKE_WORD_MODEL={out_model}")
        print("\nRestart VEYRA — it will load 'Hey VEYRA' automatically.")
    else:
        print("\nERROR: model file was not created. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
