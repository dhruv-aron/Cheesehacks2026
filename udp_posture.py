import tensorflow as tf
import tensorflow_hub as hub
import cv2
import numpy as np
import time
import argparse
import os

model = hub.load("https://tfhub.dev/google/movenet/singlepose/lightning/4")
movenet = model.signatures['serving_default']

# Dictionary mapping joint names to their corresponding keypoint indices in MoveNet
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

def draw_keypoints(frame, keypoints, confidence_threshold):
    y, x, _ = frame.shape
    shaped = np.squeeze(np.multiply(keypoints, [y, x, 1]))
    for kp in shaped:
        ky, kx, kp_conf = kp
        if kp_conf > confidence_threshold:
            cv2.circle(frame, (int(kx), int(ky)), 5, (0, 255, 0), -1)

def draw_connections(frame, keypoints, edges, confidence_threshold):
    y, x, _ = frame.shape
    shaped = np.squeeze(np.multiply(keypoints, [y, x, 1]))
    for edge, _ in edges.items():
        p1, p2 = edge
        y1, x1, c1 = shaped[p1]
        y2, x2, c2 = shaped[p2]
        if (c1 > confidence_threshold) and (c2 > confidence_threshold):      
            cv2.line(frame, (int(x1), int(y1)), (int(x2), int(y2)), (255, 0, 0), 2)

def calculate_angle(a, b, c):
    a = np.array([a[1], a[0]])
    b = np.array([b[1], b[0]])
    c = np.array([c[1], c[0]])
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(radians * 180.0 / np.pi)
    if angle > 180.0:
        angle = 360.0 - angle
    return angle

def get_distance(p1, p2):
    """Calculate Euclidean distance between two keypoints [y, x, conf]."""
    return np.linalg.norm(np.array([p1[1], p1[0]]) - np.array([p2[1], p2[0]]))

def is_confident(confidence_threshold, *kpts):
    """Check if all provided keypoints are above the confidence threshold."""
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

    # Calculate a reference scale based on shoulder width to normalize distances
    # This helps account for the person being close or far from the camera
    if is_confident(confidence_threshold, left_shoulder, right_shoulder):
        shoulder_width = get_distance(left_shoulder, right_shoulder)
        if shoulder_width < 10:
            shoulder_width = 10 
    else:
        shoulder_width = 50 # Fallback scale

    # --- 1. Hands out of frame (Slightly Suspicious) ---
    if not is_confident(confidence_threshold, left_wrist):
        score += 10
        reasons.append("Left hand out of frame")
    if not is_confident(confidence_threshold, right_wrist):
        score += 10
        reasons.append("Right hand out of frame")

    # --- 2. Sudden Movements (Very Suspicious/Aggressive if large) ---
    if prev_kpts is not None:
        prev_left_wrist = prev_kpts[KEYPOINT_DICT['left_wrist']]
        prev_right_wrist = prev_kpts[KEYPOINT_DICT['right_wrist']]
        
        # We only check sudden movement if hands are in frame this frame and last frame
        if is_confident(confidence_threshold, left_wrist) and is_confident(confidence_threshold, prev_left_wrist):
            left_movement = get_distance(left_wrist, prev_left_wrist) / shoulder_width
            if left_movement > 0.8: # Must be a VERY sudden/fast movement
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

    # --- 3. Hand at waist (Suspicious) ---
    if is_confident(confidence_threshold, right_wrist, right_hip):
        if get_distance(right_wrist, right_hip) / shoulder_width < 0.8: 
            score += 20
            reasons.append("Right hand at waist")
            
    if is_confident(confidence_threshold, left_wrist, left_hip):
        if get_distance(left_wrist, left_hip) / shoulder_width < 0.8:
            score += 20
            reasons.append("Left hand at waist")

    # --- 4. Hands up near shoulders (Suspicious, could be fighting stance) ---
    if is_confident(confidence_threshold, left_wrist, left_shoulder):
        if left_wrist[0] < left_shoulder[0] + (0.5 * shoulder_width):
            score += 15
            reasons.append("Left hand raised")
            
    if is_confident(confidence_threshold, right_wrist, right_shoulder):
        if right_wrist[0] < right_shoulder[0] + (0.5 * shoulder_width):
            score += 15
            reasons.append("Right hand raised")

    # --- 5. Hands out (Suspicious, could be aiming) ---
    if is_confident(confidence_threshold, left_wrist, left_shoulder):
        if get_distance(left_wrist, left_shoulder) / shoulder_width > 1.2:
            score += 15
            reasons.append("Left hand extended")
            
    if is_confident(confidence_threshold, right_wrist, right_shoulder):
        if get_distance(right_wrist, right_shoulder) / shoulder_width > 1.2:
            score += 15
            reasons.append("Right hand extended")

    # --- 6. Hands Up / Palms Forward (Negative Weighting - Surrender) ---
    # Significant reduction if wrists are clearly above elbows (hands up position)
    if is_confident(confidence_threshold, left_wrist, left_elbow, left_shoulder) and \
       is_confident(confidence_threshold, right_wrist, right_elbow, right_shoulder):
       
        # wrists above elbows (lower Y value)
        if (left_wrist[0] < left_elbow[0]) and (right_wrist[0] < right_elbow[0]):
            score -= 50
            reasons.append("Hands up (Surrender)")
            # Clean up redundant alerts that triggered just because hands are high
            reasons = [r for r in reasons if "raised" not in r]

    # --- 7. Two hands together on one hip or out in shooting motion (Very Dangerous) ---
    if is_confident(confidence_threshold, left_wrist, right_wrist):
        hands_together = get_distance(left_wrist, right_wrist) / shoulder_width < 0.6
        if hands_together:
            # Check if on one hip
            on_left_hip = is_confident(confidence_threshold, left_hip) and get_distance(left_wrist, left_hip) / shoulder_width < 0.8 and get_distance(right_wrist, left_hip) / shoulder_width < 0.8
            on_right_hip = is_confident(confidence_threshold, right_hip) and get_distance(left_wrist, right_hip) / shoulder_width < 0.8 and get_distance(right_wrist, right_hip) / shoulder_width < 0.8
            
            if on_left_hip or on_right_hip:
                score += 80
                reasons.append("Two hands together on one hip (Very Dangerous)")
                
            # Check if shooting motion at shoulder level
            if is_confident(confidence_threshold, left_shoulder, right_shoulder):
                avg_shoulder_y = (left_shoulder[0] + right_shoulder[0]) / 2.0
                avg_wrist_y = (left_wrist[0] + right_wrist[0]) / 2.0
                
                at_shoulder_level = abs(avg_wrist_y - avg_shoulder_y) / shoulder_width < 0.5
                dist_from_left_shoulder = get_distance(left_wrist, left_shoulder) / shoulder_width
                dist_from_right_shoulder = get_distance(right_wrist, right_shoulder) / shoulder_width
                
                if at_shoulder_level and (dist_from_left_shoulder > 1.2 or dist_from_right_shoulder > 1.2):
                    score += 80
                    reasons.append("Two hands together in shooting motion (Very Dangerous)")

    # --- 8. Hands on head (Not dangerous) ---
    if is_confident(confidence_threshold, left_wrist, right_wrist, nose, left_shoulder, right_shoulder):
        if left_wrist[0] < left_shoulder[0] and right_wrist[0] < right_shoulder[0]:
            if get_distance(left_wrist, nose) / shoulder_width < 1.0 and get_distance(right_wrist, nose) / shoulder_width < 1.0:
                score -= 100
                reasons.append("Hands on head (Not dangerous)")
                reasons = [r for r in reasons if "raised" not in r and "extended" not in r and "Surrender" not in r]

    score = max(0, min(score, 100))
    return score, reasons

