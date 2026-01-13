from deepface import DeepFace
import os
import json

# Use the existing image
IMAGE_PATH = os.path.join("uploads", "20260113_100907.jpg")

try:
    if os.path.exists(IMAGE_PATH):
        print(f"Analyzing {IMAGE_PATH}...")
        objs = DeepFace.represent(img_path=IMAGE_PATH, model_name="VGG-Face", enforce_detection=False)
        if objs and len(objs) > 0:
            print("First face keys:", objs[0].keys())
            print("Facial area keys:", objs[0]['facial_area'].keys())
        else:
            print("No faces found.")
    else:
        print("Image not found.")
except Exception as e:
    print(f"Error: {e}")
