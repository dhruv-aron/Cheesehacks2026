#!/usr/bin/env python3
"""
Entry point for running stream transcription in a separate process.
Consumes 16 kHz mono float32 audio chunks from a multiprocessing.Queue,
buffers to ~2.5s, skips silence, runs Whisper, prints transcript.
Used by combined_server to avoid GIL and isolate Whisper in its own process.
"""
import sys
import time

import numpy as np

from transcription.transcribe_and_assess import (
    SAMPLE_RATE as TRANSCRIPTION_SAMPLE_RATE,
    get_whisper_model,
    transcribe_audio,
)

# Match combined_server: longer chunks + silence gate to reduce Whisper hallucination
CHUNK_SEC = 2.5
SILENCE_RMS_THRESHOLD = 0.008
GEMINI_BATCH_SEC = 5.0


def run_transcription_process(transcription_queue, use_gemini: bool):
    """
    Run in a child process. Reads numpy float32 chunks (16 kHz mono) from
    transcription_queue until None is received. Buffers, filters silence,
    transcribes with Whisper, optionally sends to Gemini.
    """
    gemini_client = None
    if use_gemini:
        try:
            from google import genai
            gemini_client = genai.Client()
        except Exception as e:
            print("[Transcription process] Gemini init failed:", e, file=sys.stderr)
            use_gemini = False

    try:
        model = get_whisper_model()
    except Exception as e:
        print("[Transcription process] Whisper load failed:", e, file=sys.stderr)
        return

    target_samples = int(TRANSCRIPTION_SAMPLE_RATE * CHUNK_SEC)
    buffer = []
    buffer_samples = 0
    last_gemini_time = 0.0

    while True:
        try:
            chunk = transcription_queue.get()
        except Exception:
            break
        if chunk is None:
            break
        chunk = np.squeeze(chunk)
        if chunk.ndim > 1:
            chunk = chunk.mean(axis=1)
        buffer.append(chunk)
        buffer_samples += chunk.size
        if buffer_samples < target_samples:
            continue
        combined = np.concatenate(buffer, axis=0).astype(np.float32)
        buffer = [combined[target_samples:]] if combined.size > target_samples else []
        buffer_samples = combined.size - target_samples if combined.size > target_samples else 0
        to_transcribe = combined[:target_samples] if combined.size >= target_samples else combined
        if to_transcribe.size < 16000:
            continue
        rms = np.sqrt(np.mean(to_transcribe.astype(np.float64) ** 2))
        if rms < SILENCE_RMS_THRESHOLD:
            continue
        try:
            text = transcribe_audio(model, to_transcribe, TRANSCRIPTION_SAMPLE_RATE)
            if text and use_gemini and gemini_client is not None:
                now = time.monotonic()
                if now - last_gemini_time >= GEMINI_BATCH_SEC:
                    last_gemini_time = now
                    try:
                        from transcription.transcribe_and_assess import _run_gemini_and_print
                        _run_gemini_and_print(gemini_client, text)
                    except Exception as e:
                        print("[Transcription process] Gemini error:", e, file=sys.stderr)
        except Exception as e:
            print("[Transcription process]", e, file=sys.stderr)

    if buffer_samples > 0 and buffer:
        remainder = np.concatenate(buffer, axis=0).astype(np.float32)
        if remainder.size >= 16000:
            rms = np.sqrt(np.mean(remainder.astype(np.float64) ** 2))
            if rms >= SILENCE_RMS_THRESHOLD:
                try:
                    transcribe_audio(model, remainder, TRANSCRIPTION_SAMPLE_RATE)
                except Exception as e:
                    print("[Transcription process]", e, file=sys.stderr)
