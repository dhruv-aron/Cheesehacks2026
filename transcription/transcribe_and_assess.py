#!/usr/bin/env python3
"""
Live mic transcription using Whisper (good model for M4 Mac) + Gemini threat assessment.
Context: transcription is from a police stop; Gemini assesses threat level.
Prints transcript live in the terminal as you speak.
"""

import argparse
import os
import sys
import queue
import threading
import time
import numpy as np

try:
    import sounddevice as sd
except OSError as e:
    if "PortAudio" in str(e):
        print(
            "PortAudio not found. On Linux (e.g. Debian/Ubuntu/Arduino):\n"
            "  sudo apt-get update\n"
            "  sudo apt-get install -y libportaudio2 portaudio19-dev\n"
            "Then: pip install --force-reinstall sounddevice",
            file=sys.stderr,
        )
    raise

from faster_whisper import WhisperModel
from google import genai
from google.genai import types

# --- Config (tuned for M4 Mac + live transcript) ---
SAMPLE_RATE = 16000  # Whisper expects 16 kHz
# Short chunks = low latency: transcript prints live (~1s delay)
LIVE_CHUNK_SEC = 1.0
# Send this many seconds of transcript to Gemini (batched in background)
GEMINI_BATCH_SEC = 5.0
# "small" = fast load & run; "medium" / "medium.en" = better accuracy, slower load
WHISPER_MODEL = "small"
WHISPER_COMPUTE_TYPE = "int8"  # works on CPU; use "float16" if you have GPU/Metal
WHISPER_DEVICE = "cpu"  # "cpu" is fast on M4; use "cuda" on NVIDIA
GEMINI_MODEL = "gemini-2.5-flash"

THREAT_ASSESSMENT_SYSTEM_PROMPT = """You are a threat assessment assistant. You will receive a transcription of audio from a police stop (e.g., traffic stop, pedestrian stop). Your job is to assess the situation and provide a concise threat assessment.

Consider:
- Tone and language (calm vs agitated, compliant vs hostile)
- Explicit threats or aggressive language
- Signs of de-escalation or escalation
- Any mention of weapons, violence, or intent to harm
- Context that might indicate risk to the officer or the person stopped

Respond with:
1. THREAT LEVEL: [LOW / MODERATE / ELEVATED / HIGH] and one sentence why.
2. KEY OBSERVATIONS: 2-4 bullet points.
3. RECOMMENDATION: One short sentence (e.g., "Continue de-escalation" or "Request backup if available").
Keep the response brief and actionable."""


def get_whisper_model():
    """Load Whisper model; fallback compute type if float16/int8 not supported (e.g. CPU)."""
    for compute_type in (WHISPER_COMPUTE_TYPE, "int8", "float32"):
        try:
            return WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=compute_type,
                cpu_threads=0,
                num_workers=1,
            )
        except ValueError as e:
            if "compute type" in str(e).lower():
                if compute_type == "float32":
                    raise
                print(f"  Fallback: {compute_type} not supported, trying next...", flush=True)
                continue
            raise
    raise RuntimeError("Could not load Whisper with any compute type")


def record_chunk(q: queue.Queue, sample_rate: int, chunk_sec: float):
    """Record audio in small chunks and put raw numpy frames into q."""
    block_size = int(sample_rate * chunk_sec)
    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype=np.float32,
        blocksize=block_size,
    ) as stream:
        while True:
            data, _ = stream.read(block_size)
            if data.size == 0:
                break
            q.put(data.copy())


def transcribe_audio(model: WhisperModel, audio_f32: np.ndarray, sample_rate: int) -> str:
    """Run Whisper; print each segment live to the terminal, return full text."""
    audio_1d = np.squeeze(audio_f32)
    if audio_1d.ndim != 1:
        audio_1d = audio_1d.flatten()
    segments, _ = model.transcribe(audio_1d, language=None, vad_filter=True)
    parts = []
    for s in segments:
        seg_text = s.text.strip()
        if seg_text:
            # Live transcript: print immediately so you see it as you speak
            print(seg_text, end=" ", flush=True)
            parts.append(seg_text)
    if parts:
        print(flush=True)
    return " ".join(parts).strip()


def _run_gemini_and_print(gemini_client: genai.Client, transcription: str) -> None:
    """Run threat assessment in background and print result (for threading)."""
    try:
        result = assess_threat(gemini_client, transcription)
        print("[Threat assessment]\n" + result + "\n", flush=True)
    except Exception as e:
        print(f"[LOG] Gemini error: {e}", flush=True)


def assess_threat(gemini_client: genai.Client, transcription: str) -> str:
    """Send transcription to Gemini with police-stop context and get threat assessment."""
    if not transcription or not transcription.strip():
        return "[No speech transcribed — cannot assess.]"
    print("[LOG] Calling Gemini API for threat assessment...", flush=True)
    user_message = (
        "Transcription from a police stop (e.g., traffic or pedestrian stop):\n\n"
        f'"""\n{transcription}\n"""\n\n'
        "Provide the threat assessment as specified in your instructions."
    )
    t0 = time.perf_counter()
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=THREAT_ASSESSMENT_SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=512,
        ),
    )
    elapsed = time.perf_counter() - t0
    print(f"[LOG] Gemini response received ({elapsed:.1f}s)", flush=True)
    if hasattr(response, "text") and response.text:
        return response.text.strip()
    return "[No assessment returned.]"


def main():
    parser = argparse.ArgumentParser(description="Live mic → Whisper transcript → Gemini threat assessment")
    parser.add_argument(
        "--no-gemini",
        action="store_true",
        help="Disable Gemini API; only run live transcription (no API key needed)",
    )
    args = parser.parse_args()
    use_gemini = not args.no_gemini and not os.environ.get("DISABLE_GEMINI")

    if use_gemini and not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY in the environment (or use --no-gemini).")
        sys.exit(1)

    print("Loading Whisper...")
    model = get_whisper_model()
    if use_gemini:
        print("Loading Gemini client...")
        gemini = genai.Client()
    else:
        print("Gemini disabled (transcript only).")
        gemini = None

    audio_queue = queue.Queue()
    recorder = threading.Thread(
        target=record_chunk,
        args=(audio_queue, SAMPLE_RATE, LIVE_CHUNK_SEC),
        daemon=True,
    )
    recorder.start()

    full_transcript = []  # aggregate everything said this session
    last_gemini_time = time.monotonic()
    mode = f"full transcript to Gemini every {GEMINI_BATCH_SEC}s" if use_gemini else "transcript only"
    print(f"Live transcript (chunks every {LIVE_CHUNK_SEC}s). {mode}. Press Ctrl+C to stop.\n")
    try:
        while True:
            chunk = audio_queue.get()
            if chunk is None:
                break
            text = transcribe_audio(model, chunk, SAMPLE_RATE)
            # Print transcription immediately so it’s visible before Gemini
            if text:
                full_transcript.append(text)
            if use_gemini and full_transcript:
                now = time.monotonic()
                if now - last_gemini_time >= GEMINI_BATCH_SEC:
                    whole_transcript = " ".join(full_transcript)
                    last_gemini_time = now
                    print("[LOG] Sending full transcript to Gemini (background)...", flush=True)
                    threading.Thread(target=_run_gemini_and_print, args=(gemini, whole_transcript), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopped.")
        if full_transcript:
            print("\n--- Full transcript ---")
            print(" ".join(full_transcript))
            print("---")


if __name__ == "__main__":
    main()
