#!/bin/bash
# Headless video + audio streaming - streams /dev/video2 and default mic to laptop via UDP
# Fill in LAPTOP_IP before use (e.g. 192.168.1.100)

LAPTOP_IP="10.136.19.164"
UDP_PORT="1234"
VIDEO_DEVICE="/dev/video2"
# Audio: ALSA capture device. hw:0,0 = Logitech BRIO mic (card 0). Card 1 = Arduino board audio.
# List capture devices: arecord -l. To disable audio set AUDIO_INPUT="".
AUDIO_INPUT="hw:0,0"

# Wait for network to be ready
sleep 10

# Build FFmpeg command: video from v4l2, audio from ALSA, mux to MPEG-TS over UDP
if [ -n "$AUDIO_INPUT" ]; then
  # Video + audio
  exec ffmpeg -f v4l2 -input_format yuyv422 -video_size 640x480 -framerate 30 \
    -i "$VIDEO_DEVICE" \
    -f alsa -i "$AUDIO_INPUT" \
    -c:v libx264 -preset ultrafast -tune zerolatency \
    -b:v 2M -maxrate 2M -bufsize 1M \
    -pix_fmt yuv420p -g 30 -keyint_min 30 \
    -c:a aac -b:a 128k -ar 48000 \
    -f mpegts -muxdelay 0 -muxpreload 0 \
    "udp://${LAPTOP_IP}:${UDP_PORT}?pkt_size=1316"
else
  # Video only (original behavior)
  exec ffmpeg -f v4l2 -input_format yuyv422 -video_size 640x480 -framerate 30 \
    -i "$VIDEO_DEVICE" \
    -c:v libx264 -preset ultrafast -tune zerolatency \
    -b:v 2M -maxrate 2M -bufsize 1M \
    -pix_fmt yuv420p -g 30 -keyint_min 30 \
    -f mpegts -muxdelay 0 -muxpreload 0 \
    "udp://${LAPTOP_IP}:${UDP_PORT}?pkt_size=1316"
fi
