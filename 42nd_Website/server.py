from flask import Flask, request, jsonify, send_from_directory, session, redirect
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__, static_folder='.', static_url_path='')

# IMPORTANT: in production set a secure secret key via environment variable
app.secret_key = os.environ.get('SECRET_KEY', 'dev-change-me')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'attendance_tracker.db')

SPREADSHEET_ID = '1hf-IE9YCxvfFGpjvbshvnk59ruPexYWA5qSFmTrdtJE'

# Column headers for the managed "Applications DB" sheet tab
SHEET_HEADERS = [
    'ID', 'Callsign', 'Discord/Steam', 'Age', 'Timezone',
    'Experience', 'Availability', 'Reason', 'Status', 'Submitted At', 'Source'
]

_sheet_cache = {'wb': None}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------

def _open_sheet():
    """
    Return (forms_ws, db_ws) where:
      forms_ws = Google Forms response tab (read-only)
      db_ws    = 'Applications DB' tab managed by this server

    Returns (None, None) if credentials.json is missing or Sheets is unreachable.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_path = os.environ.get(
            'GOOGLE_CREDENTIALS_PATH',
            os.path.join(os.path.dirname(__file__), 'credentials.json')
        )
        if not os.path.exists(creds_path):
            return None, None

        if _sheet_cache['wb'] is None:
            creds = Credentials.from_service_account_file(
                creds_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            gc = gspread.authorize(creds)
            _sheet_cache['wb'] = gc.open_by_key(SPREADSHEET_ID)

        wb = _sheet_cache['wb']
        forms_ws = wb.sheet1

        try:
            db_ws = wb.worksheet('Applications DB')
        except gspread.exceptions.WorksheetNotFound:
            db_ws = wb.add_worksheet(title='Applications DB', rows=2000, cols=len(SHEET_HEADERS))
            db_ws.append_row(SHEET_HEADERS)

        return forms_ws, db_ws

    except Exception as e:
        _sheet_cache['wb'] = None
        print(f'[Sheets] {e}')
        return None, None


def sheet_push_application(app_row: dict):
    """Append a new website application to the 'Applications DB' sheet tab."""
    _, db_ws = _open_sheet()
    if db_ws is None:
        return
    try:
        db_ws.append_row([
            app_row['id'],
            app_row['callsign'],
            app_row.get('steam_name', ''),
            app_row['age'],
            app_row['timezone'],
            app_row['experience'],
            app_row['availability'],
            app_row['reason'],
            app_row.get('status', 'pending'),
            str(app_row.get('submitted_at', '')),
            'website',
        ])
    except Exception as e:
        print(f'[Sheets] push error: {e}')


def sheet_update_status(app_id: int, new_status: str):
    """Find the row with matching ID in the DB tab and update its Status cell."""
    _, db_ws = _open_sheet()
    if db_ws is None:
        return
    try:
        cell = db_ws.find(str(app_id), in_column=1)
        if cell:
            # Status is column 9 (1-indexed, matching SHEET_HEADERS index 8)
            db_ws.update_cell(cell.row, 9, new_status)
    except Exception as e:
        print(f'[Sheets] status update error: {e}')


# ---------------------------------------------------------------------------
# Routes — file serving
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return send_from_directory('.', 'Welcome_Page.html')


@app.route('/<path:filename>')
def serve_file(filename):
    return send_from_directory('.', filename)


# ---------------------------------------------------------------------------
# Routes — public API
# ---------------------------------------------------------------------------

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
    cur = con.execute(
        '''INSERT INTO applications (callsign, age, timezone, steam_name, experience, availability, reason)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (data['callsign'], age, data['timezone'], data['steam_name'],
         data['experience'], data['availability'], data['reason'])
    )
    new_id = cur.lastrowid
    app_row = dict(con.execute('SELECT * FROM applications WHERE id = ?', (new_id,)).fetchone())
    con.commit()
    con.close()

    sheet_push_application(app_row)

    return jsonify({'success': True, 'message': 'Application submitted successfully. Welcome to the recruitment process, soldier.'})


# ---------------------------------------------------------------------------
# Routes — admin auth
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Routes — admin API
# ---------------------------------------------------------------------------

@app.route('/api/admin/me', methods=['GET'])
def admin_me():
    if not session.get('admin'):
        return jsonify({'success': False}), 401
    return jsonify({'success': True, 'username': session.get('admin_user', 'Admin')})


@app.route('/api/applications', methods=['GET'])
def list_applications():
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    con = get_db()
    rows = con.execute('SELECT * FROM applications ORDER BY submitted_at DESC').fetchall()
    con.close()
    return jsonify([dict(row) for row in rows])


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
    sheet_update_status(app_id, new_status)
    return jsonify({'success': True})


@app.route('/api/sync-from-sheet', methods=['POST'])
def sync_from_sheet():
    """
    Read the Google Forms response tab and import any rows not already in the DB.
    Deduplication key: submitted_at (Google Forms timestamps are unique per submission).

    Column mapping from the Google Form:
      0  Timestamp          -> submitted_at
      1  Discord Name       -> steam_name  (closest equivalent)
      2  Trooper name       -> callsign
      3  Age                -> age
      4  EST okay?          -> timezone (set to 'EST')
      5  Arma 3 hours       -> experience  (+ armor interest appended)
      6  How did you hear   -> part of reason
      7  Role Requested     -> part of reason
      8  Armor interest     -> appended to experience
      9  Attend Saturdays   -> part of availability
      10 Days Available     -> availability
      11 Comments           -> part of reason
    """
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    forms_ws, _ = _open_sheet()
    if forms_ws is None:
        return jsonify({
            'success': False,
            'message': 'Google Sheets not configured — add credentials.json to 42nd_Website/'
        }), 503

    try:
        all_rows = forms_ws.get_all_values()
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

    if len(all_rows) < 2:
        return jsonify({'success': True, 'imported': 0, 'skipped': 0})

    con = get_db()
    imported = 0
    skipped = 0

    for row in all_rows[1:]:
        while len(row) < 12:
            row.append('')

        timestamp  = row[0].strip()
        discord    = row[1].strip()
        trooper    = row[2].strip()
        age_raw    = row[3].strip()
        arma_hours = row[5].strip()
        how_heard  = row[6].strip()
        roles      = row[7].strip()
        armor      = row[8].strip()
        attend_sat = row[9].strip()
        days_avail = row[10].strip()
        comments   = row[11].strip()

        if not timestamp or not trooper:
            continue

        exists = con.execute(
            'SELECT id FROM applications WHERE submitted_at = ?', (timestamp,)
        ).fetchone()
        if exists:
            skipped += 1
            continue

        try:
            age = int(''.join(c for c in age_raw if c.isdigit()) or '0')
        except Exception:
            age = 0

        experience = f'Arma 3 hours: {arma_hours}'
        if armor:
            experience += f' | Armor interest: {armor}'

        availability = f'Attend Saturdays: {attend_sat}'
        if days_avail:
            availability += f' | Days: {days_avail}'

        parts = []
        if roles:
            parts.append(f'Roles: {roles}')
        if how_heard:
            parts.append(f'Heard from: {how_heard}')
        if comments:
            parts.append(f'Comments: {comments}')
        reason = ' | '.join(parts) or '(imported from Google Form)'

        con.execute(
            '''INSERT INTO applications
               (callsign, age, timezone, steam_name, experience, availability, reason, status, submitted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (trooper, age, 'EST', discord, experience, availability, reason, 'pending', timestamp)
        )
        imported += 1

    con.commit()
    con.close()
    return jsonify({'success': True, 'imported': imported, 'skipped': skipped})


@app.route('/api/sync-to-sheet', methods=['POST'])
def sync_to_sheet():
    """
    Rebuild the 'Applications DB' sheet tab from the SQLite database.
    This overwrites the tab contents with the full current DB state.
    """
    if not session.get('admin'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    _, db_ws = _open_sheet()
    if db_ws is None:
        return jsonify({
            'success': False,
            'message': 'Google Sheets not configured — add credentials.json to 42nd_Website/'
        }), 503

    try:
        con = get_db()
        apps = con.execute('SELECT * FROM applications ORDER BY id').fetchall()
        con.close()

        rows = [SHEET_HEADERS]
        for a in apps:
            rows.append([
                a['id'], a['callsign'], a['steam_name'], a['age'],
                a['timezone'], a['experience'], a['availability'],
                a['reason'], a['status'] or 'pending', str(a['submitted_at']), 'db'
            ])

        db_ws.clear()
        db_ws.update('A1', rows)
        return jsonify({'success': True, 'synced': len(apps)})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_db()
    print('42nd Airborne Division Web Server Starting')

    import sys
    if '--production' in sys.argv:
        import importlib.util
        if importlib.util.find_spec('gunicorn') is None:
            print('ERROR: gunicorn not installed. Run: pip install gunicorn')
            sys.exit(1)
        print('Starting production server on 0.0.0.0:5000')
    else:
        print('Visit http://localhost:5000')
        app.run(debug=True, port=5000)
