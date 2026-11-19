# ============================================
# FEATURE EXTRACTION TEST SCRIPT
# ============================================
"""
Feature extractor ko test karne ke liye
Real face se embedding nikal ke dekho
"""

import cv2
import numpy as np
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))

from services.face_detector import FaceDetector
from services.face_processor import FaceProcessor
from services.feature_extractor import FeatureExtractor, FaceQualityChecker

def test_feature_extraction():
    """Complete feature extraction pipeline test"""

    print("="*60)
    print("FEATURE EXTRACTION PIPELINE TEST")
    print("="*60)

    # 1. Services initialize karo
    print("\n1. Initializing services...")
    detector = FaceDetector(method="insightface")
    extractor = FeatureExtractor(model_type="insightface")
    print("✓ Services initialized")

    # 2. Camera se image capture karo
    print("\n2. Capturing test image...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("✗ Camera not available")
        print("Creating test image...")
        test_image = np.ones((480, 640, 3), dtype=np.uint8) * 128
        cv2.putText(
            test_image,
            "Camera Not Available",
            (50, 240),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 0, 0),
            2
        )
    else:
        ret, test_image = cap.read()
        cap.release()

        if not ret:
            print("✗ Failed to capture image")
            return
        print("✓ Image captured")

    # 3. Faces detect karo
    print("\n3. Detecting faces...")
    faces = detector.detect_faces(test_image)
    print(f"✓ Found {len(faces)} face(s)")

    if len(faces) == 0:
        print("✗ No faces found for testing")
        return

    # 4. Har face ke liye processing
    print("\n4. Processing detected faces...")

    for i, face in enumerate(faces):
        print(f"\n{'─'*40}")
        print(f"Face {i+1}:")

        # Face crop karo
        bbox = face['bbox']
        face_crop = detector.preprocess_face(test_image, bbox)

        # Quality check karo
        print("   Checking quality...")
        quality = FaceQualityChecker.check_quality(face_crop)

        print(f"   Quality: {'GOOD' if quality['is_usable'] else 'POOR'}")
        print(f"   Metrics: {quality['metrics']}")

        if quality['issues']:
            print(f"   Issues: {', '.join(quality['issues'])}")

        # Agar quality poor hai to improve karo
        if not quality['is_usable']:
            print("   Attempting quality improvement...")
            face_crop = FaceQualityChecker.improve_quality(face_crop)

        # Features extract karo
        print("   Extracting features...")
        embedding = extractor.extract_features(face_crop)

        if embedding is not None:
            print(f"   ✓ Embedding extracted")
            print(f"   Vector dimension: {embedding.shape[0]}")
            print(f"   Vector stats:")
            print(f"     - Mean: {np.mean(embedding):.4f}")
            print(f"     - Std:  {np.std(embedding):.4f}")
            print(f"     - Min:  {np.min(embedding):.4f}")
            print(f"     - Max:  {np.max(embedding):.4f}")

            # First 5 values show karo
            print(f"   First 5 values: {embedding[:5]}")
        else:
            print("   ✗ Failed to extract embedding")

    # 5. Compare karo agar multiple faces hai
    if len(faces) >= 2:
        print(f"\n{'─'*40}")
        print("5. Comparing face embeddings...")

        # Dono faces ke embeddings lo
        face1_crop = detector.preprocess_face(test_image, faces[0]['bbox'])
        face2_crop = detector.preprocess_face(test_image, faces[1]['bbox'])

        emb1 = extractor.extract_features(face1_crop)
        emb2 = extractor.extract_features(face2_crop)

        if emb1 is not None and emb2 is not None:
            # Similarity calculate karo
            cosine_sim = extractor.compare_faces(emb1, emb2, "cosine")
            euclidean_sim = extractor.compare_faces(emb1, emb2, "euclidean")

            print(f"   Cosine Similarity: {cosine_sim:.4f}")
            print(f"   Euclidean Similarity: {euclidean_sim:.4f}")
            print(f"   {'SAME PERSON' if cosine_sim > 0.7 else 'DIFFERENT PERSON'}")

    print(f"\n{'='*60}")
    print("TEST COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    test_feature_extraction()
