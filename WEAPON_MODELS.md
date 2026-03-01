# YOLOv8 Weapon Detection Models for Mac M4

All models below are **YOLOv8-nano** based (~6 MB, ~3M params). They run well on Mac M4 with **MPS** or CPU via Ultralytics.

---

## Best options (Hugging Face)

### 1. **Firearm only (gun)** — best accuracy for guns  
**Subh775/Firearm_Detection_Yolov8n**

| | |
|---|---|
| **Classes** | Gun (pistols, rifles, shotguns) |
| **mAP@50** | 89.0% |
| **Size** | 6.24 MB (`weights/best.pt`) |
| **Use when** | You only need gun detection. |

**Download:**
```bash
# Direct URL (save as weapon.pt)
curl -L -o weapon.pt "https://huggingface.co/Subh775/Firearm_Detection_Yolov8n/resolve/main/weights/best.pt"
```
**In code:** `model = YOLO("weapon.pt")`

---

### 2. **Multi-threat (gun + knife + explosive + grenade)** — best all-round  
**Subh775/Threat-Detection-YOLOv8n**

| | |
|---|---|
| **Classes** | Gun, Knife, Explosive, Grenade |
| **mAP@50** | 81.3% overall (e.g. 92.1% grenade) |
| **Size** | 6.25 MB (`weights/best.pt`) |
| **Use when** | You want gun, knife, and explosive-type threats in one model. |

**Download:**
```bash
curl -L -o weapon.pt "https://huggingface.co/Subh775/Threat-Detection-YOLOv8n/resolve/main/weights/best.pt"
```
**In code:** `model = YOLO("weapon.pt")` — filter to specific classes in your app if needed (e.g. only `knife`, `gun`).

---

### 3. **General weapon detection**  
**Hadi959/weapon-detection-yolov8**

| | |
|---|---|
| **Classes** | General weapons (see repo/data.yaml) |
| **Size** | 6.23 MB (`best.pt`) |
| **Use when** | You prefer this dataset/benchmark. |

**Download:**
```bash
curl -L -o weapon.pt "https://huggingface.co/Hadi959/weapon-detection-yolov8/resolve/main/best.pt"
```

---

## Using with `server.py` on Mac M4

1. Download one of the models above (e.g. save as `weapon.pt` in the project).
2. Run with that model:
   ```bash
   python3 server.py --model weapon.pt
   ```
3. The app uses **MPS** on M4 when available; no extra config.

**Filter to specific classes (e.g. knife only)**  
You can add a class filter in `server.py` (e.g. only pass `classes=[...]` to `model.predict()` for the COCO/threat class IDs you want), or use the Threat-Detection model and ignore unwanted classes in your logic.

---

## Summary

| Priority | Model | Best for |
|----------|--------|----------|
| **1** | **Threat-Detection-YOLOv8n** | Gun + knife + explosive + grenade in one model |
| **2** | **Firearm_Detection_Yolov8n** | Gun-only, highest mAP for firearms |
| **3** | **Hadi959/weapon-detection-yolov8** | General weapon detection |

All three are nano-sized and suitable for real-time use on Mac M4.
