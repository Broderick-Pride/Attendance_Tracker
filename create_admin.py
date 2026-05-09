"""Helper script to create an admin user in the project's sqlite DB.

Usage:
    python create_admin.py username password

This script uses werkzeug.security.generate_password_hash to store a secure password hash.
"""
import sys
import os
import sqlite3
from werkzeug.security import generate_password_hash
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'attendance_tracker.db')

if len(sys.argv) < 3:
    print('Usage: python create_admin.py USERNAME PASSWORD')
    sys.exit(2)

username = sys.argv[1]
password = sys.argv[2]

if not username or not password:
    print('Username and password are required')
    sys.exit(2)

if not os.path.exists(DB_PATH):
    print('Database not found, initializing...')
    # Minimal init: create tables needed
    con = sqlite3.connect(DB_PATH)
    con.execute('''CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, password_hash TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    con.commit()
    con.close()

hash = generate_password_hash(password)
con = sqlite3.connect(DB_PATH)
con.execute('REPLACE INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)', (username, hash, datetime.utcnow()))
con.commit()
con.close()
print(f'Admin user "{username}" created/updated.')
