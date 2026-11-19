# ============================================
# FAISS SERVICE TEST SCRIPT
# ============================================
"""
FAISS vector database ko test karne ke liye
Register, search aur verify operations test
"""

import numpy as np
from pathlib import Path
import sys
import cv2

sys.path.append(str(Path(__file__).parent))

from services.faiss_service import FAISSService
from services.faiss_manager import FAISSManager
from services.feature_extractor import FeatureExtractor
from services.face_detector import FaceDetector

def test_faiss_operations():
    """FAISS complete operations test"""

    print("="*60)
    print("FAISS VECTOR DATABASE TEST")
    print("="*60)

    # 1. FAISS service initialize karo
    print("\n1. Initializing FAISS service...")
    index_path = Path("../data/faiss_index.bin")

    faiss_manager = FAISSManager(index_path)
    stats = faiss_manager.get_system_stats()
    print(f"✓ FAISS initialized")
    print(f"   - Type: {stats['index_type']}")
    print(f"   - Dimension: {stats['vector_dimension']}")
    print(f"   - Existing vectors: {stats['total_vectors']}")

    # 2. Test vectors create karo (simulate face embeddings)
    print("\n2. Creating test face vectors...")

    # 5 different "faces" simulate karo
    test_faces = []

    for i in range(5):
        # Random vector (512-dim) with some pattern
        base_vector = np.random.randn(512).astype(np.float32)
        # Normalize karo
        base_vector = base_vector / np.linalg.norm(base_vector)

        test_faces.append({
            "name": f"Person_{i+1}",
            "vector": base_vector,
            "email": f"person{i+1}@example.com",
            "department": "Engineering"
        })

    print(f"✓ Created {len(test_faces)} test face vectors")

    # 3. Faces register karo
    print("\n3. Registering faces...")

    for face in test_faces:
        result = faiss_manager.register_face(
            face_vector=face["vector"],
            person_name=face["name"],
            additional_info={
                "email": face["email"],
                "department": face["department"]
            }
        )

        if result["success"]:
            print(f"   ✓ {face['name']} registered → ID: {result['face_id']}")
        else:
            print(f"   ✗ Failed to register {face['name']}")

    # 4. System stats check karo
    print("\n4. System statistics:")
    stats = faiss_manager.get_system_stats()
    print(f"   - Total registered: {stats['total_vectors']}")
    print(f"   - Memory usage: {stats['memory_usage']}")

    # 5. Face recognition test
    print("\n5. Testing face recognition...")

    # First person ka vector lo
    query_face = test_faces[0]["vector"]

    # Thoda noise add karo (real-world simulation)
    noise = np.random.randn(512).astype(np.float32) * 0.1
    query_face = query_face + noise
    query_face = query_face / np.linalg.norm(query_face)

    # Recognize karo
    result = faiss_manager.recognize_face(
        face_vector=query_face,
        threshold=0.5
    )

    if result["is_recognized"]:
        best = result["best_match"]
        print(f"   ✓ Recognized as: {best['name']}")
        print(f"   ✓ Confidence: {best['confidence']}%")
    else:
        print(f"   ✗ No match found")

    # 6. Multiple matches test
    print("\n6. Testing with lower threshold (more matches)...")

    result = faiss_manager.recognize_face(
        face_vector=query_face,
        threshold=0.3,
        max_results=3
    )

    print(f"   Total matches found: {result.get('total_matches', 0)}")
    for match in result.get("all_matches", []):
        print(f"   - {match['name']}: {match['confidence']}%")

    # 7. List all registered faces
    print("\n7. All registered faces:")
    all_faces = faiss_manager.list_all_faces()
    for face in all_faces:
        print(f"   - {face['face_id'][:20]}... → {face['name']}")

    print("\n" + "="*60)
    print("FAISS TEST COMPLETE!")
    print("="*60)

def test_with_real_camera():
    """
    Real camera se face capture karo aur FAISS test karo
    """
    print("\n" + "="*60)
    print("REAL CAMERA FAISS TEST")
    print("="*60)

    # Services initialize
    index_path = Path("../data/faiss_index.bin")
    faiss_manager = FAISSManager(index_path)
    detector = FaceDetector()
    extractor = FeatureExtractor()

    # Camera capture
    print("\nCapturing image (press SPACE to capture)...")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("✗ Camera not available")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow("Press SPACE to capture, ESC to exit", frame)
        key = cv2.waitKey(1)

        if key == 32:  # SPACE key
            # Face detect
            faces = detector.detect_faces(frame)

            if len(faces) == 0:
                print("No face detected!")
                continue

            print(f"\nDetected {len(faces)} face(s)")

            # Process first face
            for i, face in enumerate(faces[:1]):  # First face only
                # Crop face
                face_crop = detector.preprocess_face(frame, face['bbox'])

                # Extract features
                embedding = extractor.extract_features(face_crop)

                if embedding is not None:
                    print(f"\nRecognizing face {i+1}...")

                    # Recognize
                    result = faiss_manager.recognize_face(embedding)

                    if result["is_recognized"]:
                        print(f"✓ MATCH: {result['best_match']['name']}")
                        print(f"  Confidence: {result['best_match']['confidence']}%")
                    else:
                        print("✗ No match found")
                        print("  Register this face? (y/n): ", end="")
                        choice = input().lower()

                        if choice == 'y':
                            name = input("  Enter name: ")
                            reg_result = faiss_manager.register_face(
                                face_vector=embedding,
                                person_name=name
                            )

                            if reg_result["success"]:
                                print(f"  ✓ Registered as: {name}")
                            else:
                                print(f"  ✗ Registration failed")

        elif key == 27:  # ESC key
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    print("\nChoose test:")
    print("1. Basic FAISS test (simulated vectors)")
    print("2. Real camera test")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        test_faiss_operations()
    elif choice == "2":
        test_with_real_camera()
    else:
        print("Invalid choice")
