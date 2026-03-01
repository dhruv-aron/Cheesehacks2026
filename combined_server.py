"""
Combined Live video stream with YOLO object detection and MoveNet posture anomaly detection.
Supports UDP stream, webcam (0), or video file.
"""
import argparse
import os
import sys
import threading
from pathlib import Path
from queue import Queue, Empty

import cv2
import numpy as np
from ultralytics import YOLO

import ai_edge_litert.interpreter as tflite
import kagglehub

# ==========================================
# 1. Configuration & Constants
# ==========================================
DEFAULT_VIDEO_SOURCE = os.environ.get("VIDEO_SOURCE", "udp://@:1234")
THREAT_MODEL_URL = "https://huggingface.co/Subh775/Threat-Detection-YOLOv8n/resolve/main/weights/best.pt"
KNIFE_CLASS_NAME = "knife"
THREAT_MODEL_PATH = Path(__file__).resolve().parent / "threat_detection.pt"
DEFAULT_MODEL = os.environ.get("YOLO_MODEL", str(THREAT_MODEL_PATH))

CONF_THRESHOLD = float(os.environ.get("YOLO_CONF", "0.30"))
DEFAULT_IMGSZ = int(os.environ.get("YOLO_IMGSZ", "640"))
DEFAULT_STRIDE = int(os.environ.get("YOLO_STRIDE", "1"))
FAST_IMGSZ = 512
FAST_STRIDE = 2
FAST_CONF = 0.30
YOLO12N_MODEL = "yolo12n.pt"

AUDIO_OUT_RATE = 48000
AUDIO_BLOCKSIZE = 1024

# ==========================================
# 2. MoveNet initialization and Constants
# ==========================================
print("Downloading/Loading MoveNet TFLite model...")
model_path = kagglehub.model_download("google/movenet/tfLite/singlepose-lightning")
tflite_model_path = f"{model_path}/3.tflite"

interpreter = tflite.Interpreter(model_path=tflite_model_path)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

KEYPOINT_DICT = {
    'nose': 0, 'left_eye': 1, 'right_eye': 2, 'left_ear': 3, 'right_ear': 4,
    'left_shoulder': 5, 'right_shoulder': 6, 'left_elbow': 7, 'right_elbow': 8,
    'left_wrist': 9, 'right_wrist': 10, 'left_hip': 11, 'right_hip': 12,
    'left_knee': 13, 'right_knee': 14, 'left_ankle': 15, 'right_ankle': 16
}

EDGES = {
    (0, 1): 'm', (0, 2): 'c', (1, 3): 'm', (2, 4): 'c',
    (0, 5): 'm', (0, 6): 'c', (5, 7): 'm', (7, 9): 'm',
    (6, 8): 'c', (8, 10): 'c', (5, 6): 'y', (5, 11): 'm',
    (6, 12): 'c', (11, 12): 'y', (11, 13): 'm', (13, 15): 'm',
    (12, 14): 'c', (14, 16): 'c'
}

# Global state for danger score smoothing
current_danger_score = 0
prev_kpts = None

# ==========================================
# 3. MoveNet Geometry Logic
# ==========================================
def draw_keypoints(frame, keypoints, confidence_threshold=0.3):
    y, x, _ = frame.shape
    shaped = np.squeeze(np.multiply(keypoints, [y, x, 1]))
    for kp in shaped:
        ky, kx, kp_conf = kp
        if kp_conf > confidence_threshold:
            cv2.circle(frame, (int(kx), int(ky)), 5, (0, 255, 0), -1)

def draw_connections(frame, keypoints, edges, confidence_threshold=0.3):
    y, x, _ = frame.shape
    shaped = np.squeeze(np.multiply(keypoints, [y, x, 1]))
    for edge, _ in edges.items():
        p1, p2 = edge
        y1, x1, c1 = shaped[p1]
        y2, x2, c2 = shaped[p2]
        if (c1 > confidence_threshold) and (c2 > confidence_threshold):      
            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)

