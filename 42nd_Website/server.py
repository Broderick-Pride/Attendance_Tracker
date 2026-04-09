from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import os

app = Flask(__name__, static_folder='.', static_url_path='')

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
    con.commit()
    con.close()


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
    except ValueError:
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
    con = get_db()
    rows = con.execute('SELECT * FROM applications ORDER BY submitted_at DESC').fetchall()
    con.close()
    return jsonify([dict(row) for row in rows])


if __name__ == '__main__':
    init_db()
    print('42nd QRF Battalion — Web Server Starting')

    # Use gunicorn in production (Linux/Oracle), Flask dev server locally
    import sys
    if '--production' in sys.argv:
        import gunicorn  # noqa: F401 — verify it's installed
        print('Starting production server on 0.0.0.0:5000')
        # gunicorn is launched via command line, not from here
        # Run: gunicorn -w 2 -b 0.0.0.0:5000 server:app
    else:
        print('Visit http://localhost:5000')
        app.run(debug=True, port=5000)
