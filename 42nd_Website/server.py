from flask import Flask, request, jsonify, send_from_directory, session, redirect
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')

# IMPORTANT: in production set a secure secret key via environment variable
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-me')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'attendance_tracker.db')


def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()
    con.execute('''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        callsign TEXT NOT NULL,
        age INTEGER NOT NULL,
        timezone TEXT NOT NULL,
        steam_name TEXT NOT NULL,
        experience TEXT NOT NULL,
        availability TEXT NOT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    con.execute('''CREATE TABLE IF NOT EXISTS admins (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    con.commit()
    con.close()


def create_admin(username: str, password: str):
    """Create or replace an admin user with a hashed password."""
    password_hash = generate_password_hash(password)
    con = get_db()
    con.execute('REPLACE INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)',
                (username, password_hash, datetime.utcnow()))
    con.commit()
    con.close()


def verify_admin(username: str, password: str) -> bool:
    con = get_db()
    row = con.execute('SELECT password_hash FROM admins WHERE username = ?', (username,)).fetchone()
    con.close()
    if not row:
        return False
    return check_password_hash(row['password_hash'], password)


@app.route('/')
def index():
    return send_from_directory('.', 'Welcome_Page.html')


@app.route('/<path:filename>')
def serve_file(filename):
    return send_from_directory('.', filename)


@app.route('/api/apply', methods=['POST'])
def apply():
    data = request.get_json()

    required = ['callsign', 'age', 'timezone', 'steam_name', 'experience', 'availability', 'reason']
    for field in required:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'Missing required field: {field}'}), 400

    try:
        age = int(data['age'])
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Age must be a number.'}), 400

    if age < 18:
        return jsonify({'success': False, 'message': 'You must be at least 18 years old to apply.'}), 400

    con = get_db()
    con.execute(
        '''INSERT INTO applications (callsign, age, timezone, steam_name, experience, availability, reason)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (data['callsign'], age, data['timezone'], data['steam_name'],
         data['experience'], data['availability'], data['reason'])
    )
    con.commit()
    con.close()

    return jsonify({'success': True, 'message': 'Application submitted successfully. Welcome to the recruitment process, soldier.'})


@app.route('/api/applications', methods=['GET'])
def list_applications():
    # Protected endpoint: only accessible to logged-in admins
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    con = get_db()
    rows = con.execute('SELECT * FROM applications ORDER BY submitted_at DESC').fetchall()
    con.close()
    return jsonify([dict(row) for row in rows])


@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'success': False, 'message': 'Missing credentials'}), 400

    if verify_admin(username, password):
        session['admin'] = True
        session['admin_user'] = username
        return jsonify({'success': True, 'message': 'Login successful'})

    return jsonify({'success': False, 'message': 'Invalid username or password'}), 401


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin', None)
    session.pop('admin_user', None)
    return jsonify({'success': True, 'message': 'Logged out'})


@app.route('/admin')
def admin_index():
    if session.get('admin'):
        return redirect('/Admin_Dashboard.html')
    return redirect('/Admin_Login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/Admin_Login.html')
    return send_from_directory('.', 'Admin_Dashboard.html')


@app.route('/api/admin/me', methods=['GET'])
def admin_me():
    if not session.get('admin'):
        return jsonify({'success': False}), 401
    return jsonify({'success': True, 'username': session.get('admin_user', 'Admin')})


@app.route('/api/applications/<int:app_id>/status', methods=['PATCH'])
def update_application_status(app_id):
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json() or {}
    new_status = data.get('status')
    if new_status not in ('pending', 'approved', 'rejected'):
        return jsonify({'success': False, 'message': 'Invalid status'}), 400
    con = get_db()
    con.execute('UPDATE applications SET status = ? WHERE id = ?', (new_status, app_id))
    con.commit()
    con.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    init_db()
    print('42nd QRF Battalion  Web Server Starting')

    # Use gunicorn in production; Flask dev server locally
    import sys
    if '--production' in sys.argv:
        import gunicorn  # noqa: F401  verify it's installed
        print('Starting production server on 0.0.0.0:5000')
        # gunicorn is launched via command line, not from here
        # Run: gunicorn -w 2 -b 0.0.0.0:5000 server:app
    else:
        print('Visit http://localhost:5000')
        app.run(debug=True, port=5000)