def get_distance(p1, p2):
    return np.linalg.norm(np.array([p1[1], p1[0]]) - np.array([p2[1], p2[0]]))

def is_confident(confidence_threshold, *kpts):
    return all(k[2] > confidence_threshold for k in kpts)

def calculate_danger_score(shaped_kpts, prev_kpts=None, confidence_threshold=0.3):
    score = 0
    reasons = []

    left_wrist = shaped_kpts[KEYPOINT_DICT['left_wrist']]
    right_wrist = shaped_kpts[KEYPOINT_DICT['right_wrist']]
    left_hip = shaped_kpts[KEYPOINT_DICT['left_hip']]
    right_hip = shaped_kpts[KEYPOINT_DICT['right_hip']]
    left_shoulder = shaped_kpts[KEYPOINT_DICT['left_shoulder']]
    right_shoulder = shaped_kpts[KEYPOINT_DICT['right_shoulder']]
    left_elbow = shaped_kpts[KEYPOINT_DICT['left_elbow']]
    right_elbow = shaped_kpts[KEYPOINT_DICT['right_elbow']]
    nose = shaped_kpts[KEYPOINT_DICT['nose']]

    if is_confident(confidence_threshold, left_shoulder, right_shoulder):
        shoulder_width = get_distance(left_shoulder, right_shoulder)
        if shoulder_width < 10:
            shoulder_width = 10 
    else:
        shoulder_width = 50 

    if not is_confident(confidence_threshold, left_wrist):
        score += 10
        reasons.append("Left hand out of frame")
    if not is_confident(confidence_threshold, right_wrist):
        score += 10
        reasons.append("Right hand out of frame")

    if prev_kpts is not None:
        prev_left_wrist = prev_kpts[KEYPOINT_DICT['left_wrist']]
        prev_right_wrist = prev_kpts[KEYPOINT_DICT['right_wrist']]
        
        if is_confident(confidence_threshold, left_wrist) and is_confident(confidence_threshold, prev_left_wrist):
            left_movement = get_distance(left_wrist, prev_left_wrist) / shoulder_width
            if left_movement > 0.8: 
                score += 50
                reasons.append("Extreme left hand movement")
            elif left_movement > 0.4:
                score += 20
                reasons.append("Sudden left hand movement")
                
        if is_confident(confidence_threshold, right_wrist) and is_confident(confidence_threshold, prev_right_wrist):
            right_movement = get_distance(right_wrist, prev_right_wrist) / shoulder_width
            if right_movement > 0.8:
                score += 50
                reasons.append("Extreme right hand movement")
            elif right_movement > 0.4:
                score += 20
                reasons.append("Sudden right hand movement")

    if is_confident(confidence_threshold, right_wrist, right_hip):
        if get_distance(right_wrist, right_hip) / shoulder_width < 0.8: 
            score += 20
            reasons.append("Right hand at waist")
            
    if is_confident(confidence_threshold, left_wrist, left_hip):
        if get_distance(left_wrist, left_hip) / shoulder_width < 0.8:
            score += 20
            reasons.append("Left hand at waist")

    if is_confident(confidence_threshold, left_wrist, left_shoulder):
        if left_wrist[0] < left_shoulder[0] + (0.5 * shoulder_width):
            score += 15
            reasons.append("Left hand raised")
            
    if is_confident(confidence_threshold, right_wrist, right_shoulder):
        if right_wrist[0] < right_shoulder[0] + (0.5 * shoulder_width):
            score += 15
            reasons.append("Right hand raised")

    if is_confident(confidence_threshold, left_wrist, left_shoulder):
        if get_distance(left_wrist, left_shoulder) / shoulder_width > 1.2:
            score += 15
            reasons.append("Left hand extended")
            
    if is_confident(confidence_threshold, right_wrist, right_shoulder):
        if get_distance(right_wrist, right_shoulder) / shoulder_width > 1.2:
            score += 15
            reasons.append("Right hand extended")

    if is_confident(confidence_threshold, left_wrist, left_elbow, left_shoulder) and \
       is_confident(confidence_threshold, right_wrist, right_elbow, right_shoulder):
        if (left_wrist[0] < left_elbow[0]) and (right_wrist[0] < right_elbow[0]):
            score -= 50
            reasons.append("Hands up (Surrender)")
            reasons = [r for r in reasons if "raised" not in r]

    if is_confident(confidence_threshold, left_wrist, right_wrist):
        hands_together = get_distance(left_wrist, right_wrist) / shoulder_width < 0.6
        if hands_together:
            on_left_hip = is_confident(confidence_threshold, left_hip) and get_distance(left_wrist, left_hip) / shoulder_width < 0.8 and get_distance(right_wrist, left_hip) / shoulder_width < 0.8
            on_right_hip = is_confident(confidence_threshold, right_hip) and get_distance(left_wrist, right_hip) / shoulder_width < 0.8 and get_distance(right_wrist, right_hip) / shoulder_width < 0.8
            
            if on_left_hip or on_right_hip:
                score += 80
                reasons.append("Two hands together on one hip (Very Dangerous)")
                
            if is_confident(confidence_threshold, left_shoulder, right_shoulder):
                avg_shoulder_y = (left_shoulder[0] + right_shoulder[0]) / 2.0
                avg_wrist_y = (left_wrist[0] + right_wrist[0]) / 2.0
                
                at_shoulder_level = abs(avg_wrist_y - avg_shoulder_y) / shoulder_width < 0.5
                dist_from_left_shoulder = get_distance(left_wrist, left_shoulder) / shoulder_width
                dist_from_right_shoulder = get_distance(right_wrist, right_shoulder) / shoulder_width
                
                if at_shoulder_level and (dist_from_left_shoulder > 1.2 or dist_from_right_shoulder > 1.2):
                    score += 80
                    reasons.append("Two hands together in shooting motion (Very Dangerous)")

    if is_confident(confidence_threshold, left_wrist, right_wrist, nose, left_shoulder, right_shoulder):
        if left_wrist[0] < left_shoulder[0] and right_wrist[0] < right_shoulder[0]:
            if get_distance(left_wrist, nose) / shoulder_width < 1.0 and get_distance(right_wrist, nose) / shoulder_width < 1.0:
                score -= 100
                reasons.append("Hands on head (Not dangerous)")
                reasons = [r for r in reasons if "raised" not in r and "extended" not in r and "Surrender" not in r]

    score = max(0, min(score, 100))
    return score, reasons

