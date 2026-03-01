# Video streaming + YOLO detection

Stream from a Linux board (Arduino) to your Mac; run YOLOv8 object detection on the stream. Server runs on **Mac M4** (MPS) or CPU.

## Linux board (Arduino) – send the stream

1. Set **start_stream.sh**: `LAPTOP_IP` = your Mac’s IP; **stream.service**: `User`/`Group` = your Linux user.
2. On the board:
   ```bash
   sudo apt update && sudo apt install -y ffmpeg
   sudo cp start_stream.sh /usr/local/bin/ && sudo chmod +x /usr/local/bin/start_stream.sh
   sudo cp stream.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable stream.service && sudo systemctl start stream.service
   ```
3. Check: `sudo systemctl status stream.service`

## Mac (laptop) – receive stream and run multi-threat detection

1. Install deps (once):
   ```bash
   pip install opencv-python ultralytics
   ```
2. Run (multi-threat model auto-downloads on first run; uses MPS on M4):
   ```bash
   python3 server.py
   ```
   Detects **Gun, Knife, Explosive, Grenade**. Default source: `udp://@:1234`. Press `q` to quit.
   - Inference size 640 and conf 0.30 by default for good detection quality.
- Local webcam: `python3 server.py --source 0`
- Custom model: `python3 server.py --model path/to/model.pt`

## Raw stream only (no YOLO)

- VLC: `vlc udp://@:1234`
- FFplay: `ffplay udp://0.0.0.0:1234`

## Notes

- Firewall: allow UDP port **1234** on the Mac.
- Webcam on board: if not `/dev/video2`, set `VIDEO_DEVICE` in `start_stream.sh`.
