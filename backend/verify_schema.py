import sqlite3
import sys

try:
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    print("=" * 70)
    print("DATABASE SCHEMA VERIFICATION")
    print("=" * 70)
    
    # Check teachers table
    print("\n1. TEACHERS TABLE:")
    cursor.execute("PRAGMA table_info(teachers)")
    teachers_cols = cursor.fetchall()
    for col in teachers_cols:
        print(f"   {col[1]} ({col[2]})")
    
    # Check students table
    print("\n2. STUDENTS TABLE:")
    cursor.execute("PRAGMA table_info(students)")
    students_cols = cursor.fetchall()
    has_created_by = False
    for col in students_cols:
        print(f"   {col[1]} ({col[2]})")
        if col[1] == 'created_by':
            has_created_by = True
    
    # Check attendance table
    print("\n3. ATTENDANCE TABLE:")
    cursor.execute("PRAGMA table_info(attendance)")
    attendance_cols = cursor.fetchall()
    has_teacher_id = False
    for col in attendance_cols:
        print(f"   {col[1]} ({col[2]})")
        if col[1] == 'teacher_id':
            has_teacher_id = True
    
    # Verify required columns
    print("\n" + "=" * 70)
    print("VERIFICATION RESULTS:")
    print("=" * 70)
    
    if len(teachers_cols) > 0:
        print("✓ Teachers table exists")
    else:
        print("✗ Teachers table missing")
    
    if has_created_by:
        print("✓ students.created_by column exists")
    else:
        print("✗ students.created_by column missing")
    
    if has_teacher_id:
        print("✓ attendance.teacher_id column exists")
    else:
        print("✗ attendance.teacher_id column missing")
    
    # Count records
    cursor.execute("SELECT COUNT(*) FROM teachers")
    teacher_count = cursor.fetchone()[0]
    print(f"\n📊 Teachers in database: {teacher_count}")
    
    cursor.execute("SELECT username, name FROM teachers")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]}")
    
    conn.close()
    print("\n" + "=" * 70)
    
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