# ==========================================
# 4. Processing unified frame
# ==========================================
def process_single_frame(frame, yolo_model, predict_kw):
    global current_danger_score, prev_kpts
    
    # --- YOLO INFERENCE ---
    results = yolo_model.predict(frame, **predict_kw)
    if results and len(results) > 0:
        annotated = results[0].plot(img=frame.copy())
    else:
        annotated = frame.copy()

    # --- MOVENET INFERENCE ---
    h, w = frame.shape[:2]
    scale = min(192/h, 192/w)
    new_h, new_w = int(h*scale), int(w*scale)
    resized = cv2.resize(frame, (new_w, new_h))
    
    pad_h, pad_w = 192 - new_h, 192 - new_w
    top, bottom = pad_h // 2, pad_h - (pad_h // 2)
    left, right = pad_w // 2, pad_w - (pad_w // 2)
    padded = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[0, 0, 0])
    
    input_image = np.expand_dims(padded, axis=0).astype(np.float32)
    
    interpreter.set_tensor(input_details[0]['index'], input_image)
    interpreter.invoke()
    keypoints = interpreter.get_tensor(output_details[0]['index'])
    
    # Make Calculations Based on Points over ORIGINAL frame dimensions
    y, x, _ = frame.shape
    shaped_kpts = np.squeeze(np.multiply(keypoints, [y, x, 1]))
    confidence_threshold = 0.3
    
    raw_score, reasons = calculate_danger_score(shaped_kpts, prev_kpts, confidence_threshold)
    prev_kpts = shaped_kpts
    
    alpha = 0.2
    if raw_score > current_danger_score:
        current_danger_score = raw_score 
    else:
        current_danger_score = current_danger_score * (1 - alpha) + raw_score * alpha 
        
    # --- DRAW OVERLAYS ---
    draw_connections(annotated, keypoints, EDGES, confidence_threshold)
    draw_keypoints(annotated, keypoints, confidence_threshold)
        
    score_int = int(current_danger_score)
    color = (0, int(255 - (score_int * 2.55)), int(score_int * 2.55)) 
    
    cv2.putText(annotated, f"Danger Score: {score_int}/100", 
                (20, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    

    return annotated, results

# ==========================================
# 5. Core Server Logic (from server.py)
# ==========================================
def ensure_threat_model() -> str:
    path = Path(DEFAULT_MODEL)
    if path.is_absolute() and path.exists():
        return str(path)
    if THREAT_MODEL_PATH.exists():
        return str(THREAT_MODEL_PATH)
    print("Downloading threat model...")
    try:
        import urllib.request
        THREAT_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(THREAT_MODEL_URL, THREAT_MODEL_PATH)
        return str(THREAT_MODEL_PATH)
    except Exception as e:
        print("Error: Could not download threat model:", e, file=sys.stderr)
        sys.exit(1)

def get_device():
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

def _audio_stream_worker(audio_queue: Queue, sample_rate: int, channels: int, stop_event: threading.Event):
    try:
        import sounddevice as sd
        import numpy as np

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

def run_with_audio_av(source: str, yolo_model, args, filter_cls_ids, use_half: bool, device: str, is_general: bool, class_names: dict):
    import av
    import numpy as np

    if "udp://" in source.lower():
        parts = source.strip().rstrip("/").replace("udp://", "").split("?")[0]
        port = parts.split(":")[-1].strip()
        av_source = "udp://0.0.0.0:%s?pkt_size=1316&overrun_nonfatal=1&listen=1" % port
    else:
        av_source = source

    try:
        container = av.open(av_source, options={"fflags": "nobuffer", "flags": "low_delay"})
    except Exception as e:
        print("PyAV open failed:", e)
        return False

    video_stream, audio_stream = None, None
    for s in container.streams:
        if s.type == "video": video_stream = s
        elif s.type == "audio": audio_stream = s

    if not video_stream: return False

    audio_queue, audio_stop = Queue(maxsize=60), threading.Event()
    if audio_stream and not args.no_audio:
        try:
            import sounddevice as sd
            rate = AUDIO_OUT_RATE
            layout = audio_stream.layout
            channels = layout.channels if hasattr(layout, "channels") else 1
            if not isinstance(channels, int): channels = len(channels)
            
            threading.Thread(target=_audio_stream_worker, args=(audio_queue, rate, channels, audio_stop), daemon=True).start()
        except ImportError:
            audio_stream = None

    frame_index = 0
    try:
        for packet in container.demux():
            if packet.stream.type == "video":
                for frame in packet.decode():
                    try: img = frame.to_ndarray(format="bgr24")
                    except: img = frame.reformat(format="bgr24").to_ndarray()
                    
                    if img is None: continue

                    if frame_index % args.stride == 0:
                        predict_kw = dict(conf=args.conf, verbose=False, imgsz=args.imgsz, half=use_half, device=device)
                        if filter_cls_ids is not None: predict_kw["classes"] = filter_cls_ids
                        
                        annotated, results = process_single_frame(img, yolo_model, predict_kw)

                        if not args.no_display:
                            cv2.imshow("Combined Threat Detection", annotated)
                            if cv2.waitKey(1) & 0xFF == ord("q"): raise StopIteration
                    frame_index += 1
            
            elif packet.stream.type == "audio" and audio_stream and audio_queue:
                for frame in packet.decode():
                    try:
                        arr = frame.to_ndarray()
                        if arr.dtype != np.float32: arr = arr.astype(np.float32) / (2 ** (arr.dtype.itemsize * 8 - 1))
                        if arr.ndim == 2 and arr.shape[0] < arr.shape[1]: arr = arr.T
                        
                        in_rate = frame.sample_rate or audio_stream.sample_rate or 48000
                        if in_rate != AUDIO_OUT_RATE and in_rate > 0:
                            n_out = int(round(arr.shape[0] * AUDIO_OUT_RATE / in_rate))
                            if arr.ndim == 1:
                                arr = np.interp(np.linspace(0, arr.shape[0]-1, n_out), np.arange(arr.shape[0]), arr).astype(np.float32)
                            else:
                                arr = np.column_stack([np.interp(np.linspace(0, arr.shape[0]-1, n_out), np.arange(arr.shape[0]), arr[:, c]).astype(np.float32) for c in range(arr.shape[1])])
                        try: audio_queue.put(arr, block=False)
                        except: pass
                    except: pass
    except StopIteration: pass
    except Exception as e: print("Stream error:", e)
    finally:
        audio_stop.set()
        if audio_queue:
            try: audio_queue.put(None, timeout=0.5)
            except: pass
        container.close()
    return True

def main():
    parser = argparse.ArgumentParser(description="Live Web UI for YOLO Threat Detection & TFLite Posture Detection")
    parser.add_argument("--source", "-s", default=DEFAULT_VIDEO_SOURCE)
    parser.add_argument("--model", "-m", default=None)
    parser.add_argument("--general", "-g", action="store_true")
    parser.add_argument("--all-threats", action="store_true")
    parser.add_argument("--conf", type=float, default=None)
    parser.add_argument("--no-display", action="store_true")
    parser.add_argument("--imgsz", type=int, default=None)
    parser.add_argument("--stride", type=int, default=None)
    parser.add_argument("--fast", "-f", action="store_true")
    parser.add_argument("--no-audio", action="store_true")
    parser.add_argument("--no-half", action="store_true")
    args = parser.parse_args()

    if args.general: args.model = YOLO12N_MODEL
    if args.fast:
        if args.imgsz is None: args.imgsz = FAST_IMGSZ
        if args.stride is None: args.stride = FAST_STRIDE
        if args.conf is None: args.conf = FAST_CONF
        
    args.imgsz = args.imgsz or DEFAULT_IMGSZ
    args.stride = args.stride or DEFAULT_STRIDE
    args.conf = args.conf or CONF_THRESHOLD
    model_path = args.model or ensure_threat_model()

    is_general = model_path == YOLO12N_MODEL or "yolo12" in model_path.lower()
    device = get_device()
    print("Loading YOLO model:", model_path, "| device:", device)
    yolo_model = YOLO(model_path)
    class_names = yolo_model.names

    filter_cls_ids = None
    if not is_general and not args.all_threats:
        filter_cls_ids = [i for i, name in class_names.items() if str(name).lower() == KNIFE_CLASS_NAME]
        
    use_half = False
    if device == "cuda" and not args.no_half:
        try:
            import torch
            use_half = torch.cuda.is_available()
        except: pass

    # UDP PYAV PASS
    if not args.no_audio and "udp://" in args.source.lower():
        try:
            import av
            if run_with_audio_av(args.source, yolo_model, args, filter_cls_ids, use_half, device, is_general, class_names):
                if not args.no_display: cv2.destroyAllWindows()
                return
        except Exception as e:
            print("Audio path failed, falling back to video only:", e)

    # WEBCAM/FALLBACK PASS
    print("Using standard OpenCV path.")
    cap = open_capture(args.source)
    if not cap.isOpened():
        print("Error: Could not open video stream.")
        sys.exit(1)

    frame_index = 0
    while True:
        ret, frame = cap.read()
        if not ret: break

        if frame_index % args.stride == 0:
            predict_kw = dict(conf=args.conf, verbose=False, imgsz=args.imgsz, half=use_half, device=device)
            if filter_cls_ids is not None: predict_kw["classes"] = filter_cls_ids
            annotated, results = process_single_frame(frame, yolo_model, predict_kw)

            if not args.no_display:
                cv2.imshow("Combined Threat Detection", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"): break

        frame_index += 1

    cap.release()
    if not args.no_display: cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
