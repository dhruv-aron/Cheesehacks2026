
## Demo Video

[Watch the Demo Video on YouTube](https://www.youtube.com/watch?v=AkkOrvXaqBg&t=31s)

## Inspiration

First responders often get into unforeseen situations where they are in danger but are unable to call for backup or help. We wanted a system that would be able to detect danger from a variety of inputs to gain a full understanding of the threat level and context, then contact authorities if the situation escalates. The application could also be used for assessing danger for anyone at the scene and acting quicker than human instinct.

---

## What It Does

Our model uses two primary inputs: video and audio, to assess risk by detecting weaponry, dangerous motions of individuals, and distinctive keywords that indicate a dangerous situation. By combining these signals, we generate an **Aggregate Risk Score**, a numerical reflection of how dangerous a situation is for an officer. If the system determines the situation exceeds a defined danger threshold, the software automatically contacts authorities through a phone call, providing key contextual details such as identified threats, detected weaponry, and relevant audio cues.

---

## How We Built It

We used the Arduino UNO Q connected to a webcam to capture audio and video for our on-system Python-based classification and identification models. Leveraging the UNO Q and parallel processing for audio and video streams, we achieved near real-time analysis. The UNO Q enables portability and communicates over WiFi for transmitting model inputs and results.

On the processing end, we run three separate models across two Python threads. One thread processes the video stream, performing pose detection, stance analysis, and object detection before outputting the annotated video feed. The second thread continuously transcribes conversation audio, searching for semantically relevant keywords that may indicate danger. These three models work together to calculate the Aggregate Risk Score in real time.

If the calculated danger level exceeds a preset threshold, an emergency dispatch call is made using Twilio. The call provides a summarized report of the situation based on both visual and audio cues. All of this information is displayed in our React.js frontend, which shows the live annotated video stream, real-time detection updates, and a prominently displayed danger level indicator. Using a REST-based architecture, we created seamless communication between the frontend and backend.

---

## Challenges We Ran Into

One of the biggest challenges was the limited processing power of our mobile hardware, the Arduino. With only 2 GB of RAM and constrained CPU resources, running multiple machine learning models locally required careful optimization. Because many classification and detection models are computationally intensive, we offloaded heavy processing tasks to a more powerful external system. This architecture better reflects real-world deployments, where on-field equipment communicates with centralized servers.

Another significant challenge involved weapon classification accuracy. Lightweight models frequently produced false positives, incorrectly identifying harmless objects as weapons and artificially inflating the risk score. To address this, we fine-tuned the parameters of an open-source YOLOv8 model to improve detection precision and reduce hallucinations.

---
