# ============================================
# FACE RECOGNITION SYSTEM - MAIN ENTRY POINT
# ============================================
"""
Ye main file hai jo saare components ko jodti hai.
Isse aap faces register kar sakte hain aur recognize kar sakte hain.
"""

import cv2
import os
import sys
from pathlib import Path
import numpy as np
import logging

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parent / "backend"))

from backend.services.pipeline import FaceProcessingPipeline
from backend.config import settings

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FaceApp:
    def __init__(self):
        print("Initializing Face Recognition System...")
        self.pipeline = FaceProcessingPipeline()
        print("System Ready!")

    def register_new_face(self):
        """Naya face register karne ke liye"""
        print("\n--- FACE REGISTRATION ---")
        name = input("Enter person name: ").strip()
        if not name:
            print("Error: Name cannot be empty")
            return

        source = input("Register from (1) Webcam or (2) Image Path: ")
        
        img = None
        if source == "1":
            img = self._capture_from_webcam("Position your face and press SPACE to capture")
        else:
            path = input("Enter image path: ").strip()
            img = cv2.imread(path)
            if img is None:
                print(f"Error: Could not read image from {path}")
                return

        if img is not None:
            print(f"Registering {name}...")
            result = self.pipeline.register_person(img, name)
            if result.get("success"):
                print(f"✓ Success! {name} registered with ID: {result['face_id']}")
            else:
                print(f"✗ Failed: {result.get('message')}")

    def recognize_faces(self):
        """Faces recognize karne ke liye"""
        print("\n--- FACE RECOGNITION ---")
        source = input("Recognize from (1) Webcam or (2) Image Path: ")
        
        if source == "1":
            print("Starting webcam recognition. Press 'q' to exit.")
            self._live_recognition()
        else:
            path = input("Enter image path: ").strip()
            img = cv2.imread(path)
            if img is None:
                print(f"Error: Could not read image from {path}")
                return
            
            print("Processing image...")
            results = self.pipeline.process_image(img, return_visualization=True)
            
            if results["faces_found"] > 0:
                print(f"Found {results['faces_found']} faces")
                for i, face in enumerate(results["faces"]):
                    if face.get("recognition") and face["recognition"].get("is_recognized"):
                        match = face["recognition"]["best_match"]
                        print(f"  Face {i+1}: {match['name']} ({match['confidence']}%)")
                    else:
                        print(f"  Face {i+1}: Unknown")
                
                # Show result
                cv2.imshow("Recognition Results", results["visualization"])
                print("Press any key on the image window to continue")
                cv2.waitKey(0)
                cv2.destroyAllWindows()
            else:
                print("No faces found in image")

    def list_faces(self):
        """Registered faces ki list dikhao"""
        faces = self.pipeline.faiss_manager.list_all_faces()
        print("\n--- REGISTERED FACES ---")
        if not faces:
            print("No faces registered yet.")
        else:
            for face in faces:
                print(f"ID: {face['face_id']} | Name: {face['name']} | Date: {face['registered_at']}")
        print(f"Total: {len(faces)}")

    def bulk_import_from_folder(self):
        """Import images from `data/faces`.
        - If `data/faces` contains subfolders, each subfolder name is used as the person name.
        - If images are directly under `data/faces`, the file stem before an underscore is used
          as the person name (e.g. alice_01.jpg -> name 'alice'). Otherwise the full stem
          is used as the name.
        """
        faces_dir = settings.DATA_DIR / "faces"
        if not faces_dir.exists():
            print(f"Faces folder not found: {faces_dir}")
            return

        allowed = settings.ALLOWED_EXTENSIONS
        added = 0
        skipped = 0

        for entry in faces_dir.iterdir():
            # Subfolder per person
            if entry.is_dir():
                person_name = entry.name
                for img_file in entry.iterdir():
                    if not img_file.is_file():
                        continue
                    if img_file.suffix.lower().lstrip('.') not in allowed:
                        skipped += 1
                        continue
                    img = cv2.imread(str(img_file))
                    if img is None:
                        skipped += 1
                        continue
                    res = self.pipeline.register_person(img, person_name)
                    if res.get('success'):
                        added += 1
                        print(f"Added: {person_name} <- {img_file.name} (id={res.get('face_id')})")
                    else:
                        skipped += 1
                        print(f"Skipped: {img_file.name} -> {res.get('message')}")

            # Single images in faces folder
            elif entry.is_file():
                if entry.suffix.lower().lstrip('.') not in allowed:
                    skipped += 1
                    continue

                # Infer name from filename
                stem = entry.stem
                if '_' in stem:
                    person_name = stem.split('_')[0]
                else:
                    person_name = stem

                img = cv2.imread(str(entry))
                if img is None:
                    skipped += 1
                    continue

                res = self.pipeline.register_person(img, person_name)
                if res.get('success'):
                    added += 1
                    print(f"Added: {person_name} <- {entry.name} (id={res.get('face_id')})")
                else:
                    skipped += 1
                    print(f"Skipped: {entry.name} -> {res.get('message')}")

        print(f"\nBulk import complete. Added: {added}, Skipped: {skipped}")

    def _capture_from_webcam(self, instruction):
        """Webcam se image capture karo"""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open webcam")
            return None

        print(instruction)
        captured_frame = None
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            cv2.imshow("Webcam - Press SPACE to Capture, ESC to Cancel", frame)
            key = cv2.waitKey(1)
            
            if key == 32: # SPACE
                captured_frame = frame
                break
            elif key == 27: # ESC
                break
        
        cap.release()
        cv2.destroyAllWindows()
        return captured_frame

    def _live_recognition(self):
        """Live webcam recognition loop"""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open webcam")
            return

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Process frame
            results = self.pipeline.process_image(frame, return_visualization=True)
            
            # Show frame
            if "visualization" in results:
                cv2.imshow("Live Face Recognition - Press 'q' to Quit", results["visualization"])
            else:
                cv2.imshow("Live Face Recognition - Press 'q' to Quit", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()

    def clear_all(self):
        """Database clear karo"""
        confirm = input("Are you sure you want to delete ALL registered faces? (y/N): ")
        if confirm.lower() == 'y':
            self.pipeline.faiss_manager.faiss.clear_all()
            print("Database cleared!")

def main():
    app = FaceApp()
    
    while True:
        print("\n=== FACE RECOGNITION SYSTEM ===")
        print("1. Register New Face")
        print("2. Recognize Faces")
        print("3. List Registered Faces")
        print("4. Clear Database")
        print("5. Bulk Import Faces from data/faces")
        print("6. Exit")
        
        choice = input("\nSelect an option: ")
        
        if choice == "1":
            app.register_new_face()
        elif choice == "2":
            app.recognize_faces()
        elif choice == "3":
            app.list_faces()
        elif choice == "4":
            app.clear_all()
        elif choice == "5":
            app.bulk_import_from_folder()
        elif choice == "6":
            print("Exiting...")
            break
        else:
            print("Invalid choice, try again.")

if __name__ == "__main__":
    main()
