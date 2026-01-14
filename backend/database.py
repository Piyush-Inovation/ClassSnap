import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "attendance.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Create students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        class_name TEXT,
        face_photo_path TEXT
    )
    """)
    
    # Create face_encodings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS face_encodings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        encoding TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    """)
    
    # Create attendance table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        date TEXT NOT NULL,
        status TEXT NOT NULL,
        confidence REAL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )
    """)
    
    # Try to add confidence column if it doesn't exist (migration for existing db)
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN confidence REAL")
    except sqlite3.OperationalError:
        # Column likely already exists
        pass

    # ---------------------------
    # TASK 8: AUTHENTICATION SCHEMA
    # ---------------------------
    
    # Create teachers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teachers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Add created_by to students
    try:
        cursor.execute("ALTER TABLE students ADD COLUMN created_by INTEGER")
    except sqlite3.OperationalError:
        pass

    # Add teacher_id to attendance
    try:
        cursor.execute("ALTER TABLE attendance ADD COLUMN teacher_id INTEGER")
    except sqlite3.OperationalError:
        pass
    
    # Seed default admin user if not exists
    cursor.execute("SELECT id FROM teachers WHERE username = 'admin'")
    if not cursor.fetchone():
        # We need bcrypt here. If it's not installed yet, this might fail unless we permit it to fail gently
        # or assume it's run after pip install.
        try:
            import bcrypt
            password = "password123"
            # Encode password to bytes, hash, then decode back to string for storage
            hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            cursor.execute("""
            INSERT INTO teachers (username, password_hash, name, email)
            VALUES (?, ?, ?, ?)
            """, ('admin', hashed, 'System Administrator', 'admin@school.com'))
            print("Default admin user created (admin/password123)")
        except ImportError:
            print("Warning: bcrypt not installed. Skipping admin user creation.")

    conn.commit()
    conn.close()
