# test_register.py - Simple registration test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "backend"))

import cv2
import numpy as np
from services.face_detector import FaceDetector
from services.feature_extractor import FeatureExtractor

# Initialize
print("Loading models...")
detector = FaceDetector()
extractor = FeatureExtractor()

# Test image (webcam se capture)
print("Opening camera...")
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Camera not available, use image file instead")
    # Fallback - test image path
    test_image_path = input("Enter image path: ")
    img = cv2.imread(test_image_path)
    if img is None:
        print("Failed to load image. Exiting.")
        exit(1)
else:
    print("Press SPACE to capture, ESC to exit")
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to read from camera. Exiting.")
            cap.release()
            exit(1)
        cv2.imshow("Press SPACE", frame)
        key = cv2.waitKey(1)
        if key == 32:  # SPACE
            img = frame
            break
        elif key == 27:  # ESC
            cap.release()
            exit()
    cap.release()

if img is None:
    print("No image available. Exiting.")
    exit(1)

print(f"Image shape: {img.shape}")

# Detect faces
print("Detecting faces...")
faces = detector.detect_faces(img, confidence_threshold=0.3)
print(f"Found {len(faces)} faces")

if len(faces) > 0:
    face = faces[0]
    print(f"Face confidence: {face['confidence']}")
    print(f"Face bbox: {face['bbox']}")

    # Crop face
    face_crop = detector.preprocess_face(img, face['bbox'])
    print(f"Face crop shape: {face_crop.shape}")

    # Extract features
    print("Extracting features...")
    embedding = extractor.extract_features(face_crop)

    if embedding is not None:
        print(f"✓ SUCCESS! Embedding shape: {embedding.shape}")
        print(f"First 5 values: {embedding[:5]}")
    else:
        print("✗ Failed to extract features")
        print("Trying with resized image...")
        face_resized = cv2.resize(face_crop, (112, 112))
        embedding = extractor.extract_features(face_resized)

        if embedding is not None:
            print(f"✓ SUCCESS with resize!")
        else:
            print("✗ Still failed. Image quality issue.")
else:
    print("No faces detected!")
