"""
Configuration settings for the AI Face Recognition Attendance System backend.

This module centralizes all configuration-related values so they can be
imported and used across the application.
"""

import os
from datetime import timedelta

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

    # JWT Configuration
    # Use the secure key generated
    JWT_SECRET_KEY = "b95e5fabd7f2cf5797a877eefda42acaf9a99c81d22e25d473157d0af06e40c7"
    
    # Use timedelta for expiration
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)


config = Config()