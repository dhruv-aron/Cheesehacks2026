"""
Live video stream with YOLO object detection.
Default: best knife detection via Threat-Detection-YOLOv8n (filtered to knife only).
Use --all-threats for Gun, Knife, Explosive, Grenade. Use --general for YOLO12n (80 COCO classes). Mac M4 (MPS) supported.
Supports: UDP stream (e.g. from Arduino/FFmpeg), webcam (0), or video file.
When source is UDP, audio from the stream is played (requires: pip install av sounddevice). Use --no-audio to disable.
Use --fast for lower latency (imgsz=512, stride=2) with good detection quality.
"""
import argparse
import os
import sys
import threading
from pathlib import Path
from queue import Queue, Empty

import cv2
from ultralytics import YOLO

# Default: UDP stream from Linux/Arduino. Use VIDEO_SOURCE=0 for local webcam.
DEFAULT_VIDEO_SOURCE = os.environ.get("VIDEO_SOURCE", "udp://@:1234")
# Best knife detection: Threat-Detection-YOLOv8n (trained on Gun, Knife, Explosive, Grenade). Default: filter to knife only.
THREAT_MODEL_URL = "https://huggingface.co/Subh775/Threat-Detection-YOLOv8n/resolve/main/weights/best.pt"
KNIFE_CLASS_NAME = "knife"
THREAT_MODEL_PATH = Path(__file__).resolve().parent / "threat_detection.pt"
DEFAULT_MODEL = os.environ.get("YOLO_MODEL", str(THREAT_MODEL_PATH))
# Quality-focused defaults: 640 matches training; 0.30 reduces false positives.
CONF_THRESHOLD = float(os.environ.get("YOLO_CONF", "0.30"))
DEFAULT_IMGSZ = int(os.environ.get("YOLO_IMGSZ", "640"))
DEFAULT_STRIDE = int(os.environ.get("YOLO_STRIDE", "1"))
# Low-latency mode: 512px + every 2nd frame (better detail than 480, conf 0.30 for reliable detections).
FAST_IMGSZ = 512
FAST_STRIDE = 2
FAST_CONF = 0.30

# YOLO12 nano for general object detection (COCO 80 classes); auto-downloaded by Ultralytics.
YOLO12N_MODEL = "yolo12n.pt"

THREAT_CLASSES = ("gun", "knife", "explosive", "grenade")


def ensure_threat_model() -> str:
    """Download Threat-Detection model if not present; return path to .pt file."""
    path = Path(DEFAULT_MODEL)
    if path.is_absolute() and path.exists():
        return str(path)
    if THREAT_MODEL_PATH.exists():
        return str(THREAT_MODEL_PATH)
    print("Downloading threat model (knife detection; Gun, Knife, Explosive, Grenade)...")
    try:
        import urllib.request
        THREAT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(THREAT_MODEL_URL, THREAT_MODEL_PATH)
        if not THREAT_MODEL_PATH.exists() or THREAT_MODEL_PATH.stat().st_size < 1_000_000:
            raise RuntimeError("Downloaded file too small or missing")
        print("Saved:", THREAT_MODEL_PATH)
        return str(THREAT_MODEL_PATH)
    except Exception as e:
        print("Error: Could not download threat model:", e, file=sys.stderr)
        print("Download manually: curl -L -o threat_detection.pt", THREAT_MODEL_URL, file=sys.stderr)
        sys.exit(1)


def get_device():
    """Use MPS on Mac M1/M2/M4 if available, else CPU."""
    try:
        import torch
        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


def open_capture(source: str):
    """Open video capture for UDP, webcam, or file. Minimal buffer for low latency."""
    if source.isdigit():
        cap = cv2.VideoCapture(int(source))
    elif source.startswith(("udp://", "rtsp://", "http")):
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    else:
        cap = cv2.VideoCapture(source)
    try:
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return cap


# Fixed output rate for stable playback (sender uses 48000)
AUDIO_OUT_RATE = 48000
AUDIO_BLOCKSIZE = 1024


