#!/bin/bash
# Headless video streaming server - streams /dev/video2 to laptop via UDP
# Fill in LAPTOP_IP before use (e.g. 192.168.1.100)

LAPTOP_IP="10.136.19.164"
UDP_PORT="1234"
VIDEO_DEVICE="/dev/video2"

# Wait for network to be ready
sleep 10

# Stream with low-latency FFmpeg settings
# - ultrafast + zerolatency: minimal encoding delay
# - tune zerolatency: no buffering for live streaming
# - preset ultrafast: fastest encoding
# - muxdelay/muxpreload 0: reduce UDP muxer delay
exec ffmpeg -f v4l2 -input_format yuyv422 -video_size 640x480 -framerate 30 \
  -i "$VIDEO_DEVICE" \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -b:v 2M -maxrate 2M -bufsize 1M \
  -pix_fmt yuv420p -g 30 -keyint_min 30 \
  -f mpegts -muxdelay 0 -muxpreload 0 \
  "udp://${LAPTOP_IP}:${UDP_PORT}?pkt_size=1316"
