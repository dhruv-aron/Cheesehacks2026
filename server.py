"""
Live video stream with YOLO object detection.
Default: best knife detection via Threat-Detection-YOLOv8n (filtered to knife only).
Use --all-threats for Gun, Knife, Explosive, Grenade. Use --general for YOLO12n (80 COCO classes). Mac M4 (MPS) supported.
Supports: UDP stream (e.g. from Arduino/FFmpeg), webcam (0), or video file.
Use --fast for lower latency (imgsz=512, stride=2) with good detection quality.
"""
import argparse
import os
import sys
from pathlib import Path

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
