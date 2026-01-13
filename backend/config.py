"""
Configuration settings for the AI Face Recognition Attendance System backend.

This module centralizes all configuration-related values so they can be
imported and used across the application.
"""

import os

# Base directory of the backend project (directory where this file lives)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    """
    Base configuration class.
    You can later extend this (e.g., DevelopmentConfig, ProductionConfig) if needed.
    """

    # Default port the Flask app will run on
    PORT = int(os.getenv("PORT", 5000))

    # Folder for temporary image uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

    # Folder for storing student face images
    STUDENT_FACES_FOLDER = os.path.join(BASE_DIR, "student_faces")

    # Maximum allowed payload (file) size in bytes (10 MB)
    # Flask expects this in bytes for MAX_CONTENT_LENGTH
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB

    # Allowed file extensions for uploaded images
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}


config = Config()