def main():
    parser = argparse.ArgumentParser(description="Police Officer Anomaly Detection with MoveNet")
    DEFAULT_VIDEO_SOURCE = os.environ.get("VIDEO_SOURCE", "udp://@:1234")
    parser.add_argument(
        "--source", "-s",
        default=DEFAULT_VIDEO_SOURCE,
        help="Video source: udp://@:1234, 0 (webcam), or path to file",
    )
    args = parser.parse_args()

    source = args.source
    if source.isdigit():
        source = int(source)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Error: Could not open video source: {source}")
        return

    print(f"Starting video stream from {source}. Press 'q' to quit.")
    
    current_danger_score = 0
    alpha = 0.2  
    prev_kpts = None
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        img = frame.copy()
        img = tf.expand_dims(img, axis=0)
        img = tf.image.resize_with_pad(img, 192, 192)
        input_image = tf.cast(img, dtype=tf.int32)
        
        outputs = movenet(input_image)
        keypoints = outputs['output_0'].numpy()
        
        confidence_threshold = 0.3
        
        # Make Calculations Based on Points
        y, x, _ = frame.shape
        shaped_kpts = np.squeeze(np.multiply(keypoints, [y, x, 1]))
        
        # Compute instantaneous score
        raw_score, reasons = calculate_danger_score(shaped_kpts, prev_kpts, confidence_threshold)
        
        # Update prev_kpts for the next frame
        prev_kpts = shaped_kpts
        
        # Smooth the score over time
        if raw_score > current_danger_score:
            current_danger_score = raw_score # Instantly spike up
        else:
            current_danger_score = current_danger_score * (1 - alpha) + raw_score * alpha # Slowly decay down
            
        # Draw skeleton and joints over the slightly darkened frame
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (x, y), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.3, frame, 0.7, 0)
        
        draw_connections(frame, keypoints, EDGES, confidence_threshold)
        draw_keypoints(frame, keypoints, confidence_threshold)
            
        # UI Overlay for Danger Score
        # Color dynamically shifts from green (safe) to red (danger)
        score_int = int(current_danger_score)
        color = (0, int(255 - (score_int * 2.55)), int(score_int * 2.55)) 
        
        cv2.putText(frame, f"Danger Score: {score_int}/100", 
                    (20, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3, cv2.LINE_AA)
        
        # Print the reasons on screen
        for i, reason in enumerate(reasons):
            cv2.putText(frame, f"- {reason}", 
                        (20, 90 + (i * 30)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2, cv2.LINE_AA)

        cv2.imshow('Police Officer Anomaly Detection', frame)
        
        if cv2.waitKey(10) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
