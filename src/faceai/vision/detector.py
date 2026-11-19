"""
SCRFD face detector (InsightFace `det_10g.onnx`), pure numpy post-processing.

Detector ka output seedha boxes nahi hota. Model image ko 3 scales (stride 8/16/32) pe grid mein
baant'ta hai. Har grid cell (anchor) pe 2 anchors, aur har anchor ke liye predict karta hai:
  - score:  yahan face hai? (0..1)
  - bbox:   anchor center se left/top/right/bottom ki DOORI (distance), stride units mein
  - kps:    5 landmarks ka anchor center se offset
Humein ye "decode" karna padta hai -> phir NMS (overlapping duplicate boxes hatao).
"""

import cv2
import numpy as np
import onnxruntime as ort

from faceai.vision.types import DetectedFace

STRIDES = (8, 16, 32)
NUM_ANCHORS = 2


class SCRFDDetector:
    def __init__(
        self, session: ort.InferenceSession, input_size: int = 640, nms_threshold: float = 0.4
    ):
        self.session = session
        self.input_size = input_size
        self.nms_threshold = nms_threshold
        self.input_name = session.get_inputs()[0].name
        self.output_names = [o.name for o in session.get_outputs()]
        if len(self.output_names) != 9:
            raise ValueError(
                f"expected SCRFD with 9 outputs (scores/bbox/kps x3), got "
                f"{len(self.output_names)}"
            )
        self._anchor_cache: dict[tuple[int, int, int], np.ndarray] = {}

    # ---------- public ----------
    def detect(self, image_bgr: np.ndarray, threshold: float = 0.5) -> list[DetectedFace]:
        blob, scale = self._preprocess(image_bgr)
        outputs = self.session.run(self.output_names, {self.input_name: blob})
        boxes, kps, scores = self._decode(outputs, threshold)
        if len(scores) == 0:
            return []
        boxes /= scale
        kps /= scale
        keep = _nms(boxes, scores, self.nms_threshold)
        order = sorted(keep, key=lambda i: -scores[i])
        return [DetectedFace(bbox=boxes[i], kps=kps[i], det_score=float(scores[i])) for i in order]

    # ---------- internals ----------
    def _preprocess(self, img: np.ndarray) -> tuple[np.ndarray, float]:
        """Aspect ratio rakhte hue resize, bottom/right pe black padding -> square input."""
        size = self.input_size
        h, w = img.shape[:2]
        scale = size / max(h, w)
        nh, nw = int(round(h * scale)), int(round(w * scale))
        canvas = np.zeros((size, size, 3), dtype=np.uint8)
        canvas[:nh, :nw] = cv2.resize(img, (nw, nh))
        # (x - 127.5) / 128, BGR->RGB, HWC->NCHW  (training ke time yahi normalization tha)
        blob = cv2.dnn.blobFromImage(
            canvas, 1.0 / 128, (size, size), (127.5, 127.5, 127.5), swapRB=True
        )
        return blob, scale

    def _anchor_centers(self, h: int, w: int, stride: int) -> np.ndarray:
        key = (h, w, stride)
        if key not in self._anchor_cache:
            grid = np.stack(np.mgrid[:h, :w][::-1], axis=-1).astype(np.float32)  # (h, w, 2) x,y
            centers = (grid * stride).reshape(-1, 2)
            self._anchor_cache[key] = np.repeat(centers, NUM_ANCHORS, axis=0)
        return self._anchor_cache[key]

    def _decode(self, outputs: list[np.ndarray], threshold: float):
        all_boxes, all_kps, all_scores = [], [], []
        fmc = len(STRIDES)
        for i, stride in enumerate(STRIDES):
            scores = outputs[i].reshape(-1)
            bbox_d = outputs[i + fmc].reshape(-1, 4) * stride
            kps_d = outputs[i + 2 * fmc].reshape(-1, 10) * stride
            fh = fw = self.input_size // stride
            centers = self._anchor_centers(fh, fw, stride)

            pos = np.where(scores >= threshold)[0]
            if len(pos) == 0:
                continue
            c = centers[pos]
            d = bbox_d[pos]
            boxes = np.stack(
                [c[:, 0] - d[:, 0], c[:, 1] - d[:, 1], c[:, 0] + d[:, 2], c[:, 1] + d[:, 3]],
                axis=-1,
            )
            k = kps_d[pos].reshape(-1, 5, 2) + c[:, None, :]
            all_boxes.append(boxes)
            all_kps.append(k)
            all_scores.append(scores[pos])

        if not all_scores:
            return np.empty((0, 4)), np.empty((0, 5, 2)), np.empty((0,))
        return (
            np.concatenate(all_boxes).astype(np.float32),
            np.concatenate(all_kps).astype(np.float32),
            np.concatenate(all_scores).astype(np.float32),
        )


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_threshold: float) -> list[int]:
    """Non-Maximum Suppression: ek face pe kai overlapping boxes -> sirf best wala rakho."""
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1) * np.maximum(0.0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_threshold]
    return keep
