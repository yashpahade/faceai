# ============================================
# FACE DETECTION TEST SCRIPT
# ============================================
"""
Face detection service test karne ke liye script
Backend complete hone se pehle test kar lo
"""

import cv2
import sys
from pathlib import Path

# Services import karo
sys.path.append(str(Path(__file__).parent))
from services.face_detector import FaceDetector
from services.face_processor import FaceProcessor

def test_face_detection():
    """Face detection service ka basic test"""
    
    print("="*50)
    print("FACE DETECTION SERVICE TEST")
    print("="*50)
    
    # 1. Detector initialize karo
    print("\n1. Initializing Face Detector...")
    detector = FaceDetector(method="insightface")
    print("✓ Detector initialized")
    
    # 2. Test image load karo (webcam se capture)
    print("\n2. Capturing test image from webcam...")
    cap = cv2.VideoCapture(0)  # Default camera
    
    if not cap.isOpened():
        print("✗ Camera not available!")
        print("Creating test image with drawn faces instead...")
        # Create test image
        test_image = 128 * np.ones((480, 640, 3), dtype=np.uint8)
    else:
        ret, test_image = cap.read()
        cap.release()
        
        if not ret:
            print("✗ Failed to capture image")
            return
        print("✓ Image captured")
    
    # 3. Image validate karo
    print("\n3. Validating image...")
    is_valid = FaceProcessor.validate_face_image(test_image)
    if not is_valid:
        print("✗ Invalid image")
        return
    print("✓ Image valid")
    
    # 4. Faces detect karo
    print("\n4. Detecting faces...")
    faces = detector.detect_faces(test_image, confidence_threshold=0.5)
    print(f"✓ Found {len(faces)} face(s)")
    
    # 5. Results show karo
    print("\n5. Detection Results:")
    for i, face in enumerate(faces):
        print(f"\n   Face {i+1}:")
        print(f"   - Bounding Box: {face['bbox']}")
        print(f"   - Confidence: {face['confidence']:.2f}")
        if face.get('landmarks'):
            print(f"   - Landmarks: {len(face['landmarks'])} points")
    
    # 6. Visualize result
    if len(faces) > 0:
        print("\n6. Drawing detection results...")
        result_image = detector.draw_faces(test_image, faces)
        
        # Save image
        output_path = "test_results.jpg"
        cv2.imwrite(output_path, result_image)
        print(f"✓ Result saved to {output_path}")
    
    print("\n" + "="*50)
    print("TEST COMPLETE!")
    print("="*50)

if __name__ == "__main__":
    import numpy as np
    test_face_detection()