def _audio_stream_worker(audio_queue: Queue, sample_rate: int, channels: int, stop_event: threading.Event):
    """Play audio using OutputStream callback so playback runs at a constant rate (smoother)."""
    try:
        import sounddevice as sd
        import numpy as np

        # Buffer: hold samples we haven't played yet (interleaved float32)
        buffer = []
        buffer_frames = 0

        def _get_frames(n_frames):
            nonlocal buffer_frames
            out = np.zeros((n_frames, channels), dtype=np.float32, order="C")
            filled = 0
            while filled < n_frames:
                if not buffer:
                    try:
                        chunk = audio_queue.get(timeout=0.1)
                        if chunk is None:
                            break
                        if chunk.dtype != np.float32:
                            chunk = np.clip(
                                chunk.astype(np.float32) / (2 ** (chunk.dtype.itemsize * 8 - 1)), -1.0, 1.0
                            )
                        if chunk.ndim == 1:
                            chunk = chunk.reshape(-1, 1)
                        if chunk.shape[1] != channels:
                            chunk = np.repeat(chunk, channels, axis=1) if channels > 1 else chunk[:, :1]
                        buffer.append(chunk)
                        buffer_frames += chunk.shape[0]
                    except Empty:
                        break
                if buffer:
                    take = min(buffer[0].shape[0], n_frames - filled)
                    out[filled : filled + take] = buffer[0][:take]
                    filled += take
                    if take >= buffer[0].shape[0]:
                        buffer_frames -= buffer[0].shape[0]
                        buffer.pop(0)
                    else:
                        buffer[0] = buffer[0][take:]
                        buffer_frames -= take
            return out

        def callback(outdata, frames, time_info, status):
            if status:
                print("Audio:", status, file=sys.stderr)
            data = _get_frames(frames)
            outdata[:] = data

        with sd.OutputStream(
            samplerate=sample_rate,
            channels=channels,
            dtype="float32",
            blocksize=AUDIO_BLOCKSIZE,
            callback=callback,
        ):
            stop_event.wait()
    except Exception as e:
        print("Audio playback error:", e, file=sys.stderr)


def run_with_audio_av(
    source: str,
    model,
    args,
    filter_cls_ids,
    use_half: bool,
    device: str,
    is_general: bool,
    class_names: dict,
):
    """Run YOLO on video from UDP stream and play audio using PyAV. Source must be UDP."""
    import av
    import numpy as np

    # PyAV/FFmpeg: receiver must bind and listen. Match sender pkt_size.
    if "udp://" in source.lower():
        # e.g. udp://@:1234 or udp://0.0.0.0:1234
        parts = source.strip().rstrip("/").replace("udp://", "").split("?")[0]
        if "@" in parts:
            port = parts.split(":")[-1].strip()
        else:
            port = parts.split(":")[-1].strip()
        av_source = "udp://0.0.0.0:%s?pkt_size=1316&overrun_nonfatal=1&listen=1" % port
    else:
        av_source = source

    try:
        container = av.open(av_source, options={"fflags": "nobuffer", "flags": "low_delay"})
    except Exception as e:
        print("PyAV open failed:", e)
        return False

    video_stream = None
    audio_stream = None
    for s in container.streams:
        if s.type == "video":
            video_stream = s
        elif s.type == "audio":
            audio_stream = s

    if not video_stream:
        container.close()
        return False
    if not audio_stream:
        print("No audio stream in source (video-only). Install av/sounddevice and ensure sender uses audio.")

    audio_queue = Queue(maxsize=60)
    audio_stop = threading.Event()
    if audio_stream:
        try:
            import sounddevice as sd
            # Use fixed 48 kHz to match sender and avoid speed/wobble
            rate = AUDIO_OUT_RATE
            layout = audio_stream.layout
            if hasattr(layout, "channels"):
                channels = layout.channels if isinstance(layout.channels, int) else len(layout.channels)
            else:
                channels = 1
            audio_thread = threading.Thread(
                target=_audio_stream_worker,
                args=(audio_queue, rate, channels, audio_stop),
                daemon=True,
            )
            audio_thread.start()
            print("Audio from stream enabled (speakers, %d Hz)" % rate)
        except ImportError:
            print("Install sounddevice for audio: pip install sounddevice")
            audio_stream = None

    last_results = None
    frame_index = 0

    try:
        # Demux all streams; handle video and audio packets.
        for packet in container.demux():
            if packet.stream.type == "video":
                for frame in packet.decode():
                    try:
                        img = frame.to_ndarray(format="bgr24")
                    except Exception:
                        img = frame.reformat(format="bgr24").to_ndarray()
                    if img is None:
                        continue

                    if frame_index % args.stride == 0:
                        predict_kw = dict(
                            conf=args.conf,
                            verbose=False,
                            imgsz=args.imgsz,
                            half=use_half,
                            device=device,
                            max_det=100,
                            iou=0.5,
                        )
                        if filter_cls_ids is not None:
                            predict_kw["classes"] = filter_cls_ids
                        results = model.predict(img, **predict_kw)
                        last_results = results

                    if last_results and len(last_results) > 0:
                        annotated = last_results[0].plot(img=img.copy())
                    else:
                        annotated = img
                    frame_index += 1

                    if not args.no_display:
                        if is_general:
                            title = "YOLO12 general detection"
                        elif args.all_threats:
                            title = "Multi-threat detection (Gun, Knife, Explosive, Grenade)"
                        else:
                            title = "Knife detection"
                        cv2.imshow(title, annotated)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            raise StopIteration
                    else:
                        if last_results and len(last_results) > 0 and len(last_results[0].boxes) > 0:
                            for box in last_results[0].boxes:
                                cls_id = int(box.cls[0])
                                conf = float(box.conf[0])
                                name = class_names.get(cls_id, str(cls_id))
                                print("Detection: %s @ conf=%.2f" % (name, conf))

            elif packet.stream.type == "audio" and audio_stream is not None and audio_queue is not None:
                for frame in packet.decode():
                    try:
                        arr = frame.to_ndarray()
                        # Normalize to float32 [-1, 1]
                        if arr.dtype != np.float32:
                            arr = arr.astype(np.float32) / (2 ** (arr.dtype.itemsize * 8 - 1))
                        # (samples, channels) for sounddevice; PyAV often (channels, samples)
                        if arr.ndim == 2 and arr.shape[0] < arr.shape[1]:
                            arr = arr.T
                        # Resample to 48 kHz if stream rate differs (avoids speed/wobble)
                        in_rate = frame.sample_rate or audio_stream.sample_rate or 48000
                        if in_rate != AUDIO_OUT_RATE and in_rate > 0:
                            n_out = int(round(arr.shape[0] * AUDIO_OUT_RATE / in_rate))
                            if arr.ndim == 1:
                                arr = np.interp(
                                    np.linspace(0, arr.shape[0] - 1, n_out),
                                    np.arange(arr.shape[0]),
                                    arr,
                                ).astype(np.float32)
                            else:
                                arr = np.column_stack([
                                    np.interp(
                                        np.linspace(0, arr.shape[0] - 1, n_out),
                                        np.arange(arr.shape[0]),
                                        arr[:, c],
                                    ).astype(np.float32)
                                    for c in range(arr.shape[1])
                                ])
                        try:
                            audio_queue.put(arr, block=False)
                        except Exception:
                            pass
                    except Exception:
                        pass

    except StopIteration:
        pass
    except Exception as e:
        print("Stream error:", e)
    finally:
        audio_stop.set()
        if audio_queue is not None:
            try:
                audio_queue.put(None, timeout=0.5)
            except Exception:
                pass
        container.close()
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Live YOLO detection. Default: knife detection. Use --all-threats or --general. Mac M4 (MPS) supported."
    )
    parser.add_argument(
        "--source", "-s",
        default=DEFAULT_VIDEO_SOURCE,
        help="Video source: udp://@:1234, 0 (webcam), or path to file",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Path to .pt model (default: threat_detection.pt). Use --general for yolo12n.pt",
    )
    parser.add_argument(
        "--general", "-g",
        action="store_true",
        help="Use YOLO12n for general object detection (80 COCO classes); auto-downloaded",
    )
    parser.add_argument(
        "--all-threats",
        action="store_true",
        help="Show all threat classes (Gun, Knife, Explosive, Grenade). Default: knife only.",
    )
    parser.add_argument("--conf", type=float, default=None, help="Confidence threshold 0-1 (default 0.30)")
    parser.add_argument("--no-display", action="store_true", help="Headless; no window")
    parser.add_argument("--imgsz", type=int, default=None, help="Inference size (default 640, 512 in --fast)")
    parser.add_argument("--stride", type=int, default=None, help="Run detection every N frames (default 1, 2 in --fast)")
    parser.add_argument("--fast", "-f", action="store_true", help="Lower latency: imgsz=512, stride=2 (good accuracy)")
    parser.add_argument("--no-audio", action="store_true", help="Disable audio playback from UDP stream")
    parser.add_argument("--no-half", action="store_true", help="Disable FP16 (use if errors on GPU/MPS)")
    args = parser.parse_args()

    if args.general:
        args.model = YOLO12N_MODEL

    if args.fast:
        if args.imgsz is None:
            args.imgsz = FAST_IMGSZ
        if args.stride is None:
            args.stride = FAST_STRIDE
        if args.conf is None:
            args.conf = FAST_CONF
    if args.imgsz is None:
        args.imgsz = DEFAULT_IMGSZ
    if args.stride is None:
        args.stride = DEFAULT_STRIDE
    if args.conf is None:
        args.conf = CONF_THRESHOLD

    if args.model is None:
        model_path = ensure_threat_model()
    else:
        model_path = args.model

    is_general = model_path == YOLO12N_MODEL or "yolo12" in model_path.lower()
    device = get_device()
    print("Loading model:", model_path, "| device:", device)
    model = YOLO(model_path)
    class_names = model.names

    # Threat model: default to knife only; use --all-threats for Gun, Knife, Explosive, Grenade.
    filter_cls_ids = None
    if not is_general and not args.all_threats:
        filter_cls_ids = [i for i, name in class_names.items() if str(name).lower() == KNIFE_CLASS_NAME]
        if filter_cls_ids:
            print("Knife detection only (use --all-threats for Gun, Knife, Explosive, Grenade)")
        else:
            filter_cls_ids = None
    if is_general:
        print("Classes: COCO 80 (general)")
    elif filter_cls_ids is None:
        print("Classes:", class_names)

    use_half = False
    if device == "cuda" and not args.no_half:
        try:
            import torch
            use_half = torch.cuda.is_available()
        except Exception:
            pass

    print("Opening source:", args.source)
    # When source is UDP and audio not disabled, try PyAV for video+audio (audio played to speakers).
    use_av_audio = (
        not args.no_audio
        and args.source.strip().lower().startswith("udp://")
    )
    if use_av_audio:
        try:
            import av
            print("Trying video+audio path (PyAV)...")
            if run_with_audio_av(
                args.source,
                model,
                args,
                filter_cls_ids,
                use_half,
                device,
                is_general,
                class_names,
            ):
                if not args.no_display:
                    cv2.destroyAllWindows()
                return
        except ImportError as e:
            print("Install av and sounddevice for audio: pip install av sounddevice")
            print("Falling back to video only.")
        except Exception as e:
            print("Audio path failed, falling back to video only:", e)
        use_av_audio = False

    print("Using video-only path (OpenCV). No audio.")

    cap = open_capture(args.source)
    if not cap.isOpened():
        print("Error: Could not open video stream.")
        sys.exit(1)

    print("Stream connected. Press 'q' to quit. imgsz=%s conf=%.2f stride=%s%s" % (
        args.imgsz, args.conf, args.stride, " [fast]" if args.fast else ""))
    last_results = None
    frame_index = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Dropped frame or stream interrupted.")
            break

        if frame_index % args.stride == 0:
            predict_kw = dict(
                conf=args.conf,
                verbose=False,
                imgsz=args.imgsz,
                half=use_half,
                device=device,
                max_det=100,
                iou=0.5,
            )
            if filter_cls_ids is not None:
                predict_kw["classes"] = filter_cls_ids
            results = model.predict(frame, **predict_kw)
            last_results = results

        if last_results and len(last_results) > 0:
            annotated = last_results[0].plot(img=frame.copy())
        else:
            annotated = frame

        frame_index += 1

        if not args.no_display:
            if is_general:
                title = "YOLO12 general detection"
            elif args.all_threats:
                title = "Multi-threat detection (Gun, Knife, Explosive, Grenade)"
            else:
                title = "Knife detection"
            cv2.imshow(title, annotated)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        else:
            if last_results and len(last_results) > 0 and len(last_results[0].boxes) > 0:
                for box in last_results[0].boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = class_names.get(cls_id, str(cls_id))
                    print("Detection: %s @ conf=%.2f" % (name, conf))

    cap.release()
    if not args.no_display:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
