import os

import json

from openai import OpenAI as GroqOpenAI

import hashlib

import secrets

import re

import threading

import time

import io

import html

from urllib import request as urllib_request, error as urllib_error, parse as urllib_parse

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None

from flask import Flask, request, jsonify, render_template, redirect, url_for, session, send_from_directory, make_response

from werkzeug.utils import secure_filename

from werkzeug.security import generate_password_hash, check_password_hash

from flask_cors import CORS



# ─── Load environment variables (.env in dev, Railway env panel in prod) ───

try:

    from dotenv import load_dotenv

    load_dotenv()

except ImportError:

    pass



# ─── Database adapter (replaces sqlite3 with psycopg2 for Supabase Postgres) ───

import db as _db



# ─── File storage adapter (Supabase Storage, falls back to local disk) ───

import storage as _storage
import seed_assessments_pg

app = Flask(__name__, template_folder='.', static_folder='.')

app.secret_key = os.getenv('SECRET_KEY', 'aha_psy_CHANGE_ME_IN_RAILWAY_prod_secret_2024')

_IS_VERCEL = bool(os.getenv('VERCEL') or os.getenv('VERCEL_ENV'))
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', '/tmp/uploads' if _IS_VERCEL else 'uploads')

try:
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
except OSError:
    UPLOAD_FOLDER = '/tmp/uploads'
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

APP_BASE_URL = os.getenv('APP_BASE_URL', 'https://aha-psychological-service.vercel.app').rstrip('/')
EAT = ZoneInfo('Africa/Addis_Ababa') if ZoneInfo else timezone(timedelta(hours=3))



# ─── CORS: allow Vercel frontend to call Railway backend ───

CORS(app, supports_credentials=True, origins=[
    'http://localhost:5000',
    'http://127.0.0.1:5000',
    'http://localhost:8000',
    'https://*.vercel.app',
    'https://web-production-0b7ca.up.railway.app',
    os.getenv('FRONTEND_URL', ''),
])



CLINICAL_AI_MODEL = 'llama-3.3-70b-versatile'

TELEGRAM_BOT_USERNAME = os.getenv('TELEGRAM_BOT_USERNAME', 'Aha_Psychological_Service_Bot').strip()

TELEGRAM_POLLING_ACTIVE = False

os.environ.setdefault('TELEGRAM_BOT_TOKEN', '8814921367:AAEsa9O2v_qzGU7HF5zn6ehX7gc17zwNhpE')



# ─────────────────────────────────────────────

# DATABASE INITIALIZATION

# ─────────────────────────────────────────────

def init_db():

    with _db.connect() as conn:

        c = conn.cursor()



        # ── Legacy tables (keep working) ──

        c.execute('''CREATE TABLE IF NOT EXISTS slides (

            id SERIAL PRIMARY KEY,

            image_path TEXT NOT NULL, headline TEXT, summary TEXT,

            alignment TEXT DEFAULT 'center', button_name TEXT, button_link TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS org_members (

            id SERIAL PRIMARY KEY,

            name TEXT NOT NULL, role TEXT NOT NULL, photo_path TEXT,

            parent_id INTEGER, node_type TEXT DEFAULT 'normal',

            sort_order INTEGER DEFAULT 0, summary TEXT)''')



        # ── Users & Auth ──

        c.execute('''CREATE TABLE IF NOT EXISTS users (

            id SERIAL PRIMARY KEY,

            username TEXT UNIQUE NOT NULL,

            email TEXT,

            password_hash TEXT NOT NULL,

            role TEXT NOT NULL DEFAULT 'receptionist',

            full_name TEXT,

            phone TEXT,

            specialization TEXT,

            languages TEXT DEFAULT 'English',

            gender TEXT,

            max_caseload INTEGER DEFAULT 20,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            is_active INTEGER DEFAULT 1,

            last_login TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (

            id SERIAL PRIMARY KEY,

            user_id INTEGER, action TEXT, resource TEXT,

            detail TEXT, timestamp TEXT DEFAULT CURRENT_TIMESTAMP,

            ip_address TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS app_settings (

            key TEXT PRIMARY KEY,

            value TEXT

        )''')



        # ── Clients ──

        c.execute('''CREATE TABLE IF NOT EXISTS clients (

            id SERIAL PRIMARY KEY,

            full_name TEXT NOT NULL,

            date_of_birth TEXT,

            gender TEXT,

            phone TEXT,

            email TEXT,

            address TEXT,

            emergency_contact_name TEXT,

            emergency_contact_phone TEXT,

            registration_date TEXT DEFAULT CURRENT_TIMESTAMP,

            status TEXT DEFAULT 'registered',

            assigned_therapist_id INTEGER,

            language_pref TEXT DEFAULT 'English',

            therapist_gender_pref TEXT DEFAULT 'No Preference',

            intake_source TEXT DEFAULT 'walk-in',

            risk_level TEXT DEFAULT 'low',

            notes TEXT,

            client_code TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS client_journey (

            id SERIAL PRIMARY KEY,

            client_id INTEGER NOT NULL,

            stage TEXT NOT NULL,

            changed_by INTEGER,

            changed_at TEXT DEFAULT CURRENT_TIMESTAMP,

            notes TEXT)''')



        # ── Intake & Screening ──

        c.execute('''CREATE TABLE IF NOT EXISTS intake_forms (

            id SERIAL PRIMARY KEY,

            client_id INTEGER,

            submission_date TEXT DEFAULT CURRENT_TIMESTAMP,

            concerns TEXT,

            therapy_pref TEXT,

            modality_pref TEXT,

            has_prior_therapy INTEGER DEFAULT 0,

            prior_therapy_notes TEXT,

            referral_source TEXT,

            additional_notes TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS screening_responses (

            id SERIAL PRIMARY KEY,

            client_id INTEGER,

            questionnaire_type TEXT,

            responses_json TEXT,

            total_score INTEGER,

            severity_level TEXT,

            risk_flags_json TEXT,

            submitted_at TEXT DEFAULT CURRENT_TIMESTAMP)''')



        c.execute('''CREATE TABLE IF NOT EXISTS risk_alerts (

            id SERIAL PRIMARY KEY,

            client_id INTEGER,

            alert_type TEXT,

            severity TEXT,

            description TEXT,

            triggered_at TEXT DEFAULT CURRENT_TIMESTAMP,

            resolved_by INTEGER,

            resolved_at TEXT,

            is_active INTEGER DEFAULT 1)''')



        # ── Scheduling ──

        c.execute('''CREATE TABLE IF NOT EXISTS rooms (

            id SERIAL PRIMARY KEY,

            name TEXT NOT NULL,

            code TEXT UNIQUE,

            color TEXT DEFAULT '#043069',

            is_active INTEGER DEFAULT 1,

            sort_order INTEGER DEFAULT 0,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')



        c.execute('''CREATE TABLE IF NOT EXISTS appointments (

            id SERIAL PRIMARY KEY,

            client_id INTEGER,

            therapist_id INTEGER,

            room_id INTEGER,

            start_time TEXT,

            end_time TEXT,

            type TEXT DEFAULT 'individual',

            status TEXT DEFAULT 'scheduled',

            location TEXT DEFAULT 'In-Person',

            notes TEXT,

            created_by INTEGER,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            recurrence_rule TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS appointment_history (

            id SERIAL PRIMARY KEY,

            appointment_id INTEGER,

            action TEXT,

            performed_by INTEGER,

            reason TEXT,

            timestamp TEXT DEFAULT CURRENT_TIMESTAMP)''')



        # ── Clinical ──

        c.execute('''CREATE TABLE IF NOT EXISTS session_notes (

            id SERIAL PRIMARY KEY,

            appointment_id INTEGER,

            therapist_id INTEGER,

            client_id INTEGER,

            note_type TEXT DEFAULT 'progress',

            content TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS treatment_plans (

            id SERIAL PRIMARY KEY,

            client_id INTEGER,

            therapist_id INTEGER,

            goals TEXT,

            interventions TEXT,

            review_date TEXT,

            status TEXT DEFAULT 'active',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')



        c.execute('''CREATE TABLE IF NOT EXISTS referrals (

            id SERIAL PRIMARY KEY,

            client_id INTEGER,

            from_therapist_id INTEGER,

            to_therapist_id INTEGER,

            reason TEXT,

            status TEXT DEFAULT 'pending',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')



        # ── Finance ──

        c.execute('''CREATE TABLE IF NOT EXISTS services (

            id SERIAL PRIMARY KEY,

            name TEXT NOT NULL,

            description TEXT,

            duration_minutes INTEGER DEFAULT 60,

            price REAL DEFAULT 0.0,

            is_active INTEGER DEFAULT 1)''')



        c.execute('''CREATE TABLE IF NOT EXISTS invoices (

            id SERIAL PRIMARY KEY,

            client_id INTEGER,

            service_id INTEGER,

            amount REAL,

            issue_date TEXT DEFAULT CURRENT_TIMESTAMP,

            due_date TEXT,

            status TEXT DEFAULT 'pending',

            notes TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS payments (

            id SERIAL PRIMARY KEY,

            invoice_id INTEGER,

            client_id INTEGER,

            amount_paid REAL,

            payment_method TEXT DEFAULT 'cash',

            payment_date TEXT DEFAULT CURRENT_TIMESTAMP,

            received_by INTEGER,

            notes TEXT)''')



        # ── Communications ──

        c.execute('''CREATE TABLE IF NOT EXISTS messages (

            id SERIAL PRIMARY KEY,

            sender_id INTEGER,

            recipient_id INTEGER,

            client_id INTEGER,

            subject TEXT,

            body TEXT,

            channel TEXT DEFAULT 'internal',

            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,

            read_at TEXT,

            is_read INTEGER DEFAULT 0)''')



        # â”€â”€ Dynamic Assessments â”€â”€

        c.execute('''CREATE TABLE IF NOT EXISTS assessment_templates (

            id SERIAL PRIMARY KEY,

            name TEXT NOT NULL,

            slug TEXT UNIQUE,

            description TEXT,

            form_language TEXT DEFAULT 'English',

            is_public INTEGER DEFAULT 1,

            is_active INTEGER DEFAULT 1,

            created_by INTEGER,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,

            updated_at TEXT,

            config_json TEXT)''')



        c.execute('''CREATE TABLE IF NOT EXISTS assessment_questions (

            id SERIAL PRIMARY KEY,

            template_id INTEGER NOT NULL,

            question_key TEXT,

            label_en TEXT,

            label_am TEXT,

            question_type TEXT DEFAULT 'text',

            required INTEGER DEFAULT 0,

            options_json TEXT,

            helper_text TEXT,

            sort_order INTEGER DEFAULT 0,

            scoring_json TEXT,

            logic_json TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')



        c.execute('''CREATE TABLE IF NOT EXISTS assessment_submissions (

            id SERIAL PRIMARY KEY,

            template_id INTEGER NOT NULL,

            client_id INTEGER,

            appointment_id INTEGER,

            source TEXT DEFAULT 'public',

            responses_json TEXT,

            structured_content TEXT,

            short_summary TEXT,

            detailed_summary TEXT,

            created_by INTEGER,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')



        # â”€â”€ Telegram integration â”€â”€

        c.execute('''CREATE TABLE IF NOT EXISTS telegram_link_codes (

            id SERIAL PRIMARY KEY,

            user_id INTEGER NOT NULL,

            code TEXT UNIQUE NOT NULL,

            role TEXT,

            created_by INTEGER,

            expires_at TEXT,

            used_at TEXT,

            telegram_chat_id TEXT,

            telegram_username TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')



        c.execute('''CREATE TABLE IF NOT EXISTS telegram_events (

            id SERIAL PRIMARY KEY,

            user_id INTEGER,

            event_type TEXT,

            payload_json TEXT,

            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,

            delivery_status TEXT DEFAULT 'pending')''')



        # â”€â”€ Extra fields for richer workflows â”€â”€

        ensure_column(conn, 'users', 'telegram_chat_id', 'TEXT')

        ensure_column(conn, 'users', 'telegram_username', 'TEXT')

        ensure_column(conn, 'users', 'telegram_linked_at', 'TEXT')

        ensure_column(conn, 'clients', 'intake_json', 'TEXT')

        ensure_column(conn, 'intake_forms', 'personal_json', 'TEXT')

        ensure_column(conn, 'intake_forms', 'issue_json', 'TEXT')

        ensure_column(conn, 'intake_forms', 'form_language', 'TEXT')

        ensure_column(conn, 'intake_forms', 'preferred_appointment_date', 'TEXT')

        ensure_column(conn, 'intake_forms', 'preferred_appointment_time', 'TEXT')

        ensure_column(conn, 'intake_forms', 'assessment_json', 'TEXT')

        ensure_column(conn, 'appointments', 'cancel_reason', 'TEXT')

        ensure_column(conn, 'appointments', 'change_reason', 'TEXT')

        ensure_column(conn, 'appointments', 'change_scope', 'TEXT')

        ensure_column(conn, 'appointments', 'cancelled_by', 'INTEGER')

        ensure_column(conn, 'appointments', 'updated_at', 'TEXT')

        ensure_column(conn, 'appointments', 'room_id', 'INTEGER')

        ensure_column(conn, 'session_notes', 'structured_content', 'TEXT')

        ensure_column(conn, 'session_notes', 'short_summary', 'TEXT')

        

        c.execute('''CREATE TABLE IF NOT EXISTS screening_links (

            id SERIAL PRIMARY KEY,

            token TEXT UNIQUE NOT NULL,

            therapist_id INTEGER NOT NULL,

            template_id INTEGER NOT NULL,

            client_id INTEGER,

            expires_at TEXT,

            used_at TEXT,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP

        )''')

        ensure_column(conn, 'session_notes', 'ai_summary', 'TEXT')

        ensure_column(conn, 'session_notes', 'supervisor_response', 'TEXT')

        ensure_column(conn, 'session_notes', 'supervisor_action', 'TEXT')

        ensure_column(conn, 'assessment_templates', 'category', 'TEXT')

        ensure_column(conn, 'assessment_templates', 'tags', 'TEXT')

        ensure_column(conn, 'assessment_templates', 'published', 'INTEGER DEFAULT 0')

        ensure_column(conn, 'assessment_templates', 'version', 'INTEGER DEFAULT 1')

        ensure_column(conn, 'assessment_templates', 'author', 'TEXT')



        conn.commit()



        # ── Seed default admin ──

        existing = c.execute('SELECT id FROM users WHERE username=?', ('admin',)).fetchone()

        if not existing:

            c.execute('''INSERT INTO users (username, email, password_hash, role, full_name)

                         VALUES (?,?,?,?,?)''',

                      ('admin', 'admin@ahapsych.com',

                       generate_password_hash('admin123'),

                       'admin', 'System Administrator'))



        # ── Seed demo receptionist ──

        existing2 = c.execute('SELECT id FROM users WHERE username=?', ('reception',)).fetchone()

        if not existing2:

            c.execute('''INSERT INTO users (username, email, password_hash, role, full_name)

                         VALUES (?,?,?,?,?)''',

                      ('reception', 'reception@ahapsych.com',

                       generate_password_hash('reception123'),

                       'receptionist', 'Demo Receptionist'))



        # ── Seed demo therapist ──

        existing3 = c.execute('SELECT id FROM users WHERE username=?', ('therapist',)).fetchone()

        if not existing3:

            c.execute('''INSERT INTO users (username, email, password_hash, role, full_name, specialization, gender, languages)

                         VALUES (?,?,?,?,?,?,?,?)''',

                      ('therapist', 'therapist@ahapsych.com',

                       generate_password_hash('therapist123'),

                       'therapist', 'Demo Therapist',

                       'Individual Counseling', 'Female', 'English,Amharic'))



        # ── Seed demo supervisor ──

        existing4 = c.execute('SELECT id FROM users WHERE username=?', ('supervisor',)).fetchone()

        if not existing4:

            c.execute('''INSERT INTO users (username, email, password_hash, role, full_name)

                       VALUES (?,?,?,?,?)''',

                      ('supervisor', 'supervisor@ahapsych.com',

                       generate_password_hash('supervisor123'),

                       'supervisor', 'Demo Supervisor'))



        # Keep the bundled demo accounts usable even if an older DB exists.

        c.execute("UPDATE users SET is_active=1 WHERE username IN ('admin', 'reception', 'therapist', 'supervisor')")



        room_count = list(c.execute('SELECT COUNT(*) AS cnt FROM rooms').fetchone().values())[0]

        if room_count == 0:

            c.executemany('INSERT INTO rooms (name, code, color, is_active, sort_order) VALUES (?,?,?,?,?)', [

                ('Room 1', 'R1', '#043069', 1, 1),

                ('Room 2', 'R2', '#0d9488', 1, 2),

                ('Room 3', 'R3', '#ffbf00', 1, 3),

            ])



        # ── Seed services ──

        svc_count = list(c.execute('SELECT COUNT(*) AS cnt FROM services').fetchone().values())[0]

        if svc_count == 0:

            services = [

                ('Individual Counseling', 'One-on-one therapy sessions', 60, 500.0),

                ('Group Therapy', 'Facilitated group sessions', 90, 200.0),

                ('Couples/Family Therapy', 'Relationship counseling', 60, 700.0),

                ('Psychological Assessment', 'Comprehensive psychological evaluation', 120, 1500.0),

                ('Crisis Intervention', 'Urgent mental health support', 60, 0.0),

                ('Supervision Session', 'Clinical supervision for therapists', 60, 0.0),

            ]

            c.executemany('INSERT INTO services (name, description, duration_minutes, price) VALUES (?,?,?,?)', services)



        conn.commit()
        backfill_missing_appointment_rooms()

        # Seed default assessment templates
        try:
            seed_assessments_pg.seed_all(conn)
            conn.commit()
        except Exception as e:
            print(f"[STARTUP] Error seeding templates: {e}")


# ─────────────────────────────────────────────

# HELPERS

# ─────────────────────────────────────────────

def get_db():

    """Returns a _db._Connection backed by Supabase Postgres."""

    return _db.connect()



def ensure_column(conn, table, column, ddl):

    """Adds a column to `table` if it does not already exist (PostgreSQL-safe)."""

    row = conn.execute(

        "SELECT 1 FROM information_schema.columns WHERE table_name=%s AND column_name=%s",

        (table, column)

    ).fetchone()

    if not row:

        base_type = ddl.split()[0]

        conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {base_type}")



def normalize_role(role):

    role = str(role or '').strip().lower()

    if role in ('administrator', 'system administrator', 'super admin', 'superadmin', 'root'):

        return 'admin'

    if role in ('reception', 'front desk'):

        return 'receptionist'

    return role


def current_user():

    user = session.get('user')

    if not user:

        return None

    user = dict(user)

    user['role'] = normalize_role(user.get('role'))

    return user



def now_in_eat():

    return datetime.now(EAT)


def _ensure_eat_datetime(value):

    if not value:

        return None

    try:

        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))

    except Exception:

        return None

    if dt.tzinfo is None:

        return dt.replace(tzinfo=EAT)

    return dt.astimezone(EAT)


def portal_url_for_role(role):

    role = normalize_role(role)

    portal_paths = {

        'therapist': '/portals/therapist_portal.html',

        'receptionist': '/portals/reception_portal.html',

        'admin': '/portals/admin_portal.html',

        'supervisor': '/portals/supervisor_portal.html',

    }

    return APP_BASE_URL + portal_paths.get(role, '/login')


def require_role(*roles):

    user = current_user()

    if not user:

        return False

    allowed = {normalize_role(role) for role in roles}

    return user.get('role') in allowed



def log_action(user_id, action, resource, detail=''):

    with get_db() as conn:

        conn.execute('INSERT INTO audit_logs (user_id, action, resource, detail, ip_address) VALUES (?,?,?,?,?)',

                     (user_id, action, resource, detail, request.remote_addr))

        conn.commit()



def generate_client_code():

    return 'AHA-' + secrets.token_hex(3).upper()


def slugify_text(text):

    slug = re.sub(r'[^a-z0-9]+', '-', str(text or '').strip().lower()).strip('-')

    return slug or f'template-{secrets.token_hex(3)}'


def unique_assessment_slug(conn, base_name, current_id=None):

    base_slug = slugify_text(base_name)

    slug = base_slug

    suffix = 1

    while True:

        params = [slug]

        query = 'SELECT id FROM assessment_templates WHERE slug=?'

        if current_id is not None:

            query += ' AND id != ?'

            params.append(current_id)

        exists = conn.execute(query, tuple(params)).fetchone()

        if not exists:

            return slug

        suffix += 1

        slug = f'{base_slug}-{suffix}'


def coerce_int(value, default=0):

    try:

        if value is None or value == '':

            return default

        if isinstance(value, bool):

            return 1 if value else 0

        return int(value)

    except (TypeError, ValueError):

        return default


def coerce_required(value):

    if isinstance(value, bool):

        return 1 if value else 0

    if isinstance(value, (int, float)):

        return 1 if value else 0

    text = str(value or '').strip().lower()

    if text in ('1', 'true', 'yes', 'y', 'required', 'on', 'checked'):

        return 1

    return 0


def normalize_question_type(value):

    text = str(value or 'text').strip().lower().replace('-', '_').replace(' ', '_')

    mapping = {

        'short_answer': 'text',

        'singlechoice': 'single_choice',

        'single_choice': 'single_choice',

        'multiplechoice': 'multiple_choice',

        'multiple_choice': 'multiple_choice',

        'checkbox': 'multiple_choice',

        'checkboxes': 'multiple_choice',

        'likert': 'scale',

        'likert_scale': 'scale',

        'rating': 'scale',

        'rating_scale': 'scale',

        'scale': 'scale',

        'open_ended': 'textarea',

        'openended': 'textarea',

        'long_answer': 'textarea',

        'paragraph': 'textarea',

        'yes_no': 'boolean',

        'yesno': 'boolean',

        'boolean': 'boolean',

        'true_false': 'boolean',

        'truefalse': 'boolean',

        'numeric': 'number',

    }

    return mapping.get(text, text if text in ('text', 'textarea', 'single_choice', 'multiple_choice', 'scale', 'date', 'number', 'boolean', 'instruction', 'info', 'intro', 'heading', 'title', 'paragraph', 'separator', 'note') else 'text')


def normalize_assessment_question(question, idx=0):

    q = dict(question or {})

    label = str(q.get('label_en') or q.get('question') or '').strip()

    helper = str(q.get('helper_text') or '').strip()

    options = q.get('options', [])

    if isinstance(options, str):

        options = [opt.strip() for opt in options.split('\n') if opt.strip()]

    elif not isinstance(options, list):

        options = [str(options)] if options not in (None, '') else []

    text_blob = f"{label} {helper} {' '.join(options)}".lower()

    qtype = normalize_question_type(q.get('question_type', 'text'))

    if qtype in ('text', 'scale') and re.search(r'\b(yes/no|yes or no|y/n|\(yes/no\)|\(y/n\))\b', text_blob):

        qtype = 'boolean'

    if qtype == 'boolean':

        options = ['Yes', 'No']

    q['question_key'] = q.get('question_key') or f'q{idx+1}'

    q['label_en'] = label

    q['label_am'] = str(q.get('label_am') or '').strip()

    q['question_type'] = qtype

    q['required'] = coerce_required(q.get('required', 0))

    q['options'] = options

    q['helper_text'] = helper

    q['sort_order'] = coerce_int(q.get('sort_order', idx + 1), idx + 1)

    q['scoring'] = q.get('scoring') or {}

    q['logic'] = q.get('logic') or {}

    return q



def generate_login_code(length=8):

    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

    return ''.join(secrets.choice(alphabet) for _ in range(length))



def get_bot_token():

    return os.getenv('TELEGRAM_BOT_TOKEN', '').strip()



def get_setting(key, default=''):

    with get_db() as conn:

        row = conn.execute('SELECT value FROM app_settings WHERE key=?', (key,)).fetchone()

    return row['value'] if row and row['value'] is not None else default



def set_setting(key, value):

    with get_db() as conn:

        conn.execute('INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))

        conn.commit()



def telegram_api(method, payload):

    token = get_bot_token()

    if not token:

        return False, 'Telegram bot token not configured'

    url = f'https://api.telegram.org/bot{token}/{method}'

    data = json.dumps(payload).encode('utf-8')

    req = urllib_request.Request(url, data=data, headers={'Content-Type': 'application/json'})

    try:

        with urllib_request.urlopen(req, timeout=6) as resp:

            return True, json.loads(resp.read().decode('utf-8'))

    except urllib_error.URLError as exc:

        return False, str(exc)



def telegram_api_get(method, params=None, timeout=20):

    token = get_bot_token()

    if not token:

        return False, 'Telegram bot token not configured'

    query = urllib_parse.urlencode(params or {})

    url = f'https://api.telegram.org/bot{token}/{method}'

    if query:

        url = f'{url}?{query}'

    req = urllib_request.Request(url)

    try:

        with urllib_request.urlopen(req, timeout=timeout) as resp:

            return True, json.loads(resp.read().decode('utf-8'))

    except urllib_error.URLError as exc:

        return False, str(exc)





def send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=None):

    def _compact(value):

        lines = [line.rstrip() for line in str(value or '').replace('\r', '').split('\n')]

        compacted = []

        blank = False

        for line in lines:

            if not line.strip():

                if not blank:

                    compacted.append('')

                blank = True

            else:

                compacted.append(line)

                blank = False

        return '\n'.join(compacted).strip()

    if not chat_id:

        print(f'[TELEGRAM] send_telegram_message: No chat_id')

        return False

    payload = {
        'chat_id': chat_id,
        'text': _compact(text),
        'disable_web_page_preview': True,
        'parse_mode': parse_mode
    }

    if reply_markup:
        payload['reply_markup'] = reply_markup

    ok, result = telegram_api('sendMessage', payload)

    print(f'[TELEGRAM] send_telegram_message to {chat_id}: ok={ok}, result={result}')

    return ok, result


def _telegram_safe(value, default='Not specified'):

    text = default if value in (None, '') else str(value)

    return html.escape(text, quote=False)


def _appointment_notification_body(appt, action, reason='', old_start_time=None, old_end_time=None, change_scope=''):

    client_name = _telegram_safe(appt.get('client_name') or 'Client')

    client_code = _telegram_safe(appt.get('client_code') or 'Not specified')

    therapist = _telegram_safe(appt.get('therapist_name') or 'Unassigned therapist')

    therapist_id = appt.get('therapist_id')

    room_source = appt.get('room')

    if room_source:

        try:

            room = _telegram_safe(room_display_name(room_source))

        except Exception:

            room = _telegram_safe(appt.get('location') or appt.get('room_name') or appt.get('room_code') or 'Unassigned')

    else:

        room = _telegram_safe(appt.get('location') or appt.get('room_name') or appt.get('room_code') or 'Unassigned')

    current_status = (appt.get('status') or 'scheduled').replace('_', ' ').strip().title()

    if current_status.lower() == 'no show':

        current_status = 'No-show'

    session_type = _telegram_safe((appt.get('type') or 'Session').replace('_', ' ').title())

    location = _telegram_safe(appt.get('location') or 'Not specified')

    current_start = _telegram_safe(format_datetime_readable(appt.get('start_time')))

    current_end = _telegram_safe(format_datetime_readable(appt.get('end_time')))

    reason_text = _telegram_safe(reason or 'No reason provided')

    scope = (change_scope or '').strip().lower()

    scope_label = 'Temporary change' if scope == 'temporary' else 'Permanent change' if scope == 'permanent' else 'Administrative update'

    action_title = {

        'created': 'New session scheduled',

        'changed': 'Session updated',

        'rescheduled': 'Session rescheduled',

        'cancelled': 'Session cancelled',

        'terminated': 'Session terminated',

        'no_show': 'Session marked no-show',

    }.get(action, 'Appointment update')

    lines = [

        f'📋 <b>{action_title}</b>',

        '',

        f'• <b>Client:</b> {client_name} <code>{client_code}</code>',

        f'• <b>Therapist:</b> {therapist}',

        f'• <b>Therapist ID:</b> <code>{therapist_id or "Not assigned"}</code>',

        f'• <b>Session type:</b> {session_type}',

        f'• <b>Location:</b> {location}',

        f'• <b>Room:</b> {room}',

        f'• <b>Current status:</b> {current_status}',

    ]

    if action in ('rescheduled', 'changed'):

        lines.extend(['', '🔄 <b>Change details</b>'])

        if old_start_time:

            lines.append(f'• <b>Previous date/time:</b> {_telegram_safe(format_datetime_readable(old_start_time))}')

        if old_end_time:

            lines.append(f'• <b>Previous end time:</b> {_telegram_safe(format_datetime_readable(old_end_time))}')

        lines.extend([

            f'• <b>New date/time:</b> {current_start}',

            f'• <b>New end time:</b> {current_end}',

        ])

    elif action in ('cancelled', 'terminated'):

        lines.extend([

            '',

            '🛑 <b>Cancellation details</b>' if action == 'cancelled' else '🚫 <b>Termination details</b>',

            f'• <b>Scheduled date/time:</b> {current_start}',

            f'• <b>End time:</b> {current_end}',

        ])

    elif action == 'no_show':

        lines.extend([

            '',

            '⚠️ <b>No-show details</b>',

            f'• <b>Session time:</b> {current_start}',

            f'• <b>End time:</b> {current_end}',

        ])

    else:

        lines.extend([

            '',

            '🗓️ <b>Schedule details</b>',

            f'• <b>Date/time:</b> {current_start}',

            f'• <b>End time:</b> {current_end}',

        ])

    lines.extend([

        f'• <b>Scope:</b> {_telegram_safe(scope_label)}',

        f'• <b>Reason:</b> {reason_text}',

    ])

    return '\n'.join(lines)



def build_appointment_message(appt, action, reason='', old_start_time=None, old_end_time=None, change_scope=''):
    client_name = appt.get('client_name') or 'Client'
    therapist_name = appt.get('therapist_name') or 'Therapist'
    
    # Format date strings beautifully if possible
    def fdt(val):
        if not val: return ''
        try:
            # Parse ISO e.g. 2026-07-30T10:00:00
            val = str(val)
            d, t = val.split('T') if 'T' in val else val.split(' ')
            t = t[:5] # HH:MM
            return f"<b>{d}</b> at <b>{t}</b>"
        except:
            return f"<b>{val}</b>"

    new_start = fdt(appt.get('start_time'))
    old_start = fdt(old_start_time)
    
    room = appt.get('room_name') or appt.get('location') or 'Not specified'
    appt_type = (appt.get('type') or 'Session').title()
    status = (appt.get('status') or 'scheduled').replace('_', ' ').title()
    
    lines = [f"👤 <b>Client:</b> {client_name}"]
    lines.append(f"👨‍⚕️ <b>Therapist:</b> {therapist_name}")
    lines.append(f"🏷️ <b>Type:</b> {appt_type}")
    lines.append(f"🚪 <b>Location:</b> {room}")
    lines.append(f"📊 <b>Status:</b> {status}")
    lines.append("")
    
    if action in ('cancelled', 'terminated'):
        lines.append(f"❌ <b>Cancelled / Terminated</b>")
        lines.append(f"📅 Was: {new_start}")
        if reason:
            lines.append(f"💬 Reason: {reason}")
    elif action == 'no_show':
        lines.append(f"⚠️ <b>Client No-Show</b>")
        lines.append(f"📅 Date: {new_start}")
        if reason:
            lines.append(f"💬 Note: {reason}")
    elif action in ('rescheduled', 'changed'):
        lines.append(f"🔄 <b>Schedule Changed</b>")
        if change_scope == 'permanent':
            lines.append(f"<i>(This is a permanent change to the recurring series)</i>")
        if old_start:
            lines.append(f"📅 Previous: {old_start}")
        lines.append(f"📅 New Time: {new_start}")
        if reason:
            lines.append(f"💬 Reason: {reason}")
    else:
        lines.append(f"📅 <b>Date/Time:</b> {new_start}")
        if reason:
            lines.append(f"💬 Note: {reason}")

    return '\n'.join(lines)


def notify_user(user_id, subject, body):
    with get_db() as conn:
        user = conn.execute('SELECT id, full_name, telegram_chat_id, role FROM users WHERE id=?', (user_id,)).fetchone()

    if not user:
        return

    chat_id = user['telegram_chat_id']
    if not chat_id:
        return

    text = f"\U0001f514 <b>{subject}</b>\n\n{body}"
    portal = portal_url_for_role(user['role'])
    markup = {
        'inline_keyboard': [
            [{'text': '\U0001f310 Open Portal', 'web_app': {'url': portal}}]
        ]
    }

    send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=markup)


def notify_appointment_update(appt, action, reason='', old_start_time=None, old_end_time=None, change_scope=''):

    subject_map = {

        'created': 'New appointment scheduled',

        'cancelled': 'Appointment cancelled',

        'terminated': 'Appointment terminated',

        'no_show': 'Session marked no-show',

        'completed': 'Appointment completed',

        'changed': 'Appointment changed',

        'rescheduled': 'Appointment changed',

    }

    subject = subject_map.get(action, 'Appointment updated')

    body = build_appointment_message(appt, action, reason, old_start_time=old_start_time, old_end_time=old_end_time, change_scope=change_scope)

    roles = ['admin', 'receptionist']

    if action in ('created', 'changed', 'rescheduled', 'cancelled', 'terminated', 'no_show', 'completed'):

        notify_roles(roles, subject, body)

    notify_user(appt.get('therapist_id'), subject, body)

    return subject, body



def notify_roles(roles, subject, body):

    with get_db() as conn:

        users = conn.execute(

            f"SELECT id, telegram_chat_id FROM users WHERE role IN ({','.join('?' for _ in roles)}) AND is_active=1",

            tuple(roles)

        ).fetchall()

    for user in users:

        send_telegram_message(user['telegram_chat_id'], f"<b>{subject}</b>\n\n{body}")



def safe_date_filter(start_value, end_value):

    conditions = []

    params = []

    if start_value:

        conditions.append('a.start_time::date >= %s::date')

        params.append(start_value)

    if end_value:

        conditions.append('a.start_time::date <= %s::date')

        params.append(end_value)

    return conditions, params



def format_datetime_readable(value):

    dt = _ensure_eat_datetime(value)

    if not dt:

        return 'Not specified'

    hour = dt.strftime('%I').lstrip('0') or '12'

    return f"{dt.strftime('%B')} {dt.day}, {dt.year} at {hour}:{dt.strftime('%M')} {dt.strftime('%p')} EAT"


def room_display_name(room):

    if not room:

        return 'Unassigned'

    code = room.get('code') or ''

    name = room.get('name') or 'Room'

    return f'{name}{f" ({code})" if code else ""}'



def fetch_active_rooms():

    with get_db() as conn:

        rows = conn.execute('''SELECT id, name, code, color, is_active, sort_order

                               FROM rooms

                               WHERE COALESCE(is_active, 1)=1

                               ORDER BY sort_order ASC, name ASC''').fetchall()

    return [dict(r) for r in rows]



def get_room_by_id(room_id):

    if not room_id:

        return None

    with get_db() as conn:

        row = conn.execute('SELECT id, name, code, color, is_active, sort_order FROM rooms WHERE id=?', (room_id,)).fetchone()

    return dict(row) if row else None



def is_room_available(room_id, start_time, end_time, appointment_id=None):

    if not room_id or not start_time or not end_time:

        return False

    with get_db() as conn:

        row = conn.execute('''SELECT COUNT(*) AS cnt

                              FROM appointments

                              WHERE room_id=?

                                AND status NOT IN ('cancelled','terminated')

                                AND start_time::timestamp < %s::timestamp

                                AND COALESCE(end_time, start_time)::timestamp > %s::timestamp

                                AND (? IS NULL OR id<>?)''',

                           (room_id, end_time, start_time, appointment_id, appointment_id)).fetchone()

    return (row['cnt'] if row else 0) == 0



def available_rooms_for_slot(start_time, end_time, appointment_id=None):

    rooms = fetch_active_rooms()

    available = [room for room in rooms if is_room_available(room['id'], start_time, end_time, appointment_id=appointment_id)]

    return available



def choose_room_for_slot(start_time, end_time, preferred_room_id=None, appointment_id=None):

    if preferred_room_id and is_room_available(preferred_room_id, start_time, end_time, appointment_id=appointment_id):

        return preferred_room_id

    available = available_rooms_for_slot(start_time, end_time, appointment_id=appointment_id)

    return available[0]['id'] if available else None



def backfill_missing_appointment_rooms():

    with get_db() as conn:

        rows = conn.execute('''

            SELECT id, start_time, end_time, room_id, status

            FROM appointments

            WHERE room_id IS NULL

              AND start_time IS NOT NULL

              AND COALESCE(status, 'scheduled') NOT IN ('cancelled', 'terminated')

            ORDER BY start_time::timestamp ASC, id ASC

        ''').fetchall()

        for row in rows:

            chosen = choose_room_for_slot(row['start_time'], row['end_time'] or row['start_time'], appointment_id=row['id'])

            if not chosen:

                rooms = fetch_active_rooms()

                chosen = rooms[0]['id'] if rooms else None

            if chosen:

                conn.execute('UPDATE appointments SET room_id=? WHERE id=?', (chosen, row['id']))

                conn.commit()



def call_openai(prompt, system=None, model=None, num_predict=700):
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_api_key:
        print("[AI ERROR] GROQ_API_KEY is not set or empty in environment variables.")
        return False, "GROQ_API_KEY not configured."

    system_prompt = system or (
        'You are a careful clinical documentation assistant. You may improve grammar, punctuation, '
        'structure, and professionalism, but you must not invent facts, diagnoses, interventions, '
        'or outcomes. Keep the content grounded in the source text and return plain-text output with '
        'the exact headings requested.'
    )

    chosen_model = model or CLINICAL_AI_MODEL

    try:
        client = GroqOpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        response = client.chat.completions.create(
            model=chosen_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            top_p=0.9,
            max_tokens=num_predict,
        )
        result_text = response.choices[0].message.content
        print(f"[AI OK] Groq responded with {len(result_text)} chars.")
        return True, result_text
    except Exception as e:
        print(f"[AI ERROR] Groq call failed: {e}")
        return False, str(e)


@app.route('/api/ai/test', methods=['GET'])
def ai_test():
    """Diagnostic endpoint to verify Groq AI is configured and working."""
    key = os.getenv('GROQ_API_KEY', '').strip()
    if not key:
        return jsonify({'status': 'error', 'message': 'GROQ_API_KEY is not set in environment variables.'}), 500
    ok, result = call_openai('Say hello in one sentence.', num_predict=50)
    if ok:
        return jsonify({'status': 'ok', 'message': 'Groq AI is working.', 'response': result})
    return jsonify({'status': 'error', 'message': result}), 500



def build_note_prompt(raw_text, note_type='progress', client_name='', session_date='', therapist_name=''):

    return f"""You are a clinical documentation assistant for Aha Psychological Service.

Rewrite the therapist's draft into a polished, detailed, and factual counseling session summary.



Clinical rules:

- You may rewrite, paraphrase, and soften the wording so it reads like a professional clinical note.

- Improve grammar, spelling, clarity, tone, and structure where helpful.

- Do not invent symptoms, diagnoses, interventions, risk level, or outcomes.

- Keep the meaning aligned with the source, but do not copy the exact wording if it sounds rough or informal.

- If a detail is missing, write "Not specified" rather than guessing.

- Preserve important clinical facts, dates, and client statements.

- Be detailed, but stay factual and grounded in the draft.

- Return plain text only.

- Do not use markdown bullets, stars, emojis, or commentary outside the requested headings.

- Make the structure clear enough to paste directly into the chart.

- Do not use SOAP headings such as Subjective, Objective, Assessment, or Plan.

- Always use the exact headings and order shown below.

- Do not add any introduction, closing sentence, or extra summary section.

- Do not rename, combine, or reorder headings.

- Under each heading, write factual clinical prose paragraphs only.

- If a section has no clear source detail, write "Not specified" under that section.

- Base the output only on the source text below. If the source does not support a detail, do not infer it.

- Keep the answer grounded in the chart draft, not in general clinical assumptions.



Note metadata:

Client: {client_name}

Session date: {session_date}

Therapist: {therapist_name}

Note type: {note_type}



Required format:

Counseling Session Summary & Follow Up

Counselor:  ____________________________ Session Date:  ________________ Time:  ________

Client(s) Name:  ________________________________________Code: ____	Session #: ________

**************************************************************************************

Reflect from previous session and specific compliant:

Write 1 to 3 factual paragraphs summarizing the main concerns, progress since the last session, the client’s current presentation, and any notable emotional or behavioral patterns.



Session treatment goal:

Write 1 short paragraph describing the counseling goal or goals being worked on in this session.



Assessment of progress:

Write 1 to 2 paragraphs describing what changed, what improved, what remains difficult, and what the client was able or not able to do.



Session intervention:

Write 1 to 3 paragraphs describing interventions used by the therapist, including CBT, reflection, cognitive restructuring, role play, psychoeducation, or other clinically relevant support.



Therapeutic plan/next steps:

Write 1 to 2 paragraphs describing homework, follow-up tasks, coping strategies, boundary practice, or what should happen next.



Special Attention:

Write any risk, safety, emotional, family, work, grief, or clinical concerns that deserve attention. If none, write "Not specified".



Source text to rewrite:

{raw_text}

"""



def build_note_prompt_v2(raw_text, note_type='progress', client_name='', session_date='', therapist_name=''):

    style = (note_type or 'progress').strip().lower()

    style_map = {
        'soap': """Return the note in this exact structure:

SOAP NOTE

SUBJECTIVE:
Use the client’s reported experience, chief concern, mood, and events since last session.

OBJECTIVE:
Use factual therapist observations only.

ASSESSMENT:
Describe clinical impression and progress using only the source text.

PLAN:
Include interventions, homework, and next steps from the source text.
""",
        'dap': """Return the note in this exact structure:

DAP NOTE

DATA:
Include what the client reported and what the therapist observed.

ASSESSMENT:
Describe the clinical interpretation and current state.

PLAN:
Include interventions, homework, and follow-up steps from the source text.
""",
        'progress': """Return the note in this exact structure:

PROGRESS NOTE

SESSION SUMMARY:
Write a concise but complete summary of the session.

PROGRESS TOWARD GOALS:
Describe changes, improvements, and barriers.

INTERVENTIONS:
Describe therapist interventions and client response.

HOMEWORK/BETWEEN-SESSION TASKS:
List tasks or coping skills to practice.

RISK ASSESSMENT:
Summarize safety or risk concerns.

NEXT SESSION:
Describe next steps and the next focus.
""",
        'crisis': """Return the note in this exact structure:

CRISIS NOTE

PRESENTING CRISIS:
Describe the crisis situation.

RISK ASSESSMENT:
Include suicidal ideation, plan/intent, means access, and protective factors when available.

INTERVENTIONS:
List crisis interventions used.

SAFETY PLAN:
Summarize the safety plan and protective actions.

DISPOSITION:
Describe the immediate disposition or recommended level of care.

FOLLOW-UP:
State the follow-up plan.
"""
    }

    requested_structure = style_map.get(style, """Return the note in this exact structure:

Counseling Session Summary & Follow Up

Counselor: ____________________________ Session Date: ________________ Time: ________

Client(s) Name: ________________________________________ Code: ____ Session #: ________

Reflect from previous session and specific complaint:

Session treatment goal:

Assessment of progress:

Session intervention:

Therapeutic plan/next steps:

Special Attention:
""")

    return f"""You are a clinical documentation assistant for Aha Psychological Service.

Rewrite the therapist's draft into a polished, detailed, and factual clinical note.

Clinical rules:

- Preserve every clinically relevant detail already present in the source text.
- Reorganize the text into the requested structure without deleting meaning.
- Do not invent symptoms, diagnoses, interventions, risk level, or outcomes.
- If a detail is missing, write "Not specified" rather than guessing.
- Improve grammar, spelling, clarity, tone, and professionalism.
- Keep the content grounded in the source text only.
- Return plain text only.
- Do not add commentary, markdown decoration, or extra headings.
- Do not add blank template prompts that erase the therapist's draft.

Metadata:

Client: {client_name}
Session date: {session_date}
Therapist: {therapist_name}
Format: {style}

Requested structure:

{requested_structure}

Source text:

{raw_text}

"""


def extract_ai_sections(text, structured_label='STRUCTURED NOTE:', summary_label='SHORT SUMMARY:'):

    body = (text or '').strip()

    if not body:

        return '', ''

    upper = body.upper()

    s_idx = upper.find(structured_label.upper())

    m_idx = upper.find(summary_label.upper())

    if s_idx != -1 and m_idx != -1 and m_idx > s_idx:

        structured = body[s_idx + len(structured_label):m_idx].strip()

        summary = body[m_idx + len(summary_label):].strip()

        return structured, summary

    if s_idx != -1:

        structured = body[s_idx + len(structured_label):].strip()

        return structured, ''

    return body, ''



def make_short_summary(text, sentence_count=3, char_limit=360):

    clean = ' '.join((text or '').split())

    if not clean:

        return ''

    parts = re.split(r'(?<=[.!?])\s+', clean)

    summary = ' '.join(parts[:sentence_count]).strip()

    if len(summary) > char_limit:

        summary = summary[:char_limit].rsplit(' ', 1)[0].strip()

    return summary or clean[:char_limit]



def trim_counseling_template(text):

    body = (text or '').strip()

    if not body:

        return ''

    markers = [

        'Counseling Session Summary & Follow Up',

        'Counseling Session Summary:',

        'Counseling Session Summary',

    ]

    for marker in markers:

        idx = body.find(marker)

        if idx != -1:

            return body[idx:].strip()

    return body



def strip_html_tags(text):

    text = text or ''

    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.I | re.S)

    text = re.sub(r'<[^>]+>', ' ', text)

    text = (text

            .replace('&nbsp;', ' ')

            .replace('&amp;', '&')

            .replace('&lt;', '<')

            .replace('&gt;', '>'))

    return re.sub(r'\s+', ' ', text).strip()



def extract_docx_text_from_bytes(blob):

    try:

        import zipfile

        from xml.etree import ElementTree as ET

        with zipfile.ZipFile(io.BytesIO(blob)) as zf:

            xml = zf.read('word/document.xml')

        root = ET.fromstring(xml)

        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

        lines = []

        for para in root.findall('.//w:p', ns):

            text_parts = [node.text for node in para.findall('.//w:t', ns) if node.text]

            line = ''.join(text_parts).strip()

            if line:

                lines.append(line)

        return '\n'.join(lines).strip()

    except Exception:

        return ''



def sanitize_assessment_text(text):

    text = (text or '').replace('\r\n', '\n').replace('\r', '\n')

    if '<' in text and '>' in text:

        text = strip_html_tags(text)

    text = re.sub(r'\u00a0', ' ', text)

    text = re.sub(r'[ \t]+\n', '\n', text)

    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()



def extract_json_object(text):

    body = (text or '').strip()

    if not body:

        return None

    candidates = [body]

    code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', body, flags=re.I)

    if code_match:

        candidates.insert(0, code_match.group(1).strip())

    first = body.find('{')

    last = body.rfind('}')

    if first != -1 and last != -1 and last > first:

        candidates.insert(0, body[first:last + 1])

    for candidate in candidates:

        try:

            return json.loads(candidate)

        except Exception:

            continue

    return None



def _assessment_category_from_text(title, text):

    haystack = f'{title}\n{text}'.lower()

    mapping = [

        ('Depression', ['phq', 'depress', 'mood', 'sadness']),

        ('Anxiety', ['gad', 'anx', 'worry', 'panic']),

        ('Trauma', ['ptsd', 'trauma', 'stress', 'event']),

        ('Personality', ['personality', 'trait', 'borderline', 'millon']),

        ('Substance Use', ['alcohol', 'drug', 'substance', 'audit', 'dast']),

        ('Sleep', ['sleep', 'insomnia', 'restless']),

        ('Child/Adolescent', ['child', 'adolescent', 'youth', 'teen']),

        ('General Screening', []),

    ]

    for category, keywords in mapping:

        if any(k in haystack for k in keywords):

            return category

    return 'General Screening'



def heuristic_assessment_parse(text):

    text = sanitize_assessment_text(text)

    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]

    title = lines[0] if lines else 'Untitled Assessment'

    if len(title.split()) > 12 and len(lines) > 1:

        title = lines[1] if len(lines[1].split()) <= 12 else title

    questions = []

    current = None

    item_pattern = re.compile(r'^(?:[-*•·]|\(?[A-H]\)?[.)]|Q\d+[.)]|\d+[.)])\s*(.+)$', re.I)

    for line in lines[1:]:

        numbered = re.match(r'^(\d{1,3})[.)\-:]\s*(.+)$', line)

        bullet = item_pattern.match(line)

        if numbered and len(numbered.group(2).split()) > 2:

            if current:

                questions.append(current)

            question_text = numbered.group(2).strip()
            lower_text = question_text.lower()
            is_boolean = bool(re.search(r'\b(yes/no|yes or no|y/n|\(yes/no\)|\(y/n\))\b', lower_text))

            current = {

                'question_key': f'q{numbered.group(1)}',

                'label_en': re.sub(r'\s*\(?yes\s*/\s*no\)?\s*$', '', question_text, flags=re.I).strip(),

                'label_am': '',

                'question_type': 'boolean' if is_boolean else 'scale',

                'required': 1,

                'options': ['Yes', 'No'] if is_boolean else [],

                'helper_text': '',

                'sort_order': int(numbered.group(1)),

                'scoring': {},

                'logic': {}

            }

            continue

        if bullet and current:

            option_text = bullet.group(1).strip()

            if len(option_text) <= 120 and option_text not in current['options']:

                current['options'].append(option_text)

            continue

        if current and not current.get('helper_text') and len(line) < 200 and not line.endswith('?'):

            current['helper_text'] = line

    if current:

        questions.append(current)

    if not questions:

        for idx, line in enumerate(lines[1:25], start=1):

            if len(line) > 8:

                questions.append({

                    'question_key': f'q{idx}',

                    'label_en': line,

                    'label_am': '',

                    'question_type': 'text',

                    'required': 1,

                    'options': [],

                    'helper_text': '',

                    'sort_order': idx,

                    'scoring': {},

                    'logic': {}

                })

    duplicates = []

    seen = set()

    for q in questions:

        key = re.sub(r'\s+', ' ', (q.get('label_en') or '').strip().lower())

        if key in seen:

            duplicates.append(q.get('label_en'))

        seen.add(key)

    warnings = []

    if duplicates:

        warnings.append(f'Duplicate questions detected: {len(duplicates)}')

    if not any('instruction' in ln.lower() for ln in lines[:8]):

        warnings.append('Instructions may be missing or buried in the text')

    if not any(q.get('options') for q in questions):

        warnings.append('No response options were detected, so items were treated as open-ended or scale prompts')

    return {

        'title': title,

        'author': '',

        'description': '',

        'instructions': '',

        'category': _assessment_category_from_text(title, text),

        'questions': questions,

        'scoring_rules': [],

        'interpretation_guidelines': [],

        'severity_classifications': [],

        'warnings': warnings,

        'source_excerpt': '\n'.join(lines[:40])

    }



def parse_assessment_structure(text):

    text = sanitize_assessment_text(text)

    if not text:

        return heuristic_assessment_parse(text)

    heuristic = heuristic_assessment_parse(text)

    prompt = f"""

You are converting a psychological assessment into a structured JSON template.

Return ONLY valid JSON with these keys:

title, author, description, instructions, category, questions, scoring_rules, interpretation_guidelines, severity_classifications, warnings.



Rules:

- Preserve original numbering where possible.

- Each question should include: question_key, label_en, label_am, question_type, required, options, helper_text, sort_order, scoring, logic.

- Use question_type values: text, textarea, single_choice, multiple_choice, scale, date, number, boolean.

- options must be a JSON array of strings.

- scoring, logic, scoring_rules, interpretation_guidelines, severity_classifications must be arrays or objects, not markdown.

- If a field is unknown, use an empty string, empty array, or empty object.

- Keep warnings concise.



Assessment text:

{text[:18000]}

""".strip()

    ok, result = call_openai(prompt, model=CLINICAL_AI_MODEL, num_predict=2000)

    if ok and result.strip():

        payload = extract_json_object(result)

        if isinstance(payload, dict):

            payload['questions'] = [normalize_assessment_question(q, idx) for idx, q in enumerate(payload.get('questions') or heuristic.get('questions', []))]

            payload.setdefault('warnings', [])

            if not payload.get('questions'):
                payload['questions'] = [normalize_assessment_question(q, idx) for idx, q in enumerate(heuristic.get('questions', []))]

            payload.setdefault('title', heuristic.get('title', 'Untitled Assessment'))

            payload.setdefault('category', _assessment_category_from_text(payload.get('title', ''), text))

            if heuristic.get('warnings'):
                merged_warnings = list(dict.fromkeys([*(payload.get('warnings') or []), *heuristic.get('warnings', [])]))
                has_options = any(q.get('options') for q in (payload.get('questions') or []))
                if has_options:
                    merged_warnings = [w for w in merged_warnings if 'no response options' not in str(w).lower()]
                payload['warnings'] = merged_warnings

            return payload

    fallback = heuristic

    if result.strip():

        fallback['warnings'] = list(fallback.get('warnings', [])) + [result.strip()[:200]]

    return fallback



def normalize_structured_text(text):

    out = (text or '').replace('\r', '').strip()

    if not out:

        return ''

    out = re.sub(r'```[\s\S]*?```', '', out).strip()

    out = re.sub(r'\*\*(.+?)\*\*', r'\1', out)

    out = re.sub(r'^\s*[-*•]\s+', '- ', out, flags=re.M)

    out = re.sub(r'\n{3,}', '\n\n', out)

    return out.strip()



def _extract_heading_block(text, headings):

    if not text:

        return ''

    body = text.replace('\r\n', '\n')

    heading_positions = []

    for heading in headings:

        pattern = re.compile(r'(?im)^\s*(?:\*\*)?' + re.escape(heading) + r'(?:\*\*)?\s*:?\s*(?:\n|$)')

        match = pattern.search(body)

        if match:

            heading_positions.append((match.start(), match.end(), heading))

    if not heading_positions:

        return ''

    heading_positions.sort(key=lambda item: item[0])

    extracted = []

    for idx, (_, end, heading) in enumerate(heading_positions):

        next_start = heading_positions[idx + 1][0] if idx + 1 < len(heading_positions) else len(body)

        block = body[end:next_start].strip()

        if block:

            extracted.append(f'{heading}: {block}')

    return '\n\n'.join(extracted).strip()



def normalize_ai_note_output(ai_text, raw_text='', note_type='progress'):

    clean_ai = re.sub(r'```[\s\S]*?```', '', ai_text or '').strip()

    source = raw_text or clean_ai

    session_details = _extract_heading_block(clean_ai, ['Session Details', 'Session summary', 'Session Summary'])

    presenting = _extract_heading_block(clean_ai, ['Presenting Concerns', 'Chief Complaint', 'Presenting Problem'])

    interventions = _extract_heading_block(clean_ai, ['Collaborative Support', 'Interventions', 'Session Intervention', 'Therapeutic Support'])

    observations = _extract_heading_block(clean_ai, ['Observations', 'Objective', 'Therapist Observations', 'Clinical Observations'])

    homework = _extract_heading_block(clean_ai, ['Homework/Future Planning', 'Homework', 'Future Planning', 'Plan', 'Next Steps', 'Follow-up'])



    if not session_details:

        session_details = make_short_summary(source, 2, 500) or '[Session details not specified]'

    if not presenting:

        presenting = ' '.join(re.findall(r'(?i)(stress[^.?!]*|anxiety[^.?!]*|grief[^.?!]*|sleep[^.?!]*|work[^.?!]*|overwhelm[^.?!]*)', source)) or '[Presenting concerns not specified]'

    if not interventions:

        interventions = '[Interventions not specified]'

    if not observations:

        observations = '[Observations not specified]'

    if not homework:

        homework = '[Plan / follow-up not specified]'



    assessment_line = 'Client presents with concerns discussed in the session; no formal diagnosis was added unless explicitly documented in the source text.'

    structured = f"""SUBJECTIVE:

Session details: {session_details}



Presenting concerns: {presenting}



OBJECTIVE:

Observations: {observations}



Interventions used: {interventions}



ASSESSMENT:

{assessment_line}



PLAN:

Homework / follow-up: {homework}

"""

    summary = make_short_summary(clean_ai or source, 3, 500) or make_short_summary(source, 3, 500) or 'Summary not specified.'

    return structured.strip(), summary.strip()



def build_client_summary_prompt(client_name, notes_json):

    return f"""You are preparing a professional client progress summary for a counseling file.

Rules:

- Improve grammar, readability, and presentation where helpful.

- Do not add facts that are not explicitly supported by the source material.

- Preserve chronology and cite recurring themes carefully.

- Write in a professional counseling tone.



Client: {client_name}

Source records:

{notes_json}



Return exactly in this format:

SUMMARY:

[detailed integrated summary]



KEY THEMES:

[bullet-style themes]



    FOLLOW-UP PRIORITIES:

[follow-up priorities]

"""



def compact_history_entry(entry, fields):

    parts = []

    for label, key in fields:

        value = entry.get(key)

        if value is None or value == '':

            continue

        parts.append(f'{label}: {value}')

    return ' | '.join(parts)



def build_history_timeline(notes, plans):

    timeline = []

    for idx, note in enumerate(notes, start=1):

        content = note.get('structured_content') or note.get('content') or note.get('short_summary') or note.get('ai_summary') or ''

        row = compact_history_entry(note, [

            ('Session', 'created_at'),

            ('Type', 'note_type'),

            ('Therapist', 'therapist_name'),

        ])

        if row:

            row = f'{row} | Session #: {idx}'

        else:

            row = f'Session #: {idx}'

        if content:

            row += f'\nNote: {content}'

        timeline.append(row.strip())

    for idx, plan in enumerate(plans, start=1):

        row = compact_history_entry(plan, [

            ('Plan', 'created_at'),

            ('Review', 'review_date'),

            ('Status', 'status'),

        ])

        if row:

            row = f'{row} | Treatment plan #{idx}'

        else:

            row = f'Treatment plan #{idx}'

        goals = plan.get('goals') or ''

        interventions = plan.get('interventions') or ''

        details = []

        if goals:

            details.append(f'Goals: {goals}')

        if interventions:

            details.append(f'Interventions: {interventions}')

        if details:

            row += '\n' + '\n'.join(details)

        timeline.append(row.strip())

    return timeline



def chunk_lines(lines, max_chars=4500):

    chunks = []

    current = []

    current_len = 0

    for line in lines:

        line = line.strip()

        if not line:

            continue

        extra = len(line) + (2 if current else 0)

        if current and current_len + extra > max_chars:

            chunks.append('\n\n'.join(current))

            current = [line]

            current_len = len(line)

        else:

            current.append(line)

            current_len += extra

    if current:

        chunks.append('\n\n'.join(current))

    return chunks



def build_client_detailed_summary_chunk_prompt(client_name, client_code, therapist_name, chunk_text, chunk_index, chunk_total):

    return f"""You are summarizing one section of a larger counseling file for Aha Psychological Service.

Use only the source material below.



Rules:

- Do not invent facts, diagnoses, or outcomes.

- Keep the writing clinical, factual, and concise.

- Preserve chronology when it is present.

- Extract the important facts, themes, interventions, responses, and plan points.

- If something is missing, do not guess.

- Return plain text only.



Client: {client_name}

Client code: {client_code}

Counselor: {therapist_name}

Chunk: {chunk_index} of {chunk_total}



Source material:

{chunk_text}



Return a compact source summary with these headings:

Chunk Summary:

Key Facts:

Themes:

Plan / Follow-up:

"""



def build_client_detailed_summary_synthesis_prompt(client_name, client_code, therapist_name, chunk_summaries):

    return f"""You are a clinical documentation assistant for Aha Psychological Service.

Write the final detailed client summary using only the chunk summaries below.



Strict rules:

- Do not invent facts, diagnoses, or outcomes.

- Merge repeated information carefully.

- Resolve conflicts only by preferring the most recent clearly dated source.

- Keep the wording clinical, professional, and neutral.

- Return plain text only.

- Follow the exact format below.



Client: {client_name}

Client code: {client_code}

Counselor: {therapist_name}



Chunk summaries:

{chunk_summaries}



Return exactly in this format:

Counseling Session Summary:

Counselor: ____________________________ Session Date: ________________ Time: ________

Client(s) Name: ________________________________________ Code: ____ Session #: Multiple sessions reviewed

1) Subjective assessment: Client's Description history and current status.

1.1) Client's description:



1.2) the overall story of the client:



1.3) Clients personal History:



2) Objective Assessment: Quantitative, factual, and measurable data



3) Case conceptualization, goal setting, and planning set the counseling/therapy goal and outline the plan for future sessions.



Special Attention/Note:

"""



def is_trivial_ai_response(text):

    normalized = re.sub(r'\s+', ' ', (text or '').strip()).lower()

    if not normalized:

        return True

    if normalized in {'ok', 'okay', 'okay.', 'done', 'thanks', 'not specified'}:

        return True

    return len(normalized) < 40



def generate_client_detailed_summary(client_name, client_code, therapist_name, notes, plans):

    timeline = build_history_timeline(notes, plans)

    source_text = '\n\n---\n\n'.join(timeline)

    if not source_text.strip():

        source_text = 'No source records were found.'



    if len(source_text) <= 9000:

        prompt = build_client_detailed_summary_prompt(client_name, client_code, therapist_name, source_text)

        ok, result = call_openai(prompt, model=CLINICAL_AI_MODEL, num_predict=1500)

        if ok and result.strip() and not is_trivial_ai_response(result):

            return True, normalize_structured_text(result), result



    chunks = chunk_lines(timeline, max_chars=4200)

    chunk_summaries = []

    for idx, chunk in enumerate(chunks, start=1):

        prompt = build_client_detailed_summary_chunk_prompt(client_name, client_code, therapist_name, chunk, idx, len(chunks))

        ok, result = call_openai(prompt, model=CLINICAL_AI_MODEL, num_predict=1100)

        if not (ok and result.strip()):

            result = 'Chunk summary unavailable.'

        if is_trivial_ai_response(result):

            result = result.strip() or 'Chunk summary unavailable.'

        chunk_summaries.append(f'Chunk {idx} of {len(chunks)}:\n{result.strip()}')

    synthesis_prompt = build_client_detailed_summary_synthesis_prompt(

        client_name,

        client_code,

        therapist_name,

        '\n\n'.join(chunk_summaries)

    )

    ok, result = call_openai(synthesis_prompt, model=CLINICAL_AI_MODEL, num_predict=1700)

    if ok and result.strip():

        return True, normalize_structured_text(result), result

    return False, result if isinstance(result, str) else 'AI helper unavailable', result



def build_client_detailed_summary_prompt(client_name, client_code, therapist_name, notes_json):

    return f"""You are a clinical documentation assistant for Aha Psychological Service.

Write a detailed, polished client summary for a therapist chart using only the source records.



Strict rules:

- You may rewrite, paraphrase, and professionally polish the writing.

- Improve grammar, punctuation, readability, and presentation.

- Do not invent symptoms, diagnoses, risk, interventions, or outcomes.

- Keep the language professional and clinically neutral.

- If a detail is missing, write "Not specified".

- Return plain text only.

- Do not use markdown bullets unless they are part of the requested numbered structure.

- Review every session note and treatment plan in the source records before writing the summary.

- Synthesize the complete record chronologically and do not skip recurring themes.

- If the source does not support a statement, leave it out or mark it as "Not specified".



Client: {client_name}

Client code: {client_code}

Counselor: {therapist_name}



Source records:

{notes_json}



Return exactly in this format:

Counseling Session Summary:

Counselor: ____________________________ Session Date: ________________ Time: ________

Client(s) Name: ________________________________________ Code: ____ Session #: Multiple sessions reviewed

1) Subjective assessment: Client’s Description history and current status.

1.1) Client’s description:



1.2) the overall story of the client:



1.3) Clients personal History:



2) Objective Assessment: Quantitative, factual, and measurable data



3) Case conceptualization, goal setting, and planning set the counseling/therapy goal and outline the plan for future sessions.



Special Attention/Note:

"""



def build_session_detailed_summary_prompt(client_name, client_code, therapist_name, session_number, note_data):

    return f"""You are a clinical documentation assistant for Aha Psychological Service.

Rewrite one therapist session note into a detailed, professional session summary.



Strict rules:

- You may rewrite, paraphrase, and professionally polish the writing.

- Improve grammar, punctuation, clarity, and professionalism.

- Do not invent symptoms, diagnoses, interventions, outcomes, or risk details.

- Keep the language professional and clinically neutral.

- If a detail is missing, write "Not specified".

- Return plain text only.

- Do not use markdown bullets unless they are part of the requested numbered structure.

- Base the summary only on the source note below.

- Do not add information from other sessions or general clinical assumptions.

- Preserve the order and headings exactly as written below.



Client: {client_name}

Client code: {client_code}

Counselor: {therapist_name}

Session number: {session_number}



Source note:

{note_data}



Return exactly in this format:

Counseling Session Summary & Follow Up

Counselor: ____________________________ Session Date: ________________ Time: ________

Client(s) Name: ________________________________________ Code: ____ Session #: ________

**************************************************************************************

Reflect from previous session and specific compliant:



Session treatment goal:



Assessment of progress:



Session intervention:



Therapeutic plan/next steps:



Special Attention:

"""



def format_appointment_message(appt, action, reason=''):

    client_code = appt.get('client_code') or 'Not specified'

    therapist = appt.get('therapist_name') or 'Unassigned therapist'

    room = room_display_name(appt.get('room') or {'name': appt.get('room_name'), 'code': appt.get('room_code')})

    when = format_datetime_readable(appt.get('start_time'))

    end = format_datetime_readable(appt.get('end_time'))

    status = (appt.get('status') or 'scheduled').replace('_', ' ').strip()

    title = {

        'created': 'New appointment scheduled',

        'cancelled': 'Appointment cancelled',

        'terminated': 'Appointment terminated',

        'no_show': 'Session marked no-show',

        'completed': 'Appointment completed',

        'changed': 'Appointment changed',

        'rescheduled': 'Appointment changed',

    }.get(action, 'Appointment updated')

    return '\n'.join([

        title,

        '',

        f'Client code: {client_code}',

        f'Therapist: {therapist}',

        f'Room: {room}',

        f'Status: {status.title()}',

        f'Date/time: {when}',

        f'End time: {end}',

        f'Reason: {reason or "Not provided"}',

    ])



def build_appointment_message(appt, action, reason='', old_start_time=None, old_end_time=None, change_scope=''):

    client_code = appt.get('client_code') or 'Not specified'

    therapist = appt.get('therapist_name') or 'Unassigned therapist'

    room = room_display_name(appt.get('room') or {'name': appt.get('room_name'), 'code': appt.get('room_code')})

    current_start = format_datetime_readable(appt.get('start_time'))

    current_end = format_datetime_readable(appt.get('end_time'))

    scope = (change_scope or '').strip().lower()

    scope_label = 'Temporary change' if scope == 'temporary' else 'Permanent change' if scope == 'permanent' else 'Update'

    title = {

        'created': 'New appointment scheduled',

        'cancelled': 'Appointment cancelled',

        'terminated': 'Appointment terminated',

        'no_show': 'Appointment marked no-show',

        'completed': 'Appointment completed',

        'changed': 'Appointment changed',

        'rescheduled': 'Appointment rescheduled',

    }.get(action, 'Appointment updated')

    lines = [

        title,

        '',

        f'Client code: {client_code}',

        f'Therapist: {therapist}',

        f'Room: {room}',

        f'Current status: {(appt.get("status") or "scheduled").replace("_", " ")}',

    ]

    if action in ('cancelled', 'terminated', 'no_show'):

        lines.extend([

            f'Date/time: {current_start}',

            f'End time: {current_end}',

            f'Scope: {scope_label}',

        ])

    else:

        if old_start_time:

            lines.append(f'Previous date/time: {format_datetime_readable(old_start_time)}')

        if old_end_time:

            lines.append(f'Previous end time: {format_datetime_readable(old_end_time)}')

        lines.extend([

            f'New date/time: {current_start}',

            f'New end time: {current_end}',

            f'Scope: {scope_label}',

        ])

    lines.append(f'Reason: {reason or "Not provided"}')

    return '\n'.join(lines)


def format_appointment_message(appt, action, reason=''):

    return _appointment_notification_body(appt, action, reason)



def build_appointment_message(appt, action, reason='', old_start_time=None, old_end_time=None, change_scope=''):

    return _appointment_notification_body(
        appt,
        action,
        reason,
        old_start_time=old_start_time,
        old_end_time=old_end_time,
        change_scope=change_scope,
    )



def notify_appointment_update(appt, action, reason='', old_start_time=None, old_end_time=None, change_scope=''):

    subject_map = {

        'created': 'New appointment scheduled',

        'cancelled': 'Appointment cancelled',

        'terminated': 'Appointment terminated',

        'no_show': 'Appointment marked no-show',

        'completed': 'Appointment completed',

        'changed': 'Appointment changed',

        'rescheduled': 'Appointment changed',

    }

    subject = subject_map.get(action, 'Appointment updated')

    body = build_appointment_message(appt, action, reason, old_start_time=old_start_time, old_end_time=old_end_time, change_scope=change_scope)

    roles = ['admin', 'receptionist']

    if action in ('created', 'changed', 'rescheduled', 'cancelled', 'terminated', 'no_show', 'completed'):

        notify_roles(roles, subject, body)

    notify_user(appt.get('therapist_id'), subject, body)

    return subject, body



def notify_daily_schedule(date_str=None):

    if date_str:

        try:

            target_day = datetime.fromisoformat(str(date_str)).date()

        except Exception:

            target_day = now_in_eat().date()

    else:

        target_day = now_in_eat().date()


    day_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0, tzinfo=EAT)

    day_end = day_start + timedelta(days=1)


    with get_db() as conn:

        therapists = conn.execute("""

            SELECT DISTINCT u.id, u.full_name, u.telegram_chat_id

            FROM users u

            JOIN appointments a ON a.therapist_id=u.id

            WHERE u.role='therapist' AND u.is_active=1

              AND a.start_time >= ? AND a.start_time < ?

        """, (day_start.isoformat(), day_end.isoformat())).fetchall()

        for therapist in therapists:

            appts = conn.execute("""

                SELECT a.start_time, a.end_time, c.full_name as client_name, c.client_code, a.location, a.type, r.name as room_name, r.code as room_code

                FROM appointments a

                LEFT JOIN clients c ON a.client_id=c.id

                LEFT JOIN rooms r ON a.room_id=r.id

                WHERE a.therapist_id=? AND a.start_time >= ? AND a.start_time < ? AND a.status IN ('scheduled', 'confirmed')

                ORDER BY a.start_time ASC

            """, (therapist['id'], day_start.isoformat(), day_end.isoformat())).fetchall()

            if not appts:

                continue

            lines = [

                f'\U0001f305 <b>Good morning, {therapist["full_name"]}</b>',

                f'Here is your schedule for <b>{target_day.strftime("%A, %B %d, %Y")}</b> (Ethiopia time).',

                '',

                f'You have <b>{len(appts)}</b> session(s) today.',

                '',

            ]

            for idx, appt in enumerate(appts, 1):

                room_name = appt['room_name'] or appt['room_code'] or 'Unassigned room'

                lines.append(

                    f'{idx}. <b>{format_datetime_readable(appt["start_time"])} </b> - {appt["client_name"] or "Client"} <code>{appt["client_code"] or "No code"}</code>\\n'

                    f'   \u2022 Session type: {appt["type"] or "Session"}\\n'

                    f'   \u2022 Location: {appt["location"] or "Not specified"}\\n'

                    f'   \u2022 Room: {room_name}'

                )

            send_telegram_message(therapist['telegram_chat_id'], '\\n'.join(lines), parse_mode='HTML')


def handle_telegram_update(update):
    BASE_URL = APP_BASE_URL

    def get_portal_url(user_obj=None):
        if not user_obj:
            return f'{BASE_URL}/login'
        return portal_url_for_role(user_obj.get('role', ''))

    # helpers
    def kb(*rows):
        keyboard = []
        for row in rows:
            btn_row = []
            for label, target in row:
                if target.startswith('URL:'):
                    btn_row.append({'text': label, 'url': target[4:]})
                elif target.startswith('WEBAPP:'):
                    btn_row.append({'text': label, 'web_app': {'url': target[7:]}})
                else:
                    btn_row.append({'text': label, 'callback_data': target})
            keyboard.append(btn_row)
        return {'inline_keyboard': keyboard}

    def msg(chat_id, text, markup=None):
        send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=markup)

    def portal_btn(user_obj=None, label='🌐 Open Portal'):
        return kb([[(label, f'WEBAPP:{get_portal_url(user_obj)}')]])

    def main_menu_kb(user_obj=None):
        return kb(
            [('📅 Appointments', '/appointments'), ('👤 Profile', '/profile')],
            [('❓ Help', '/help'), ('📞 Contact', '/contact')],
            [(f'🌐 Open Portal', f'WEBAPP:{get_portal_url(user_obj)}')]
        )

    # parse incoming message — handle both messages and callback_query
    callback_query = update.get('callback_query')
    if callback_query:
        chat_id = str(callback_query.get('from', {}).get('id', ''))
        text = callback_query.get('data', '')
        telegram_api('answerCallbackQuery', {'callback_query_id': callback_query['id']})
        telegram_username = callback_query.get('from', {}).get('username', '')
    else:
        message = update.get('message') or update.get('edited_message') or {}
        text = (message.get('text') or '').strip()
        chat = message.get('chat') or {}
        chat_id = str(chat.get('id') or '')
        telegram_username = message.get('from', {}).get('username', '')

    if not chat_id:
        return False

    raw_command = text.split(maxsplit=1)[0].lower() if text.startswith('/') else ''
    command = raw_command.split('@', 1)[0] if raw_command else ''
    command_args = text[len(raw_command):].strip() if raw_command else ''

    print(f'[TELEGRAM] update: chat_id={chat_id}, command={command!r}, text={text[:60]!r}')

    # lookup linked user
    user = None
    with get_db() as conn:
        user = conn.execute(
            'SELECT * FROM users WHERE telegram_chat_id=?', (chat_id,)
        ).fetchone()

    # /start
    if command == '/start':
        code = command_args.strip()

        if user and not code:
            role_emoji = {'admin': '🔐', 'therapist': '👨‍⚕️', 'receptionist': '👩‍💼', 'client': '👤'}.get(user['role'], '👤')
            msg(chat_id,
                f"👋 Welcome back, <b>{user['full_name'] or user['username']}</b>!\n\n"
                f"{role_emoji} <i>{user['role'].capitalize()}</i> · Aha Psychological Service\n\n"
                f"What would you like to do today?",
                main_menu_kb(user))
            return True

        if not code:
            msg(chat_id,
                "👋 <b>Welcome to Aha Psychological Service!</b>\n\n"
                "To get started, link your staff account:\n\n"
                "1️⃣ Log in to the <b>Admin Portal</b>\n"
                "2️⃣ Go to <b>Settings → Telegram</b>\n"
                "3️⃣ Click <b>Generate Link Code</b>\n"
                "4️⃣ Reply here with: <code>/start YOUR_CODE</code>\n\n"
                "Need help? Type /help",
                kb([[(f'🌐 Open Portal', f'URL:{BASE_URL}/login')]]))
            return True

        # validate and link
        with get_db() as conn:
            link = conn.execute(
                'SELECT * FROM telegram_link_codes WHERE code=? AND used_at IS NULL',
                (code,)
            ).fetchone()

            if not link:
                msg(chat_id,
                    "❌ <b>Invalid or expired code.</b>\n\n"
                    "Please generate a new one from the Admin Portal.",
                    kb([[(f'🌐 Get New Code', f'URL:{BASE_URL}/login')]]))
                return True

            linked_user = conn.execute('SELECT * FROM users WHERE id=?', (link['user_id'],)).fetchone()

            if not linked_user:
                msg(chat_id, "❌ User not found. Please contact your administrator.")
                return True

            conn.execute(
                'UPDATE users SET telegram_chat_id=?, telegram_username=?, telegram_linked_at=? WHERE id=?',
                (chat_id, telegram_username, datetime.now().isoformat(), link['user_id'])
            )
            conn.execute(
                'UPDATE telegram_link_codes SET used_at=?, telegram_chat_id=?, telegram_username=? WHERE id=?',
                (datetime.now().isoformat(), chat_id, telegram_username, link['id'])
            )
            conn.commit()
            user = linked_user

        role_emoji = {'admin': '🔐', 'therapist': '👨‍⚕️', 'receptionist': '👩‍💼', 'client': '👤'}.get(user['role'], '👤')
        msg(chat_id,
            f"✅ <b>Account linked successfully!</b>\n\n"
            f"Welcome, <b>{user['full_name'] or user['username']}</b>!\n"
            f"{role_emoji} <i>{user['role'].capitalize()}</i>\n\n"
            f"You will now receive instant notifications for:\n"
            f"• 📅 Appointment reminders\n"
            f"• 🎉 New client assignments\n"
            f"• 📨 Internal messages\n\n"
            f"Tap a button below to get started 👇",
            main_menu_kb())
        return True

    # all other commands require a linked account
    if not user:
        msg(chat_id,
            "❌ <b>Your account is not linked yet.</b>\n\n"
            "Send /start to see how to link your account.",
            kb([[(f'🌐 Open Portal', f'URL:{BASE_URL}/login')]]))
        return True

    # /appointments
    if command in ('/appointments', '/appointment', '/appts'):
        user_role = user.get('role', '')
        appts = []

        with get_db() as conn:
            if user_role == 'therapist':
                appts = conn.execute(
                    """SELECT a.*, c.full_name as client_name, r.name as room_name
                       FROM appointments a
                       LEFT JOIN clients c ON a.client_id=c.id
                       LEFT JOIN rooms r ON a.room_id=r.id
                       WHERE a.therapist_id=? AND a.status IN ('scheduled','confirmed')
                       AND a.start_time > ? ORDER BY a.start_time LIMIT 10""",
                    (user['id'], datetime.now().isoformat())
                ).fetchall()
            elif user_role in ('admin', 'receptionist'):
                appts = conn.execute(
                    """SELECT a.*, c.full_name as client_name, r.name as room_name,
                              u.full_name as therapist_name
                       FROM appointments a
                       LEFT JOIN clients c ON a.client_id=c.id
                       LEFT JOIN rooms r ON a.room_id=r.id
                       LEFT JOIN users u ON a.therapist_id=u.id
                       WHERE a.status IN ('scheduled','confirmed')
                       AND a.start_time > ? ORDER BY a.start_time LIMIT 10""",
                    (datetime.now().isoformat(),)
                ).fetchall()

        if not appts:
            msg(chat_id,
                "📭 <b>No upcoming appointments.</b>\n\n"
                "All appointments will appear here once scheduled.",
                portal_btn(user, '📅 Schedule on Portal'))
            return True

        lines_out = [f"📅 <b>Upcoming Appointments ({len(appts)})</b>\n"]
        for i, a in enumerate(appts, 1):
            d = dict(a)
            date_str = str(d.get('start_time', ''))[:10]
            time_str = str(d.get('start_time', ''))[11:16]
            room = d.get('room_name') or d.get('location') or 'TBD'
            therapist = d.get('therapist_name', '')
            lines_out.append(
                f"<b>{i}.</b> {d.get('client_name','Client')}\n"
                f"   📆 {date_str} at {time_str}\n"
                f"   🚪 Room: {room}"
                + (f"\n   👨‍⚕️ {therapist}" if therapist and user_role in ('admin', 'receptionist') else '')
                + "\n"
            )

        msg(chat_id, '\n'.join(lines_out), portal_btn(user, '📅 Full Schedule on Portal'))
        return True

    # /profile
    if command in ('/profile', '/me'):
        role_emoji = {'admin': '🔐', 'therapist': '👨‍⚕️', 'receptionist': '👩‍💼', 'client': '👤'}.get(user['role'], '👤')
        status = '✅ Active' if user.get('is_active') else '❌ Inactive'
        msg(chat_id,
            f"👤 <b>Your Profile</b>\n\n"
            f"<b>Name:</b> {user.get('full_name') or 'Not set'}\n"
            f"<b>Username:</b> @{user.get('username', '')}\n"
            f"<b>Role:</b> {role_emoji} {user['role'].capitalize()}\n"
            f"<b>Status:</b> {status}\n\n"
            f"<b>Email:</b> {user.get('email') or '—'}\n"
            f"<b>Phone:</b> {user.get('phone') or '—'}\n\n"
            f"<b>Specialization:</b> {user.get('specialization') or '—'}\n"
            f"<b>Languages:</b> {user.get('languages') or 'English'}\n\n"
            f"🔗 <i>Telegram linked ✅</i>",
            kb(
                [('⬅️ Main Menu', '/start')],
                [(f'🌐 Edit Profile on Portal', f'URL:{get_portal_url(user)}')]
            ))
        return True

    # /help
    if command in ('/help', '/?', '/commands'):
        msg(chat_id,
            "📖 <b>Available Commands</b>\n\n"
            "<b>🔐 Account</b>\n"
            "/start — Link or re-link your account\n"
            "/profile — View your profile\n"
            "/cancel — Unlink your account\n\n"
            "<b>📅 Appointments</b>\n"
            "/appointments — View upcoming appointments\n\n"
            "<b>❓ Support</b>\n"
            "/help — Show this message\n"
            "/contact — Contact information\n\n"
            "Or tap the buttons below to navigate!",
            main_menu_kb(user))
        return True

    # /contact
    if command in ('/contact', '/support'):
        msg(chat_id,
            "📞 <b>Contact Aha Psychological Service</b>\n\n"
            "📧 <b>Email:</b> info@ahapsychological.com\n"
            "🌐 <b>Website:</b> aha-psychological-service.vercel.app\n\n"
            "🕐 <b>Hours:</b>\n"
            "Mon–Fri: 9:00 AM – 6:00 PM\n"
            "Saturday: 10:00 AM – 4:00 PM\n"
            "Sunday: Closed\n\n"
            "💬 <i>For urgent matters, please call us directly.</i>",
            portal_btn(user, '🌐 Visit Website'))
        return True

    # /cancel (unlink)
    if command in ('/cancel', '/unlink'):
        msg(chat_id,
            "⚠️ <b>Unlink your account?</b>\n\n"
            "You will stop receiving Telegram notifications.\n"
            "You can re-link at any time.\n\n"
            "Tap <b>Confirm Unlink</b> below to proceed.",
            kb(
                [('🔴 Confirm Unlink', 'CONFIRM_UNLINK')],
                [('✅ Keep Connected', 'CANCEL_UNLINK')]
            ))
        return True

    # inline button callbacks
    if text == 'CONFIRM_UNLINK':
        with get_db() as conn:
            conn.execute('UPDATE users SET telegram_chat_id=NULL WHERE id=?', (user['id'],))
            conn.commit()
        msg(chat_id,
            "✅ <b>Account unlinked.</b>\n\n"
            "You have been disconnected from Telegram notifications.\n"
            "Send /start anytime to reconnect.")
        return True

    if text == 'CANCEL_UNLINK':
        msg(chat_id,
            "✅ <b>No changes made.</b>\n\n"
            "Your account is still connected!",
            main_menu_kb(user))
        return True

    # default / unknown
    msg(chat_id,
        f"👋 Hi <b>{user.get('full_name') or user.get('username')}</b>!\n\n"
        f"I did not recognise that command. Use the menu below 👇",
        main_menu_kb(user))
    return True


def telegram_polling_loop():

    print('[TELEGRAM] Starting polling loop...')

    try:

        telegram_api('deleteWebhook', {'drop_pending_updates': False})

        print('[TELEGRAM] Webhook deleted')

    except Exception as e:

        print(f'[TELEGRAM] Error deleting webhook: {e}')

    offset = 0

    try:

        offset = int(get_setting('telegram_update_offset', '0') or '0')

    except Exception:

        offset = 0

    print(f'[TELEGRAM] Polling starting with offset: {offset}')

    while True:

        try:

            ok, payload = telegram_api_get('getUpdates', {'offset': offset, 'timeout': 20}, timeout=25)

            if not ok:

                print(f'[TELEGRAM] getUpdates failed: {payload}')

                time.sleep(5)

                continue

            updates = payload.get('result', [])

            if updates:

                print(f'[TELEGRAM] Received {len(updates)} update(s)')

            for update in updates:

                try:

                    update_id = int(update.get('update_id', 0))

                    offset = max(offset, update_id + 1)

                    set_setting('telegram_update_offset', offset)

                    print(f'[TELEGRAM] Processing update {update_id}')

                    handle_telegram_update(update)

                except Exception as e:

                    print(f'[TELEGRAM] Error handling update: {e}')

                    continue

        except Exception as e:

            print(f'[TELEGRAM] Polling error: {e}')

            time.sleep(5)



def start_telegram_polling():

    global TELEGRAM_POLLING_ACTIVE

    token = get_bot_token()

    print(f'[TELEGRAM] start_telegram_polling called. Token present: {bool(token)}')

    if not token:

        print('[TELEGRAM] No bot token configured!')

        return

    if os.getenv('AHA_ENABLE_TELEGRAM_POLLING', '1') != '1':

        print('[TELEGRAM] Polling disabled via AHA_ENABLE_TELEGRAM_POLLING')

        return

    marker = getattr(app, '_telegram_polling_started', False)

    if marker:

        print('[TELEGRAM] Polling already started')

        return

    print('[TELEGRAM] Starting telegram polling thread...')

    app._telegram_polling_started = True

    TELEGRAM_POLLING_ACTIVE = True

    thread = threading.Thread(target=telegram_polling_loop, daemon=True)

    thread.start()

    print('[TELEGRAM] Polling thread started')



def telegram_scheduler_loop():

    while True:

        now = datetime.now()

        next_run = now.replace(hour=7, minute=0, second=0, microsecond=0)

        if next_run <= now:

            next_run += timedelta(days=1)

        time.sleep(max(30, int((next_run - now).total_seconds())))

        try:

            notify_daily_schedule()

        except Exception:

            pass



def start_telegram_scheduler():

    if not get_bot_token():

        return

    if os.getenv('AHA_ENABLE_TELEGRAM_SCHEDULER', '1') != '1':

        return

    marker = getattr(app, '_telegram_scheduler_started', False)

    if marker:

        return

    app._telegram_scheduler_started = True

    thread = threading.Thread(target=telegram_scheduler_loop, daemon=True)

    thread.start()



# Startup: only run on persistent servers, not Vercel serverless
_is_vercel = os.getenv('VERCEL', '') or os.getenv('VERCEL_ENV', '')
if not _is_vercel:
    try:
        init_db()
    except Exception as _e:
        print(f'[STARTUP] init_db failed: {_e}')

    start_telegram_scheduler()
    start_telegram_polling()
else:
    # On Vercel, init DB lazily on first request
    try:
        init_db()
    except Exception as _e:
        print(f'[VERCEL STARTUP] init_db failed (DB may not be set): {_e}')

    # On Vercel, register Telegram webhook automatically so the bot works
    def _register_telegram_webhook():
        token = get_bot_token()
        if not token:
            print('[TELEGRAM] No bot token - skipping webhook registration')
            return
        app_url = os.getenv('APP_URL', '').rstrip('/')
        if not app_url:
            # Fall back to known production domain - works across all deployments
            app_url = 'https://aha-psychological-service.vercel.app'
        webhook_url = f'{app_url}/api/telegram/webhook'
        try:
            ok, result = telegram_api('setWebhook', {
                'url': webhook_url,
                'allowed_updates': ['message', 'callback_query'],
                'drop_pending_updates': False
            })
            print(f'[TELEGRAM] Auto setWebhook -> {webhook_url} -> ok={ok}')
        except Exception as exc:
            print(f'[TELEGRAM] setWebhook failed: {exc}')

    try:
        _register_telegram_webhook()
    except Exception as _we:
        print(f'[TELEGRAM] Webhook registration error: {_we}')




# ─────────────────────────────────────────────

# AUTH ROUTES

# ─────────────────────────────────────────────

@app.route('/api/login', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])

def login():

    if request.method == 'POST':

        username = request.form.get('username', '').strip()

        password = request.form.get('password', '')

        # Legacy admin support

        if username == 'admin' and password == 'admin':

            with get_db() as conn:

                user = conn.execute('SELECT * FROM users WHERE username=?', ('admin',)).fetchone()

                if user:

                    session['user'] = dict(user)

                    session['logged_in'] = True

                    return redirect('/portals/admin_portal.html')

        with get_db() as conn:

            user = conn.execute('SELECT * FROM users WHERE username=? AND is_active=1', (username,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):

            session['user'] = dict(user)

            session['logged_in'] = True

            with get_db() as conn:

                conn.execute('UPDATE users SET last_login=? WHERE id=?', (datetime.now().isoformat(), user['id']))

                conn.commit()

            role = user['role']

            if role == 'admin':

                return redirect('/portals/admin_portal.html')

            elif role == 'receptionist':

                return redirect('/portals/reception_portal.html')

            elif role == 'therapist':

                return redirect('/portals/therapist_portal.html')

            elif role == 'supervisor':

                return redirect('/portals/supervisor_portal.html')

            else:

                return redirect('/portals/admin_portal.html')

        return send_from_directory('.', 'login.html')

    return send_from_directory('.', 'login.html')



@app.route('/logout')

def logout():

    session.clear()

    return redirect('/login')



@app.route('/admin')

def admin():

    if not session.get('logged_in'):

        return redirect('/login')

    return redirect('/portals/admin_portal.html')



# ─────────────────────────────────────────────

# PORTAL ROUTES (serve HTML files)

# ─────────────────────────────────────────────

@app.route('/portals/<path:filename>')
def serve_portal(filename):
    if filename != 'intake_form.html' and not session.get('logged_in'):
        return redirect('/login')
    
    response = make_response(send_from_directory('portals', filename))
    # Prevent Vercel edge and browser caching for portal files
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/book-appointment')

def book_appointment():

    return redirect('/portals/intake_form.html')



# ─────────────────────────────────────────────

# API: USERS

# ─────────────────────────────────────────────

@app.route('/api/users', methods=['GET'])

def get_users():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        users = [dict(r) for r in conn.execute('SELECT id,username,email,full_name,role,phone,specialization,languages,gender,max_caseload,is_active,last_login,created_at,telegram_chat_id,telegram_username,telegram_linked_at FROM users ORDER BY created_at DESC').fetchall()]

    return jsonify(users)



@app.route('/api/users', methods=['POST'])

def create_user():

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or request.form

    username = data.get('username', '').strip()

    password = data.get('password', 'changeme123')

    email = data.get('email', '')

    role = data.get('role', 'receptionist')

    full_name = data.get('full_name', '')

    phone = data.get('phone', '')

    specialization = data.get('specialization', '')

    languages = data.get('languages', 'English')

    gender = data.get('gender', '')

    max_caseload = int(data.get('max_caseload', 20))

    try:

        with get_db() as conn:

            conn.execute('INSERT INTO users (username,email,password_hash,role,full_name,phone,specialization,languages,gender,max_caseload) VALUES (?,?,?,?,?,?,?,?,?,?)',

                         (username, email, generate_password_hash(password), role, full_name, phone, specialization, languages, gender, max_caseload))

            conn.commit()

        log_action(current_user()['id'], 'CREATE_USER', 'users', f'Created {username} as {role}')

        return jsonify({'success': True})

    except Exception as e:

        if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():

            return jsonify({'error': 'Username already exists'}), 409

        raise



@app.route('/api/users/<int:uid>', methods=['PUT'])

def update_user(uid):

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        if 'is_active' in data:

            conn.execute('UPDATE users SET is_active=? WHERE id=?', (data['is_active'], uid))

        if 'role' in data:

            conn.execute('UPDATE users SET role=? WHERE id=?', (data['role'], uid))

        if 'max_caseload' in data:

            conn.execute('UPDATE users SET max_caseload=? WHERE id=?', (data['max_caseload'], uid))

        if 'full_name' in data:

            conn.execute('UPDATE users SET full_name=?,email=?,phone=?,specialization=?,languages=?,gender=? WHERE id=?',

                         (data.get('full_name',''), data.get('email',''), data.get('phone',''),

                          data.get('specialization',''), data.get('languages','English'), data.get('gender',''), uid))

        conn.commit()

    return jsonify({'success': True})



@app.route('/api/users/<int:uid>', methods=['DELETE'])

def hard_delete_user(uid):

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    try:
        with get_db() as conn:
            conn.execute('DELETE FROM users WHERE id=?', (uid,))
            conn.commit()

        if current_user():

            log_action(current_user()['id'], 'DELETE_USER', 'users', f'Deleted user id {uid}')

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Failed to delete user: {e}'}), 500



# ─────────────────────────────────────────────

# API: CLIENTS

# ─────────────────────────────────────────────

@app.route('/api/clients', methods=['GET'])

def get_clients():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    user = current_user()

    with get_db() as conn:

        if user['role'] == 'therapist':

            rows = conn.execute('SELECT c.*, u.full_name as therapist_name FROM clients c LEFT JOIN users u ON c.assigned_therapist_id=u.id WHERE c.assigned_therapist_id=? ORDER BY c.registration_date DESC', (user['id'],)).fetchall()

        else:

            rows = conn.execute('SELECT c.*, u.full_name as therapist_name FROM clients c LEFT JOIN users u ON c.assigned_therapist_id=u.id ORDER BY c.registration_date DESC').fetchall()

    return jsonify([dict(r) for r in rows])



@app.route('/api/clients', methods=['POST'])
def create_client():
    if not require_role('admin', 'receptionist'):
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}
    code = generate_client_code()
    assigned_therapist_id = data.get('assigned_therapist_id') or None

    with get_db() as conn:
        cur = conn.execute('''INSERT INTO clients (full_name,date_of_birth,gender,phone,email,address,
            emergency_contact_name,emergency_contact_phone,language_pref,therapist_gender_pref,
            intake_source,notes,client_code,status,assigned_therapist_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('full_name',''), data.get('date_of_birth',''), data.get('gender',''),
             data.get('phone',''), data.get('email',''), data.get('address',''),
             data.get('emergency_contact_name',''), data.get('emergency_contact_phone',''),
             data.get('language_pref','English'), data.get('therapist_gender_pref','No Preference'),
             data.get('intake_source','walk-in'), data.get('notes',''), code, 'registered',
             assigned_therapist_id))

        client_id = cur.lastrowid

        conn.execute('INSERT INTO client_journey (client_id, stage, changed_by, notes) VALUES (?,?,?,?)',
                     (client_id, 'registered', current_user()['id'], 'Client registered'))

        conn.commit()

    log_action(current_user()['id'], 'CREATE_CLIENT', 'clients', f'Registered client {code}')
    return jsonify({'success': True, 'client_id': client_id, 'client_code': code}), 201




@app.route('/api/clients/<int:cid>', methods=['GET'])

def get_client(cid):

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        client = conn.execute('SELECT c.*, u.full_name as therapist_name FROM clients c LEFT JOIN users u ON c.assigned_therapist_id=u.id WHERE c.id=?', (cid,)).fetchone()

        journey = conn.execute('SELECT j.*, u.full_name as changed_by_name FROM client_journey j LEFT JOIN users u ON j.changed_by=u.id WHERE j.client_id=? ORDER BY j.changed_at DESC', (cid,)).fetchall()

        appointments = conn.execute('SELECT a.*, u.full_name as therapist_name FROM appointments a LEFT JOIN users u ON a.therapist_id=u.id WHERE a.client_id=? ORDER BY a.start_time DESC', (cid,)).fetchall()

        screening = conn.execute('SELECT * FROM screening_responses WHERE client_id=? ORDER BY submitted_at DESC', (cid,)).fetchall()

        intake_forms = conn.execute('SELECT * FROM intake_forms WHERE client_id=? ORDER BY submission_date DESC', (cid,)).fetchall()

        assessments = conn.execute('''SELECT s.*, t.name as template_name

                                      FROM assessment_submissions s

                                      LEFT JOIN assessment_templates t ON s.template_id=t.id

                                      WHERE s.client_id=? ORDER BY s.created_at DESC''', (cid,)).fetchall()

        invoices = conn.execute('SELECT * FROM invoices WHERE client_id=? ORDER BY issue_date DESC', (cid,)).fetchall()

    if not client:

        return jsonify({'error': 'Not found'}), 404

    return jsonify({

        'client': dict(client),

        'journey': [dict(j) for j in journey],

        'appointments': [dict(a) for a in appointments],

        'screening': [dict(s) for s in screening],

        'intake_forms': [dict(f) for f in intake_forms],

        'assessments': [dict(a) for a in assessments],

        'invoices': [dict(i) for i in invoices],

    })



@app.route('/api/clients/<int:cid>', methods=['PUT'])

def update_client(cid):

    if not require_role('admin', 'receptionist', 'therapist'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        if 'status' in data:

            conn.execute('UPDATE clients SET status=? WHERE id=?', (data['status'], cid))

            conn.execute('INSERT INTO client_journey (client_id, stage, changed_by, notes) VALUES (?,?,?,?)',

                         (cid, data['status'], current_user()['id'], data.get('notes', '')))

            if data['status'] == 'terminated':

                conn.execute('UPDATE clients SET notes=COALESCE(notes,"") || ? WHERE id=?',

                             (f"\n\nTermination reason: {data.get('notes', '')}", cid))

        if 'assigned_therapist_id' in data:

            conn.execute('UPDATE clients SET assigned_therapist_id=?,status=? WHERE id=?',

                         (data['assigned_therapist_id'], 'assigned', cid))

            conn.execute('INSERT INTO client_journey (client_id, stage, changed_by, notes) VALUES (?,?,?,?)',

                         (cid, 'assigned', current_user()['id'], f"Assigned to therapist ID {data['assigned_therapist_id']}"))

            conn.execute('INSERT INTO messages (sender_id,recipient_id,client_id,subject,body,channel) VALUES (?,?,?,?,?,?)',

                         (current_user()['id'], data['assigned_therapist_id'], cid, 'New client assigned',

                          f'You have been assigned client ID {cid}.', 'internal'))

        if 'risk_level' in data:

            conn.execute('UPDATE clients SET risk_level=? WHERE id=?', (data['risk_level'], cid))

        if 'full_name' in data:

            conn.execute('''UPDATE clients SET full_name=?,date_of_birth=?,gender=?,phone=?,email=?,

                address=?,emergency_contact_name=?,emergency_contact_phone=?,

                language_pref=?,therapist_gender_pref=?,notes=? WHERE id=?''',

                (data.get('full_name',''), data.get('date_of_birth',''), data.get('gender',''),

                 data.get('phone',''), data.get('email',''), data.get('address',''),

                 data.get('emergency_contact_name',''), data.get('emergency_contact_phone',''),

                 data.get('language_pref','English'), data.get('therapist_gender_pref','No Preference'),

                  data.get('notes',''), cid))

        conn.commit()

    try:

        if data.get('assigned_therapist_id'):

            with get_db() as conn:

                client = conn.execute('SELECT full_name, client_code FROM clients WHERE id=?', (cid,)).fetchone()

            if client:

                body = f"""You have been assigned a new client!

<b>Client:</b> {client["full_name"]}
<b>Code:</b> {client["client_code"]}

<a href='https://aha-psychological-service.vercel.app/admin'>Open Admin Portal 🌐</a>"""

                notify_user(data['assigned_therapist_id'], '🎉 New Client Assigned', body)

    except Exception:

        pass

    return jsonify({'success': True})



# ─────────────────────────────────────────────

# API: APPOINTMENTS

# ─────────────────────────────────────────────

@app.route('/api/appointments', methods=['GET'])

def get_appointments():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    user = current_user()

    start = request.args.get('start')

    end = request.args.get('end')

    with get_db() as conn:

        query = '''SELECT a.*, c.full_name as client_name, c.client_code as client_code, u.full_name as therapist_name,

                          r.name as room_name, r.code as room_code, r.color as room_color

                   FROM appointments a

                   LEFT JOIN clients c ON a.client_id=c.id

                   LEFT JOIN users u ON a.therapist_id=u.id

                   LEFT JOIN rooms r ON a.room_id=r.id'''

        params = []

        conditions = []

        if user['role'] == 'therapist':

            conditions.append('a.therapist_id=?')

            params.append(user['id'])

        if start:

            conditions.append('a.start_time::date >= %s::date')

            params.append(start)

        if end:

            conditions.append('a.start_time::date <= %s::date')

            params.append(end)

        if conditions:

            query += ' WHERE ' + ' AND '.join(conditions)

        query += ' ORDER BY a.start_time ASC'

        rows = conn.execute(query, params).fetchall()

    return jsonify([dict(r) for r in rows])



@app.route('/api/appointments/<int:aid>', methods=['GET'])

def get_appointment(aid):

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    user = current_user()

    with get_db() as conn:

        query = '''SELECT a.*, c.full_name as client_name, c.client_code as client_code, u.full_name as therapist_name,

                          r.name as room_name, r.code as room_code, r.color as room_color

                   FROM appointments a

                   LEFT JOIN clients c ON a.client_id=c.id

                   LEFT JOIN users u ON a.therapist_id=u.id

                   LEFT JOIN rooms r ON a.room_id=r.id

                   WHERE a.id=?'''

        params = [aid]

        if user['role'] == 'therapist':

            query += ' AND a.therapist_id=?'

            params.append(user['id'])

        row = conn.execute(query, params).fetchone()

    if not row:

        return jsonify({'error': 'Not found'}), 404

    return jsonify(dict(row))



@app.route('/api/appointments', methods=['POST'])

def create_appointment():

    if not require_role('admin', 'receptionist', 'therapist'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    is_recurring = data.get('is_recurring', False)

    

    with get_db() as conn:

        if is_recurring:

            start_dt = datetime.fromisoformat(data.get('start_time'))

            end_dt = datetime.fromisoformat(data.get('end_time')) if data.get('end_time') else start_dt + timedelta(hours=1)

            

            first_appt_id = None

            for i in range(24):

                cur_start = (start_dt + timedelta(days=7*i)).isoformat()

                cur_end = (end_dt + timedelta(days=7*i)).isoformat()

                preferred_room_id = data.get('room_id')

                room_id = choose_room_for_slot(cur_start, cur_end, preferred_room_id=preferred_room_id)

                

                cur = conn.execute('''INSERT INTO appointments (client_id,therapist_id,room_id,start_time,end_time,type,status,location,notes,created_by)

                    VALUES (?,?,?,?,?,?,?,?,?,?)''',

                    (data.get('client_id'), data.get('therapist_id'), room_id, cur_start, cur_end,

                     data.get('type','individual'), data.get('status','scheduled'),

                     data.get('location','In-Person'), data.get('notes','') + (' (Recurring)' if i>0 else ''), current_user()['id']))

                if i == 0:

                    first_appt_id = cur.lastrowid

                

            conn.commit()

            if first_appt_id:

                appt = conn.execute('''SELECT a.*, c.full_name as client_name, c.client_code as client_code, u.full_name as therapist_name,

                                              r.name as room_name, r.code as room_code, r.color as room_color

                                       FROM appointments a

                                       LEFT JOIN clients c ON a.client_id=c.id

                                       LEFT JOIN users u ON a.therapist_id=u.id

                                       LEFT JOIN rooms r ON a.room_id=r.id

                                       WHERE a.id=?''', (first_appt_id,)).fetchone()

                if appt:

                    notify_user(appt['therapist_id'], 'New appointment scheduled',

                                format_appointment_message(dict(appt), 'created'))

            return jsonify({'success': True, 'id': first_appt_id}), 201

        else:

            room_id = choose_room_for_slot(data.get('start_time'), data.get('end_time') or data.get('start_time'), preferred_room_id=data.get('room_id'))

            cur = conn.execute('''INSERT INTO appointments (client_id,therapist_id,room_id,start_time,end_time,type,status,location,notes,created_by)

                VALUES (?,?,?,?,?,?,?,?,?,?)''',

                (data.get('client_id'), data.get('therapist_id'), room_id, data.get('start_time'),

                 data.get('end_time'), data.get('type','individual'), data.get('status','scheduled'),

                 data.get('location','In-Person'), data.get('notes',''), current_user()['id']))

            appt_id = cur.lastrowid

            conn.execute('INSERT INTO appointment_history (appointment_id,action,performed_by,reason) VALUES (?,?,?,?)',

                         (appt_id, 'created', current_user()['id'], 'Initial booking'))

            conn.commit()

            appt = conn.execute('''SELECT a.*, c.full_name as client_name, c.client_code as client_code, u.full_name as therapist_name,

                                          r.name as room_name, r.code as room_code, r.color as room_color

                                   FROM appointments a

                                   LEFT JOIN clients c ON a.client_id=c.id

                                   LEFT JOIN users u ON a.therapist_id=u.id

                                   LEFT JOIN rooms r ON a.room_id=r.id

                                   WHERE a.id=?''', (appt_id,)).fetchone()

            if appt:

                notify_user(appt['therapist_id'], 'New appointment scheduled',

                            format_appointment_message(dict(appt), 'created'))

    return jsonify({'success': True, 'id': appt_id}), 201



@app.route('/api/appointments/<int:aid>', methods=['PUT'])

def update_appointment(aid):

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        current = conn.execute('''SELECT a.*, r.name as room_name, r.code as room_code, r.color as room_color

                                  FROM appointments a

                                  LEFT JOIN rooms r ON a.room_id=r.id

                                  WHERE a.id=?''', (aid,)).fetchone()

        if not current:

            return jsonify({'error': 'Not found'}), 404

        old_start_time = current['start_time']

        old_end_time = current['end_time']

        updates = []

        params = []

        action = data.get('action') or data.get('status')

        reason = data.get('reason') or data.get('cancel_reason') or data.get('change_reason') or ''

        if 'status' in data:

            updates.append('status=?')

            params.append(data['status'])

        if 'notes' in data:

            updates.append('notes=?')

            params.append(data['notes'])

        if 'start_time' in data:

            updates.append('start_time=?')

            params.append(data['start_time'])

        if 'end_time' in data:

            updates.append('end_time=?')

            params.append(data['end_time'])

        if 'room_id' in data:

            updates.append('room_id=?')

            params.append(data['room_id'] or None)

        if data.get('status') == 'cancelled' or 'cancel_reason' in data:

            updates.append('cancel_reason=?')

            params.append(reason)

            updates.append('cancelled_by=?')

            params.append(current_user()['id'])

        if 'change_reason' in data or data.get('action') in ('rescheduled', 'changed'):

            updates.append('change_reason=?')

            params.append(reason)

        if 'change_scope' in data:

            updates.append('change_scope=?')

            params.append(data.get('change_scope') or '')

        if data.get('start_time') or data.get('end_time'):

            effective_room_id = data.get('room_id') if 'room_id' in data else current.get('room_id')

            chosen_room = choose_room_for_slot(data.get('start_time') or old_start_time, data.get('end_time') or old_end_time, preferred_room_id=effective_room_id, appointment_id=aid)

            updates.append('room_id=?')

            params.append(chosen_room)

        updates.append('updated_at=?')

        params.append(datetime.now().isoformat())

        params.append(aid)

        conn.execute(f'UPDATE appointments SET {", ".join(updates)} WHERE id=?', params)

        updated_action = action or data.get('status') or ('changed' if (data.get('start_time') or data.get('end_time') or data.get('change_scope')) else 'updated')

        if data.get('change_scope') == 'permanent' and data.get('start_time'):

            try:

                old_start_dt = datetime.fromisoformat(old_start_time)

                new_start_dt = datetime.fromisoformat(data['start_time'])

                delta = new_start_dt - old_start_dt

                recurring_rows = conn.execute('''

                    SELECT id, start_time, end_time FROM appointments

                    WHERE client_id=? AND therapist_id=? AND type=? AND location=?

                      AND status IN ('scheduled','completed','no_show')

                      AND (

                        notes LIKE '%Recurring%' OR

                        start_time >= ?

                      )

                      AND id <> ?

                    ORDER BY start_time ASC

                ''', (current['client_id'], current['therapist_id'], current['type'], current['location'], old_start_time, aid)).fetchall()

                for row in recurring_rows:

                    row_start = datetime.fromisoformat(row['start_time'])

                    if row_start > old_start_dt:

                        row_end = datetime.fromisoformat(row['end_time']) if row['end_time'] else None

                        new_row_start = row_start + delta

                        new_row_end = row_end + delta if row_end else None

                        row_room_id = choose_room_for_slot(new_row_start.isoformat(), new_row_end.isoformat() if new_row_end else new_row_start.isoformat(), preferred_room_id=current.get('room_id'), appointment_id=row['id'])

                        conn.execute('''

                            UPDATE appointments

                            SET start_time=?, end_time=?, room_id=?, change_reason=?, change_scope=?, updated_at=?

                            WHERE id=?

                        ''', (

                            new_row_start.isoformat(),

                            new_row_end.isoformat() if new_row_end else None,

                            row_room_id,

                            reason,

                            'permanent',

                            datetime.now().isoformat(),

                            row['id'],

                        ))

                        conn.execute('INSERT INTO appointment_history (appointment_id,action,performed_by,reason) VALUES (?,?,?,?)',

                                     (row['id'], 'changed', current_user()['id'], f'Permanent series shift: {reason}'.strip()))

            except Exception:

                pass

        if action:

            conn.execute('INSERT INTO appointment_history (appointment_id,action,performed_by,reason) VALUES (?,?,?,?)',

                         (aid, action, current_user()['id'], reason))

        conn.commit()

    try:

        with get_db() as conn:

            appt = conn.execute('''SELECT a.*, c.full_name as client_name, c.client_code as client_code, u.full_name as therapist_name,

                                          r.name as room_name, r.code as room_code, r.color as room_color

                                   FROM appointments a

                                   LEFT JOIN clients c ON a.client_id=c.id

                                   LEFT JOIN users u ON a.therapist_id=u.id

                                   LEFT JOIN rooms r ON a.room_id=r.id

                                   WHERE a.id=?''', (aid,)).fetchone()

        if appt:

            appt = dict(appt)

            if 'client_code' not in appt:

                with get_db() as conn:

                    client = conn.execute('SELECT client_code FROM clients WHERE id=?', (appt['client_id'],)).fetchone()

                    appt['client_code'] = client['client_code'] if client else ''

            if data.get('status') == 'cancelled':

                notify_appointment_update(appt, 'cancelled', reason, old_start_time=old_start_time, old_end_time=old_end_time, change_scope=data.get('change_scope') or '')

            elif data.get('status') == 'terminated':

                notify_appointment_update(appt, 'terminated', reason, old_start_time=old_start_time, old_end_time=old_end_time, change_scope=data.get('change_scope') or '')

            elif data.get('status') == 'no_show':

                notify_appointment_update(appt, 'no_show', reason, old_start_time=old_start_time, old_end_time=old_end_time, change_scope=data.get('change_scope') or '')

            elif data.get('start_time') or data.get('end_time') or data.get('change_scope'):

                notify_appointment_update(appt, updated_action, reason, old_start_time=old_start_time, old_end_time=old_end_time, change_scope=data.get('change_scope') or '')

    except Exception:

        pass

    return jsonify({'success': True})



@app.route('/api/appointments/<int:aid>', methods=['DELETE'])

def delete_appointment(aid):

    if not require_role('admin', 'receptionist'):

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        conn.execute('UPDATE appointments SET status=?, cancel_reason=?, cancelled_by=?, updated_at=? WHERE id=?',

                     ('cancelled', 'Cancelled by admin/reception', current_user()['id'], datetime.now().isoformat(), aid))

        conn.execute('INSERT INTO appointment_history (appointment_id,action,performed_by,reason) VALUES (?,?,?,?)',

                     (aid, 'cancelled', current_user()['id'], 'Cancelled by delete endpoint'))

        conn.commit()

    try:

        with get_db() as conn:

            appt = conn.execute('''SELECT a.*, c.full_name as client_name, c.client_code as client_code, u.full_name as therapist_name,

                                          r.name as room_name, r.code as room_code, r.color as room_color

                                   FROM appointments a

                                   LEFT JOIN clients c ON a.client_id=c.id

                                   LEFT JOIN users u ON a.therapist_id=u.id

                                   LEFT JOIN rooms r ON a.room_id=r.id

                                   WHERE a.id=?''', (aid,)).fetchone()

        if appt:

            notify_user(appt['therapist_id'], 'Appointment cancelled', format_appointment_message(dict(appt), 'cancelled', 'Cancelled by admin/reception'))

    except Exception:

        pass

    return jsonify({'success': True})



# ─────────────────────────────────────────────

@app.route('/api/rooms', methods=['GET', 'POST'])

def rooms_api():

    if request.method == 'GET':

        if not current_user():

            return jsonify({'error': 'Unauthorized'}), 401

        with get_db() as conn:

            rows = conn.execute('SELECT id, name, code, color, is_active, sort_order FROM rooms ORDER BY sort_order ASC, name ASC').fetchall()

        return jsonify([dict(r) for r in rows])

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    name = (data.get('name') or '').strip()

    if not name:

        return jsonify({'error': 'Room name is required'}), 400

    code = (data.get('code') or name.replace(' ', '-')).upper()

    color = data.get('color') or '#043069'

    is_active = 1 if data.get('is_active', 1) else 0

    sort_order = int(data.get('sort_order') or 0)

    with get_db() as conn:

        cur = conn.execute('INSERT INTO rooms (name, code, color, is_active, sort_order) VALUES (?,?,?,?,?)',

                           (name, code, color, is_active, sort_order))

        conn.commit()

    return jsonify({'success': True, 'id': cur.lastrowid}), 201



@app.route('/api/rooms/<int:rid>', methods=['PUT', 'DELETE'])

def room_detail_api(rid):

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        if request.method == 'DELETE':

            conn.execute('DELETE FROM rooms WHERE id=?', (rid,))

            conn.commit()

            return jsonify({'success': True})

        data = request.json or {}

        fields = []

        params = []

        for field in ('name', 'code', 'color', 'sort_order'):

            if field in data:

                fields.append(f'{field}=?')

                params.append(data[field])

        if 'is_active' in data:

            fields.append('is_active=?')

            params.append(1 if data['is_active'] else 0)

        if not fields:

            return jsonify({'error': 'No changes supplied'}), 400

        params.append(rid)

        conn.execute(f'UPDATE rooms SET {", ".join(fields)} WHERE id=?', params)

        conn.commit()

    return jsonify({'success': True})



@app.route('/api/rooms/available', methods=['GET'])

def rooms_available_api():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    start = request.args.get('start')

    end = request.args.get('end') or start

    appointment_id = request.args.get('appointment_id')

    rooms = available_rooms_for_slot(start, end, appointment_id=appointment_id)

    return jsonify({'success': True, 'rooms': rooms})



# API: SCREENING & INTAKE (Public)

# ─────────────────────────────────────────────

@app.route('/api/public/intake', methods=['POST'])

def public_intake():

    data = request.json or {}

    personal = data.get('personal', {})

    intake = data.get('intake', {})

    screening = data.get('screening', {})

    

    code = generate_client_code()

    

    with get_db() as conn:

        notes_str = f"Preferred Weekly Slot: {intake.get('preferred_time', 'Not specified')}\n\nPresenting Concerns:\n{intake.get('concerns', '')}\n\nAdditional Notes:\n{intake.get('notes', '')}"

        cur = conn.execute('''INSERT INTO clients 

            (client_code, full_name, date_of_birth, gender, phone, email, address, emergency_contact_name, emergency_contact_phone, status, risk_level, language_pref, therapist_gender_pref, intake_source, notes)

            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',

            (code, personal.get('full_name'), personal.get('date_of_birth'), personal.get('gender'),

             personal.get('phone'), personal.get('email',''), personal.get('address',''),

             personal.get('emergency_contact_name'), personal.get('emergency_contact_phone'),

             'registered', 'low', intake.get('language_pref'), intake.get('therapist_gender_pref'),

             intake.get('intake_source'), notes_str))

        client_id = cur.lastrowid

        conn.execute('UPDATE clients SET intake_json=? WHERE id=?', (json.dumps(data, ensure_ascii=True), client_id))



        conn.execute('''INSERT INTO intake_forms

            (client_id, personal_json, issue_json, form_language, preferred_appointment_date, preferred_appointment_time, assessment_json)

            VALUES (?,?,?,?,?,?,?)''',

            (client_id, json.dumps(personal, ensure_ascii=True), json.dumps(intake, ensure_ascii=True),

             intake.get('language_pref', 'English'), intake.get('preferred_date', ''), intake.get('preferred_time', ''),

             json.dumps(screening, ensure_ascii=True)))

        

        conn.execute('INSERT INTO client_journey (client_id, stage, notes) VALUES (?,?,?)', (client_id, 'registered', 'Self-registered via public intake form'))

        

        # Process screening if exists

        total_score = 0

        severity = 'minimal'

        if screening and screening.get('type') == 'PHQ-9':

            responses = screening.get('responses', {})

            total_score = sum(int(v) for v in responses.values() if str(v).isdigit())

            if total_score >= 20: severity = 'severe'

            elif total_score >= 15: severity = 'moderately_severe'

            elif total_score >= 10: severity = 'moderate'

            elif total_score >= 5: severity = 'mild'

            

            risk_flags = []

            if total_score >= 15:

                risk_flags.append({'type': 'Clinical Depression Risk', 'severity': 'high'})

            if int(responses.get('q9', 0)) > 0:

                risk_flags.append({'type': 'Self-Harm / Suicide Risk', 'severity': 'critical'})

            

            if risk_flags:

                for flag in risk_flags:

                    conn.execute('INSERT INTO risk_alerts (client_id,alert_type,severity,description) VALUES (?,?,?,?)',

                                 (client_id, flag['type'], flag['severity'], f"Auto-detected PHQ-9 score: {total_score}"))

                conn.execute('UPDATE clients SET risk_level=? WHERE id=?', ('high', client_id))

            

            conn.execute('UPDATE clients SET status=? WHERE id=?', ('screening_completed', client_id))

            conn.execute('INSERT INTO client_journey (client_id,stage,notes) VALUES (?,?,?)',

                         (client_id, 'screening_completed', f'PHQ-9 score: {total_score}'))

            

        conn.commit()

    # ── Telegram notification to admins/receptionists ──
    try:
        gender = personal.get('gender', 'Not specified')
        lang = intake.get('language_pref', 'Not specified')
        concerns_text = intake.get('concerns', '').strip() or 'Not provided'
        pref_date = intake.get('appointment_date', '') or intake.get('preferred_date', '') or 'Not specified'
        pref_time = intake.get('appointment_time', '') or intake.get('preferred_time', '') or 'Not specified'
        source = intake.get('intake_source', 'Website Intake Form')

        notif = (
            f"\U0001f195 <b>New Client Self-Registered</b>\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\U0001f194 <b>Client Code:</b> <code>{code}</code>\n"
            f"\U0001f464 <b>Gender:</b> {gender}\n"
            f"\U0001f4ac <b>Language:</b> {lang}\n"
            f"\U0001f4cd <b>Source:</b> {source}\n"
            f"\n"
            f"\U0001f4cb <b>Presenting Concern:</b>\n"
            f"{concerns_text[:300]}{'...' if len(concerns_text) > 300 else ''}\n"
            f"\n"
            f"\U0001f4c5 <b>Preferred Date:</b> {pref_date}\n"
            f"\u23f0 <b>Preferred Time:</b> {pref_time}\n"
            f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"\u27a1\ufe0f Please log in to the reception portal to assign a therapist."
        )

        with get_db() as notif_conn:
            notif_users = notif_conn.execute(
                "SELECT telegram_chat_id FROM users WHERE role IN ('admin','receptionist') AND is_active=1 AND telegram_chat_id IS NOT NULL AND telegram_chat_id != ''"
            ).fetchall()

        for nu in notif_users:
            send_telegram_message(nu['telegram_chat_id'], notif)

    except Exception as tg_err:
        print(f'[TELEGRAM] Failed to send new client notification: {tg_err}')

    return jsonify({'success': True, 'client_code': code}), 201



@app.route('/api/screening', methods=['POST'])

def submit_screening():

    data = request.json or {}

    client_id = data.get('client_id')

    questionnaire_type = data.get('questionnaire_type', 'PHQ-9')

    responses = data.get('responses', {})

    total_score = sum(int(v) for v in responses.values() if str(v).isdigit())



    # Auto-score severity

    severity = 'minimal'

    if questionnaire_type == 'PHQ-9':

        if total_score >= 20: severity = 'severe'

        elif total_score >= 15: severity = 'moderately_severe'

        elif total_score >= 10: severity = 'moderate'

        elif total_score >= 5: severity = 'mild'

    elif questionnaire_type == 'GAD-7':

        if total_score >= 15: severity = 'severe'

        elif total_score >= 10: severity = 'moderate'

        elif total_score >= 5: severity = 'mild'



    # Auto-detect risk flags

    risk_flags = []

    phq9_q9 = responses.get('q9', 0)  # Suicidal ideation item

    if int(phq9_q9) >= 1:

        risk_flags.append({'type': 'suicidal_ideation', 'severity': 'high', 'item': 'PHQ-9 Q9'})

    if severity in ['severe', 'moderately_severe']:

        risk_flags.append({'type': 'severe_distress', 'severity': 'medium', 'questionnaire': questionnaire_type})



    with get_db() as conn:

        conn.execute('''INSERT INTO screening_responses (client_id,questionnaire_type,responses_json,total_score,severity_level,risk_flags_json)

            VALUES (?,?,?,?,?,?)''',

            (client_id, questionnaire_type, json.dumps(responses), total_score, severity, json.dumps(risk_flags)))

        if risk_flags:

            for flag in risk_flags:

                conn.execute('''INSERT INTO risk_alerts (client_id,alert_type,severity,description)

                    VALUES (?,?,?,?)''',

                    (client_id, flag['type'], flag['severity'],

                     f"Auto-detected from {questionnaire_type}: score {total_score} ({severity})"))

            conn.execute('UPDATE clients SET risk_level=? WHERE id=?', ('high', client_id))

        conn.execute('UPDATE clients SET status=? WHERE id=?', ('screening_completed', client_id))

        conn.execute('INSERT INTO client_journey (client_id,stage,notes) VALUES (?,?,?)',

                     (client_id, 'screening_completed', f'{questionnaire_type} completed, score: {total_score}'))

        conn.commit()



    return jsonify({'success': True, 'score': total_score, 'severity': severity, 'risk_flags': risk_flags}), 201



# ─────────────────────────────────────────────

# API: SESSION NOTES

# ─────────────────────────────────────────────

@app.route('/api/notes', methods=['GET'])

def get_notes():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    client_id = request.args.get('client_id')
    note_type = request.args.get('note_type')

    user = current_user()

    with get_db() as conn:

        if client_id:

            if note_type:
                rows = conn.execute('SELECT n.*, u.full_name as therapist_name, c.full_name as client_name FROM session_notes n LEFT JOIN users u ON n.therapist_id=u.id LEFT JOIN clients c ON n.client_id=c.id WHERE n.client_id=? AND n.note_type=? ORDER BY n.created_at DESC', (client_id, note_type)).fetchall()
            else:
                rows = conn.execute('SELECT n.*, u.full_name as therapist_name, c.full_name as client_name FROM session_notes n LEFT JOIN users u ON n.therapist_id=u.id LEFT JOIN clients c ON n.client_id=c.id WHERE n.client_id=? ORDER BY n.created_at DESC', (client_id,)).fetchall()

        elif user['role'] == 'therapist':

            if note_type:
                rows = conn.execute('SELECT n.*, u.full_name as therapist_name, c.full_name as client_name FROM session_notes n LEFT JOIN users u ON n.therapist_id=u.id LEFT JOIN clients c ON n.client_id=c.id WHERE n.therapist_id=? AND n.note_type=? ORDER BY n.created_at DESC', (user['id'], note_type)).fetchall()
            else:
                rows = conn.execute('SELECT n.*, u.full_name as therapist_name, c.full_name as client_name FROM session_notes n LEFT JOIN users u ON n.therapist_id=u.id LEFT JOIN clients c ON n.client_id=c.id WHERE n.therapist_id=? ORDER BY n.created_at DESC', (user['id'],)).fetchall()

        else:

            if note_type:
                rows = conn.execute('SELECT n.*, u.full_name as therapist_name, c.full_name as client_name FROM session_notes n LEFT JOIN users u ON n.therapist_id=u.id LEFT JOIN clients c ON n.client_id=c.id WHERE n.note_type=? ORDER BY n.created_at DESC LIMIT 200', (note_type,)).fetchall()
            else:
                rows = conn.execute('SELECT n.*, u.full_name as therapist_name, c.full_name as client_name FROM session_notes n LEFT JOIN users u ON n.therapist_id=u.id LEFT JOIN clients c ON n.client_id=c.id ORDER BY n.created_at DESC LIMIT 100').fetchall()

    return jsonify([dict(r) for r in rows])


@app.route('/api/notes/<int:nid>', methods=['PUT'])

def update_note(nid):

    if not require_role('admin', 'therapist', 'supervisor'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}
    user = current_user()

    # Build update fields dynamically
    allowed = ['content', 'structured_content', 'short_summary', 'ai_summary',
               'note_type', 'supervisor_response', 'supervisor_action']
    updates = {k: v for k, v in data.items() if k in allowed}

    if not updates:
        return jsonify({'error': 'No valid fields to update'}), 400

    set_clause = ', '.join(f'{k}=?' for k in updates)
    values = list(updates.values()) + [nid]

    with get_db() as conn:
        conn.execute(f'UPDATE session_notes SET {set_clause}, updated_at=? WHERE id=?',
                     values[:-1] + [datetime.now().isoformat(), nid])
        conn.commit()

    return jsonify({'success': True})


@app.route('/api/reception/clients/<int:cid>', methods=['GET'])

def get_reception_client(cid):
    """Alias of /api/clients/<cid> for the reception portal."""
    return get_client(cid)



@app.route('/api/notes', methods=['POST'])

def create_note():

    if not require_role('admin', 'therapist', 'supervisor'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        conn.execute('''INSERT INTO session_notes

            (appointment_id,therapist_id,client_id,note_type,content,structured_content,short_summary,ai_summary,updated_at)

            VALUES (?,?,?,?,?,?,?,?,?)''',

                     (data.get('appointment_id'), current_user()['id'], data.get('client_id'),

                      data.get('note_type','progress'), data.get('content',''),

                      data.get('structured_content',''), data.get('short_summary',''),

                      data.get('ai_summary',''), datetime.now().isoformat()))

        conn.commit()

    return jsonify({'success': True}), 201



# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â

# API: ASSESSMENTS, AI ASSIST, TELEGRAM

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”



@app.route('/api/assessment-templates', methods=['GET', 'POST'])

def assessment_templates():

    if request.method == 'GET':

        if not current_user():

            return jsonify({'error': 'Unauthorized'}), 401

        search = request.args.get('search', '').lower()

        category = request.args.get('category', '')

        tags = request.args.get('tags', '')

        

        query = 'SELECT * FROM assessment_templates WHERE is_active=1'

        params = []

        if search:

            query += ' AND LOWER(name) LIKE ?'

            params.append(f'%{search}%')

        if category:

            query += ' AND category = ?'

            params.append(category)

        if tags:

            query += ' AND tags LIKE ?'

            params.append(f'%{tags}%')

        query += ' ORDER BY created_at DESC'

        

        with get_db() as conn:

            rows = conn.execute(query, params).fetchall()

        return jsonify([dict(r) for r in rows])

        

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    try:

        with get_db() as conn:

            slug = unique_assessment_slug(conn, data.get('slug') or data.get('name', ''))

            cur = conn.execute('''INSERT INTO assessment_templates

                               (name, slug, description, form_language, is_public, is_active, created_by, config_json, category, tags, published, version, author)

                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                               RETURNING id''',

                               (data.get('name', ''), slug, data.get('description', ''), data.get('form_language', 'English'),

                                coerce_int(data.get('is_public', 1), 1), 1, current_user()['id'], json.dumps(data.get('config', {})),

                                data.get('category', ''), data.get('tags', ''), coerce_int(data.get('published', 0), 0), coerce_int(data.get('version', 1), 1), data.get('author') or current_user().get('full_name', '')))

            row = cur.fetchone()
            tid = row['id'] if row else None


            # If questions are provided, insert them too

            if 'questions' in data and isinstance(data['questions'], list):

                if not tid:
                    raise ValueError('Template id was not returned by the database')

                for q in data['questions']:

                    raw_options = q.get('options', [])

                    if isinstance(raw_options, str):

                        raw_options = [opt.strip() for opt in raw_options.split('\n') if opt.strip()]

                    elif not isinstance(raw_options, list):

                        raw_options = [str(raw_options)] if raw_options not in (None, '') else []

                    conn.execute('''INSERT INTO assessment_questions (template_id, question_key, label_en, question_type, required, options_json, helper_text, sort_order)

                                    VALUES (?,?,?,?,?,?,?,?)''',

                                 (tid, q.get('question_key'), q.get('label_en'), normalize_question_type(q.get('question_type', 'text')), coerce_required(q.get('required', 0)),

                                  json.dumps(raw_options), q.get('helper_text', ''), coerce_int(q.get('sort_order', 0), 0)))

                conn.commit()


            conn.commit()

            return jsonify({'success': True, 'id': tid, 'slug': slug}), 201
    except Exception as e:
        return jsonify({'error': f'Failed to save template: {e}'}), 500



@app.route('/api/assessment-templates/<int:tid>', methods=['GET', 'PUT', 'DELETE'])

def assessment_template_detail(tid):

    if request.method == 'GET':

        if not current_user():

            return jsonify({'error': 'Unauthorized'}), 401

        with get_db() as conn:

            tpl = conn.execute('SELECT * FROM assessment_templates WHERE id=?', (tid,)).fetchone()

            questions = conn.execute('SELECT * FROM assessment_questions WHERE template_id=? ORDER BY sort_order, id', (tid,)).fetchall()

        if not tpl:

            return jsonify({'error': 'Not found'}), 404

        return jsonify({'template': dict(tpl), 'questions': [dict(q) for q in questions]})

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    try:
        with get_db() as conn:
            if request.method == 'DELETE':
                conn.execute('UPDATE assessment_templates SET is_active=0, updated_at=? WHERE id=?', (datetime.now().isoformat(), tid))
                conn.commit()
                return jsonify({'success': True})

            data = request.json or {}
            slug = unique_assessment_slug(conn, data.get('slug') or data.get('name', ''), current_id=tid)

            conn.execute(
                '''UPDATE assessment_templates
                   SET name=?, slug=?, description=?, form_language=?, is_public=?, updated_at=?, config_json=?, category=?, tags=?, published=?, version=?, author=?
                   WHERE id=?''',
                (
                    data.get('name', ''),
                    slug,
                    data.get('description', ''),
                    data.get('form_language', 'English'),
                    coerce_int(data.get('is_public', 1), 1),
                    datetime.now().isoformat(),
                    json.dumps(data.get('config', {})),
                    data.get('category', ''),
                    data.get('tags', ''),
                    coerce_int(data.get('published', 0), 0),
                    coerce_int(data.get('version', 1), 1),
                    data.get('author', ''),
                    tid,
                ),
            )

            if 'questions' in data and isinstance(data['questions'], list):
                conn.execute('DELETE FROM assessment_questions WHERE template_id=?', (tid,))

                for q in data['questions']:
                    raw_options = q.get('options', [])
                    if isinstance(raw_options, str):
                        raw_options = [opt.strip() for opt in raw_options.split('\n') if opt.strip()]
                    elif not isinstance(raw_options, list):
                        raw_options = [str(raw_options)] if raw_options not in (None, '') else []

                    conn.execute(
                        '''INSERT INTO assessment_questions (template_id, question_key, label_en, question_type, required, options_json, helper_text, sort_order)
                           VALUES (?,?,?,?,?,?,?,?)''',
                        (
                            tid,
                            q.get('question_key'),
                            q.get('label_en'),
                            normalize_question_type(q.get('question_type', 'text')),
                            coerce_required(q.get('required', 0)),
                            json.dumps(raw_options),
                            q.get('helper_text', ''),
                            coerce_int(q.get('sort_order', 0), 0),
                        ),
                    )

            conn.commit()
            return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': f'Failed to save template: {e}'}), 500



@app.route('/api/assessment-templates/<int:tid>/publish', methods=['POST'])

def publish_assessment_template(tid):

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    published = coerce_int(data.get('published', 1), 1)

    with get_db() as conn:

        conn.execute('UPDATE assessment_templates SET published=? WHERE id=?', (published, tid))

        conn.commit()

    return jsonify({'success': True})



@app.route('/api/assessment-templates/<int:tid>/duplicate', methods=['POST'])

def duplicate_assessment_template(tid):

    import time

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        tpl = conn.execute('SELECT * FROM assessment_templates WHERE id=?', (tid,)).fetchone()

        if not tpl:

            return jsonify({'error': 'Template not found'}), 404

        questions = conn.execute('SELECT * FROM assessment_questions WHERE template_id=? ORDER BY sort_order, id', (tid,)).fetchall()

        

        tpl_dict = dict(tpl)

        new_name = tpl_dict.get('name', 'Template') + ' (Copy)'

        new_slug = unique_assessment_slug(conn, new_name + '-' + str(int(time.time())))

        new_version = int(tpl_dict.get('version') or 1) + 1

        

        cur = conn.execute('''INSERT INTO assessment_templates 

                               (name, slug, description, form_language, is_public, is_active, created_by, config_json, category, tags, published, version, author)

                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                               RETURNING id''',

                           (new_name, new_slug, tpl_dict.get('description', ''), tpl_dict.get('form_language', 'English'),

                            coerce_int(tpl_dict.get('is_public', 1), 1), 1, current_user()['id'], tpl_dict.get('config_json', '{}'),

                            tpl_dict.get('category', ''), tpl_dict.get('tags', ''), 0, new_version, tpl_dict.get('author', '')))

        

        new_row = cur.fetchone()
        new_tid = new_row['id'] if new_row else None
        if not new_tid:
            raise ValueError('Template id was not returned by the database')

        

        for q in questions:

            q_dict = dict(q)

            conn.execute('''INSERT INTO assessment_questions (template_id, question_key, label_en, question_type, required, options_json, helper_text, sort_order)

                            VALUES (?,?,?,?,?,?,?,?)''',

                         (new_tid, q_dict.get('question_key'), q_dict.get('label_en'), normalize_question_type(q_dict.get('question_type', 'text')), coerce_required(q_dict.get('required', 0)),

                          q_dict.get('options_json', '[]'), q_dict.get('helper_text', ''), coerce_int(q_dict.get('sort_order', 0), 0)))

        conn.commit()

        return jsonify({'success': True, 'id': new_tid, 'slug': new_slug})



@app.route('/api/assessment-templates/<int:tid>/questions', methods=['POST'])

def add_assessment_question(tid):

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        cur = conn.execute('''INSERT INTO assessment_questions

            (template_id, question_key, label_en, label_am, question_type, required, options_json, helper_text, sort_order, scoring_json, logic_json)

            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',

            (tid, data.get('question_key', ''), data.get('label_en', ''), data.get('label_am', ''), normalize_question_type(data.get('question_type', 'text')),

             int(data.get('required', 0)), json.dumps(data.get('options', [])), data.get('helper_text', ''),

             int(data.get('sort_order', 0)), json.dumps(data.get('scoring', {})), json.dumps(data.get('logic', {}))))

        conn.commit()

        return jsonify({'success': True, 'id': cur.lastrowid}), 201



@app.route('/api/assessment-questions/<int:qid>', methods=['PUT', 'DELETE'])

def assessment_question_detail(qid):

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        if request.method == 'DELETE':

            conn.execute('DELETE FROM assessment_questions WHERE id=?', (qid,))

            conn.commit()

            return jsonify({'success': True})

        data = request.json or {}

        conn.execute('''UPDATE assessment_questions

                        SET question_key=?, label_en=?, label_am=?, question_type=?, required=?, options_json=?, helper_text=?, sort_order=?, scoring_json=?, logic_json=?

                        WHERE id=?''',

                     (data.get('question_key', ''), data.get('label_en', ''), data.get('label_am', ''), normalize_question_type(data.get('question_type', 'text')),

                      int(data.get('required', 0)), json.dumps(data.get('options', [])), data.get('helper_text', ''),

                      int(data.get('sort_order', 0)), json.dumps(data.get('scoring', {})), json.dumps(data.get('logic', {})), qid))

        conn.commit()

        return jsonify({'success': True})



@app.route('/api/screening-links', methods=['GET', 'POST'])

def screening_links():

    user = current_user()

    if not user:

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        if request.method == 'GET':

            query = '''
                SELECT l.*, t.name as template_name, t.description as template_description,
                       u.full_name as created_by_name, c.full_name as client_name, c.client_code
                FROM screening_links l
                LEFT JOIN assessment_templates t ON l.template_id = t.id
                LEFT JOIN users u ON l.therapist_id = u.id
                LEFT JOIN clients c ON l.client_id = c.id
            '''

            params = []

            if user.get('role') == 'therapist':

                query += ' WHERE l.therapist_id = ?'

                params.append(user['id'])

            query += ' ORDER BY l.created_at DESC LIMIT 100'

            rows = conn.execute(query, params).fetchall()

            return jsonify([dict(r) for r in rows])

        data = request.json or {}

        template_id = data.get('template_id')

        if not template_id:

            return jsonify({'error': 'Template is required'}), 400

        template = conn.execute('SELECT * FROM assessment_templates WHERE id=? AND is_active=1', (template_id,)).fetchone()

        if not template:

            return jsonify({'error': 'Template not found'}), 404

        token = secrets.token_urlsafe(12)

        expires_hours = int(data.get('expires_hours', 24))

        expires_at = (datetime.now() + timedelta(hours=max(1, expires_hours))).isoformat()

        cur = conn.execute('''INSERT INTO screening_links (token, therapist_id, template_id, client_id, expires_at)

                              VALUES (?,?,?,?,?)''',

                           (token, user['id'], template_id, data.get('client_id') or None, expires_at))

        conn.commit()

        link_url = f"{request.host_url.rstrip('/')}/screening/{token}"

        return jsonify({'success': True, 'token': token, 'link': link_url, 'expires_at': expires_at, 'id': cur.lastrowid}), 201



@app.route('/api/screening-links/<token>', methods=['GET'])

def screening_link_detail(token):

    with get_db() as conn:

        link = conn.execute('''SELECT l.*, t.name as template_name, t.description as template_description, t.form_language

                               FROM screening_links l

                               LEFT JOIN assessment_templates t ON l.template_id = t.id

                               WHERE l.token=?''', (token,)).fetchone()

        if not link:

            return jsonify({'success': False, 'error': 'Link not found'}), 404

        if link['expires_at'] and datetime.fromisoformat(str(link['expires_at'])) < datetime.now():

            return jsonify({'success': False, 'error': 'This link has expired'}), 410

        questions = conn.execute('SELECT * FROM assessment_questions WHERE template_id=? ORDER BY sort_order, id', (link['template_id'],)).fetchall()

        template = conn.execute('SELECT * FROM assessment_templates WHERE id=?', (link['template_id'],)).fetchone()

        return jsonify({'success': True, 'link': dict(link), 'template': dict(template) if template else {}, 'questions': [dict(q) for q in questions]})



@app.route('/api/screening-links/<token>/submit', methods=['POST'])

def screening_link_submit(token):

    data = request.json or {}

    responses = data.get('responses', {})

    with get_db() as conn:

        link = conn.execute('''SELECT l.*, t.name as template_name, t.description as template_description

                               FROM screening_links l

                               LEFT JOIN assessment_templates t ON l.template_id = t.id

                               WHERE l.token=?''', (token,)).fetchone()

        if not link:

            return jsonify({'success': False, 'error': 'Link not found'}), 404

        if link['expires_at'] and datetime.fromisoformat(str(link['expires_at'])) < datetime.now():

            return jsonify({'success': False, 'error': 'This link has expired'}), 410

        if link['used_at']:

            return jsonify({'success': False, 'error': 'This assessment has already been submitted'}), 409

        response_json = json.dumps(responses, ensure_ascii=True)

        summary = make_short_summary(response_json, 3, 500) or 'Assessment submitted.'

        conn.execute('''INSERT INTO assessment_submissions

            (template_id, client_id, appointment_id, source, responses_json, structured_content, short_summary, detailed_summary, created_by)

            VALUES (?,?,?,?,?,?,?,?,?)''',

            (link['template_id'], link['client_id'], None, 'screening_link', response_json, '', summary, '', link['therapist_id']))

        conn.execute('UPDATE screening_links SET used_at=? WHERE id=?', (datetime.now().isoformat(), link['id']))

        conn.commit()

        return jsonify({'success': True})



@app.route('/screening/<token>')

def screening_redirect(token):

    return redirect(f'/portals/client_screening.html?token={token}')



@app.route('/api/screening-results', methods=['GET'])

def screening_results():

    user = current_user()

    if not user:

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        query = '''
            SELECT s.*, t.name as template_name, t.category as template_category,
                   c.full_name as client_name, c.client_code, c.phone as client_phone,
                   u.full_name as created_by_name
            FROM assessment_submissions s
            LEFT JOIN assessment_templates t ON s.template_id = t.id
            LEFT JOIN clients c ON s.client_id = c.id
            LEFT JOIN users u ON s.created_by = u.id
        '''

        params = []

        if user.get('role') == 'therapist':

            query += ' WHERE s.created_by = ? OR c.assigned_therapist_id = ?'

            params.extend([user['id'], user['id']])

        query += ' ORDER BY s.created_at DESC LIMIT 100'

        rows = conn.execute(query, params).fetchall()

        return jsonify([dict(r) for r in rows])



@app.route('/api/referrals', methods=['GET', 'POST'])

def referrals_api():

    user = current_user()

    if not user:

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        if request.method == 'GET':

            query = '''
                SELECT r.*, c.full_name as client_name, c.client_code,
                       u1.full_name as from_therapist_name,
                       u2.full_name as to_therapist_name
                FROM referrals r
                LEFT JOIN clients c ON r.client_id = c.id
                LEFT JOIN users u1 ON r.from_therapist_id = u1.id
                LEFT JOIN users u2 ON r.to_therapist_id = u2.id
            '''

            params = []

            if user.get('role') == 'therapist':

                query += ' WHERE r.from_therapist_id = ? OR r.to_therapist_id = ?'

                params.extend([user['id'], user['id']])

            query += ' ORDER BY r.created_at DESC LIMIT 100'

            rows = conn.execute(query, params).fetchall()

            return jsonify([dict(r) for r in rows])

        data = request.json or {}

        client_id = data.get('client_id')

        to_therapist_id = data.get('to_therapist_id')

        reason = (data.get('reason') or '').strip()

        if not client_id or not to_therapist_id or not reason:

            return jsonify({'error': 'Client, therapist, and reason are required'}), 400

        cur = conn.execute('''INSERT INTO referrals (client_id, from_therapist_id, to_therapist_id, reason, status)

                              VALUES (?,?,?,?,?)''',

                           (client_id, user['id'], to_therapist_id, reason, 'pending'))

        conn.execute('UPDATE clients SET status=? WHERE id=?', ('awaiting_assignment', client_id))

        conn.commit()

        return jsonify({'success': True, 'id': cur.lastrowid}), 201



@app.route('/api/assessment-import', methods=['POST'])

def assessment_import():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    source_text = ''

    source_type = 'text'

    if request.files:

        upload = request.files.get('file')

        if upload and upload.filename:

            filename = upload.filename.lower()

            source_type = filename.rsplit('.', 1)[-1] if '.' in filename else 'text'

            raw = upload.read() or b''

            if source_type == 'docx':

                source_text = extract_docx_text_from_bytes(raw)

            else:

                source_text = raw.decode('utf-8', errors='ignore')

    if not source_text:

        data = request.form.to_dict() if request.form else (request.json or {})

        source_text = data.get('text') or data.get('source_text') or ''

        source_type = data.get('source_type') or source_type

    parsed = parse_assessment_structure(source_text)

    return jsonify({

        'success': True,

        'source_type': source_type,

        'source_text': source_text,

        'parsed': parsed,

    })



@app.route('/api/assessment-submissions', methods=['GET', 'POST'])

def assessment_submissions():

    if request.method == 'GET':

        if not current_user():

            return jsonify({'error': 'Unauthorized'}), 401

        client_id = request.args.get('client_id')

        template_id = request.args.get('template_id')

        with get_db() as conn:

            query = '''SELECT s.*, t.name as template_name, c.full_name as client_name

                       FROM assessment_submissions s

                       LEFT JOIN assessment_templates t ON s.template_id=t.id

                       LEFT JOIN clients c ON s.client_id=c.id'''

            params = []

            clauses = []

            if client_id:

                clauses.append('s.client_id=?')

                params.append(client_id)

            if template_id:

                clauses.append('s.template_id=?')

                params.append(template_id)

            if clauses:

                query += ' WHERE ' + ' AND '.join(clauses)

            query += ' ORDER BY s.created_at DESC'

            rows = conn.execute(query, params).fetchall()

        return jsonify([dict(r) for r in rows])

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        cur = conn.execute('''INSERT INTO assessment_submissions

            (template_id, client_id, appointment_id, source, responses_json, structured_content, short_summary, detailed_summary, created_by)

            VALUES (?,?,?,?,?,?,?,?,?)''',

            (data.get('template_id'), data.get('client_id'), data.get('appointment_id'), data.get('source', 'public'),

             json.dumps(data.get('responses', {})), data.get('structured_content', ''), data.get('short_summary', ''),

             data.get('detailed_summary', ''), current_user()['id']))

        conn.commit()

        return jsonify({'success': True, 'id': cur.lastrowid}), 201



@app.route('/api/ai/structure-note', methods=['POST'])

def ai_structure_note():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    prompt = build_note_prompt_v2(

        data.get('raw_text', ''),

        data.get('structure_style') or data.get('note_type', 'progress'),

        data.get('client_name', ''),

        data.get('session_date', ''),

        data.get('therapist_name', '')

    )

    ok, result = call_openai(prompt, model=CLINICAL_AI_MODEL)

    if ok and result.strip():

        structured = trim_counseling_template(result)

        summary = make_short_summary(structured or data.get('raw_text', ''), 3, 500) or 'Summary not specified.'

        return jsonify({'success': True, 'structured_content': structured, 'short_summary': summary, 'raw_response': result})

    fallback_text = result if result.strip() else 'AI helper unavailable'

    return jsonify({'success': False, 'fallback': True, 'error': fallback_text, 'raw_response': result}), 200



@app.route('/api/ai/client-summary', methods=['POST'])

def ai_client_summary():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    client_id = data.get('client_id')

    with get_db() as conn:

        client = conn.execute('SELECT full_name FROM clients WHERE id=?', (client_id,)).fetchone()

        notes = conn.execute('''SELECT created_at, note_type, content, structured_content, short_summary, ai_summary

                                FROM session_notes WHERE client_id=? ORDER BY created_at ASC''', (client_id,)).fetchall()

        plans = conn.execute('''SELECT created_at, goals, interventions, review_date, status

                                FROM treatment_plans WHERE client_id=? ORDER BY created_at ASC''', (client_id,)).fetchall()

    notes_blob = {

        'notes': [dict(n) for n in notes],

        'treatment_plans': [dict(p) for p in plans],

    }

    prompt = build_client_summary_prompt(client['full_name'] if client else 'Client', json.dumps(notes_blob, ensure_ascii=True))

    ok, result = call_openai(prompt)

    if ok and result.strip():

        summary, themes = extract_ai_sections(result, 'SUMMARY:', 'KEY THEMES:')

        follow_up = ''

        upper = result.upper()

        f_idx = upper.find('FOLLOW-UP PRIORITIES:')

        if f_idx != -1:

            follow_up = result[f_idx + len('FOLLOW-UP PRIORITIES:'):].strip()

        if not summary:

            summary = make_short_summary(result, 4, 700)

        if not themes:

            themes = '- Not specified'

        if not follow_up:

            follow_up = '- Not specified'

        return jsonify({'success': True, 'summary': summary, 'key_themes': themes, 'follow_up_priorities': follow_up, 'raw_response': result})

    return jsonify({'success': False, 'fallback': True, 'error': result or 'AI helper unavailable', 'raw_response': result}), 200



@app.route('/api/ai/client-detailed-summary', methods=['POST'])

def ai_client_detailed_summary():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    client_id = data.get('client_id')

    with get_db() as conn:

        client = conn.execute('SELECT full_name, client_code FROM clients WHERE id=?', (client_id,)).fetchone()

        notes = conn.execute('''SELECT n.id, n.created_at, n.note_type, n.content, n.structured_content, n.short_summary, n.ai_summary, u.full_name as therapist_name

                                FROM session_notes n

                                LEFT JOIN users u ON n.therapist_id=u.id

                                WHERE n.client_id=?

                                ORDER BY n.created_at ASC''', (client_id,)).fetchall()

        plans = conn.execute('''SELECT created_at, goals, interventions, review_date, status

                                FROM treatment_plans WHERE client_id=? ORDER BY created_at ASC''', (client_id,)).fetchall()

    ok, summary, raw_response = generate_client_detailed_summary(

        client['full_name'] if client else 'Client',

        client['client_code'] if client else '',

        current_user().get('full_name', ''),

        [dict(n) for n in notes],

        [dict(p) for p in plans],

    )

    if ok and summary.strip():

        return jsonify({'success': True, 'summary': summary, 'raw_response': raw_response})

    return jsonify({'success': False, 'fallback': True, 'error': raw_response or 'AI helper unavailable', 'raw_response': raw_response}), 200



@app.route('/api/ai/note-detailed-summary', methods=['POST'])

def ai_note_detailed_summary():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    note_id = data.get('note_id')

    if not note_id:

        return jsonify({'error': 'Missing note_id'}), 400

    with get_db() as conn:

        note = conn.execute('''SELECT n.*, c.full_name as client_name, c.client_code, u.full_name as therapist_name

                               FROM session_notes n

                               LEFT JOIN clients c ON n.client_id=c.id

                               LEFT JOIN users u ON n.therapist_id=u.id

                               WHERE n.id=?''', (note_id,)).fetchone()

        if not note:

            return jsonify({'error': 'Note not found'}), 404

        all_notes = conn.execute('''SELECT id, created_at FROM session_notes WHERE client_id=? ORDER BY created_at ASC''', (note['client_id'],)).fetchall()

    session_number = 1

    for idx, row in enumerate(all_notes, start=1):

        if row['id'] == note['id']:

            session_number = idx

            break

    note_data = {

        'id': note['id'],

        'created_at': note['created_at'],

        'note_type': note['note_type'],

        'content': note['content'],

        'structured_content': note['structured_content'],

        'short_summary': note['short_summary'],

        'ai_summary': note['ai_summary'],

    }

    prompt = build_session_detailed_summary_prompt(

        note['client_name'] or 'Client',

        note['client_code'] or '',

        note['therapist_name'] or current_user().get('full_name', ''),

        session_number,

        json.dumps(note_data, ensure_ascii=True)

    )

    ok, result = call_openai(prompt, model=CLINICAL_AI_MODEL, num_predict=1100)

    if ok and result.strip():

        return jsonify({'success': True, 'summary': normalize_structured_text(result), 'session_number': session_number, 'raw_response': result})

    return jsonify({'success': False, 'fallback': True, 'error': result or 'AI helper unavailable', 'raw_response': result}), 200



@app.route('/api/telegram/link-codes', methods=['GET', 'POST'])

def telegram_link_codes():

    if request.method == 'GET':

        if not require_role('admin'):

            return jsonify({'error': 'Unauthorized'}), 401

        with get_db() as conn:

            rows = conn.execute('''SELECT l.*, u.full_name as user_name, u.username

                                   FROM telegram_link_codes l LEFT JOIN users u ON l.user_id=u.id

                                   ORDER BY l.created_at DESC''').fetchall()

        return jsonify([dict(r) for r in rows])

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    user_id = data.get('user_id')

    expires_hours = int(data.get('expires_hours', 48))

    code = generate_login_code()

    expires_at = (datetime.now() + timedelta(hours=expires_hours)).isoformat()

    with get_db() as conn:

        user = conn.execute('SELECT id, full_name, role FROM users WHERE id=?', (user_id,)).fetchone()

        if not user:

            return jsonify({'error': 'User not found'}), 404

        conn.execute('''INSERT INTO telegram_link_codes (user_id, code, role, created_by, expires_at)

                        VALUES (?,?,?,?,?)''',

                     (user_id, code, user['role'], current_user()['id'], expires_at))

        conn.commit()

    deep_link = f'https://t.me/{TELEGRAM_BOT_USERNAME}?start={code}'

    notify_user(user_id, 'Telegram link code created', f'Your Telegram link code is: {code}\nOpen this link in Telegram: {deep_link}\nExpires at: {expires_at}')

    return jsonify({'success': True, 'code': code, 'expires_at': expires_at, 'deep_link': deep_link, 'bot_username': TELEGRAM_BOT_USERNAME})



@app.route('/api/telegram/webhook', methods=['POST'])
def telegram_webhook():
    update = request.json or {}
    handle_telegram_update(update)
    return jsonify({'ok': True})



# ─────────────────────────────────────────────

# API: RISK ALERTS

# ─────────────────────────────────────────────

@app.route('/api/telegram/status', methods=['GET'])
def telegram_status():
    if not require_role('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    token = get_bot_token()

    # Get current webhook info from Telegram
    webhook_info = {}
    if token:
        ok, result = telegram_api_get('getWebhookInfo')
        if ok and result.get('ok'):
            webhook_info = result.get('result', {})

    return jsonify({
        'success': True,
        'configured': bool(token),
        'username': TELEGRAM_BOT_USERNAME,
        'polling_active': TELEGRAM_POLLING_ACTIVE,
        'bot_url': f'https://t.me/{TELEGRAM_BOT_USERNAME}' if TELEGRAM_BOT_USERNAME else '',
        'webhook_url': webhook_info.get('url', ''),
        'webhook_pending': webhook_info.get('pending_update_count', 0),
        'last_error': webhook_info.get('last_error_message', ''),
    })


@app.route('/api/telegram/register-webhook', methods=['POST'])
def register_telegram_webhook():
    if not require_role('admin'):
        return jsonify({'error': 'Unauthorized'}), 401

    token = get_bot_token()
    if not token:
        return jsonify({'error': 'Telegram bot token not configured'}), 400

    data = request.json or {}
    base = data.get('base_url', '').rstrip('/')
    if not base:
        base = request.host_url.rstrip('/')

    webhook_url = f'{base}/api/telegram/webhook'
    ok, result = telegram_api('setWebhook', {
        'url': webhook_url,
        'allowed_updates': ['message', 'callback_query'],
        'drop_pending_updates': False
    })

    return jsonify({'success': ok, 'webhook_url': webhook_url, 'telegram_response': result})




@app.route('/api/alerts', methods=['GET'])

def get_alerts():

    if not require_role('admin', 'receptionist', 'supervisor'):

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        rows = conn.execute('''SELECT r.*, c.full_name as client_name, c.client_code

            FROM risk_alerts r LEFT JOIN clients c ON r.client_id=c.id

            WHERE r.is_active=1 ORDER BY r.triggered_at DESC''').fetchall()

    return jsonify([dict(r) for r in rows])



@app.route('/api/alerts/<int:aid>/resolve', methods=['POST'])

def resolve_alert(aid):

    if not require_role('admin', 'receptionist', 'supervisor'):

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        conn.execute('UPDATE risk_alerts SET is_active=0, resolved_by=?, resolved_at=? WHERE id=?',

                     (current_user()['id'], datetime.now().isoformat(), aid))

        conn.commit()

    return jsonify({'success': True})



# ─────────────────────────────────────────────

# API: SERVICES

# ─────────────────────────────────────────────

@app.route('/api/services', methods=['GET'])

def get_services():

    with get_db() as conn:

        rows = conn.execute('SELECT * FROM services WHERE is_active=1 ORDER BY name').fetchall()

    return jsonify([dict(r) for r in rows])



@app.route('/api/services', methods=['POST'])

def create_service():

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        conn.execute('INSERT INTO services (name,description,duration_minutes,price) VALUES (?,?,?,?)',

                     (data.get('name',''), data.get('description',''), int(data.get('duration_minutes',60)), float(data.get('price',0))))

        conn.commit()

    return jsonify({'success': True})



@app.route('/api/services/<int:sid>', methods=['PUT'])

def update_service(sid):

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        conn.execute('UPDATE services SET name=?,description=?,duration_minutes=?,price=?,is_active=? WHERE id=?',

                     (data.get('name',''), data.get('description',''), int(data.get('duration_minutes',60)),

                      float(data.get('price',0)), int(data.get('is_active',1)), sid))

        conn.commit()

    return jsonify({'success': True})



@app.route('/api/services/<int:sid>', methods=['DELETE'])

def delete_service(sid):

    if not require_role('admin'):

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        conn.execute('UPDATE services SET is_active=0 WHERE id=?', (sid,))

        conn.commit()

    return jsonify({'success': True})



# ─────────────────────────────────────────────

# API: FINANCE

# ─────────────────────────────────────────────

@app.route('/api/invoices', methods=['GET'])

def get_invoices():

    if not require_role('admin', 'receptionist'):

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        rows = conn.execute('''SELECT i.*, c.full_name as client_name, c.client_code, s.name as service_name

            FROM invoices i LEFT JOIN clients c ON i.client_id=c.id

            LEFT JOIN services s ON i.service_id=s.id ORDER BY i.issue_date DESC''').fetchall()

    return jsonify([dict(r) for r in rows])



@app.route('/api/invoices', methods=['POST'])

def create_invoice():

    if not require_role('admin', 'receptionist'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    due = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    with get_db() as conn:

        conn.execute('INSERT INTO invoices (client_id,service_id,amount,due_date,notes) VALUES (?,?,?,?,?)',

                     (data.get('client_id'), data.get('service_id'), float(data.get('amount',0)), due, data.get('notes','')))

        conn.commit()

    return jsonify({'success': True})



@app.route('/api/payments', methods=['POST'])

def record_payment():

    if not require_role('admin', 'receptionist'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        conn.execute('INSERT INTO payments (invoice_id,client_id,amount_paid,payment_method,received_by,notes) VALUES (?,?,?,?,?,?)',

                     (data.get('invoice_id'), data.get('client_id'), float(data.get('amount_paid',0)),

                      data.get('payment_method','cash'), current_user()['id'], data.get('notes','')))

        conn.execute('UPDATE invoices SET status=? WHERE id=?', (data.get('invoice_status','paid'), data.get('invoice_id')))

        conn.commit()

    return jsonify({'success': True})



# ─────────────────────────────────────────────

# API: ANALYTICS

# ─────────────────────────────────────────────

@app.route('/api/analytics/dashboard', methods=['GET'])

def get_dashboard_analytics():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    with get_db() as conn:

        total_clients = conn.execute('SELECT COUNT(*) FROM clients').fetchone()[0]

        active_clients = conn.execute("SELECT COUNT(*) FROM clients WHERE status NOT IN ('completed','terminated','inactive')").fetchone()[0]

        new_this_month = conn.execute("SELECT COUNT(*) FROM clients WHERE CAST(registration_date AS DATE) >= date_trunc('month', CURRENT_DATE)").fetchone()[0]

        today_appts = conn.execute("SELECT COUNT(*) FROM appointments WHERE CAST(start_time AS DATE) = CURRENT_DATE AND status='scheduled'").fetchone()[0]

        pending_assignment = conn.execute("SELECT COUNT(*) FROM clients WHERE status IN ('registered','screening_completed') AND assigned_therapist_id IS NULL").fetchone()[0]

        active_alerts = conn.execute("SELECT COUNT(*) FROM risk_alerts WHERE is_active=1").fetchone()[0]

        total_revenue = conn.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payments").fetchone()[0]

        revenue_this_month = conn.execute("SELECT COALESCE(SUM(amount_paid),0) FROM payments WHERE CAST(payment_date AS DATE) >= date_trunc('month', CURRENT_DATE)").fetchone()[0]

        pending_invoices = conn.execute("SELECT COUNT(*) FROM invoices WHERE status='pending'").fetchone()[0]

        therapist_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='therapist' AND is_active=1").fetchone()[0]



        # Monthly new clients (last 6 months)

        monthly_clients = conn.execute("""

            SELECT strftime('%Y-%m', registration_date) as month, COUNT(*) as count

            FROM clients WHERE registration_date >= date('now','-6 months')

            GROUP BY month ORDER BY month

        """).fetchall()



        # Appointment status breakdown

        appt_status = conn.execute("SELECT status, COUNT(*) as count FROM appointments GROUP BY status").fetchall()



        # Therapist caseloads

        caseloads = conn.execute("""

            SELECT u.full_name, u.max_caseload, COUNT(c.id) as current_caseload

            FROM users u LEFT JOIN clients c ON c.assigned_therapist_id=u.id AND c.status NOT IN ('completed','terminated')

            WHERE u.role='therapist' AND u.is_active=1 GROUP BY u.id

        """).fetchall()



        # Recent audit logs

        recent_activity = conn.execute("""

            SELECT a.*, u.full_name FROM audit_logs a LEFT JOIN users u ON a.user_id=u.id

            ORDER BY a.timestamp DESC LIMIT 10

        """).fetchall()



    return jsonify({

        'stats': {

            'total_clients': total_clients,

            'active_clients': active_clients,

            'new_this_month': new_this_month,

            'today_appointments': today_appts,

            'pending_assignment': pending_assignment,

            'active_alerts': active_alerts,

            'total_revenue': total_revenue,

            'revenue_this_month': revenue_this_month,

            'pending_invoices': pending_invoices,

            'therapist_count': therapist_count,

        },

        'monthly_clients': [dict(r) for r in monthly_clients],

        'appt_status': [dict(r) for r in appt_status],

        'caseloads': [dict(r) for r in caseloads],

        'recent_activity': [dict(r) for r in recent_activity],

    })



# ─────────────────────────────────────────────

# API: SMART ASSIGNMENT

# ─────────────────────────────────────────────

@app.route('/api/assign/recommend', methods=['POST'])

def recommend_therapist():

    if not require_role('admin', 'receptionist'):

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    client_id = data.get('client_id')

    with get_db() as conn:

        client = conn.execute('SELECT * FROM clients WHERE id=?', (client_id,)).fetchone()

        therapists = conn.execute("""

            SELECT u.*, COUNT(c.id) as caseload

            FROM users u LEFT JOIN clients c ON c.assigned_therapist_id=u.id AND c.status NOT IN ('completed','terminated')

            WHERE u.role='therapist' AND u.is_active=1 GROUP BY u.id

        """).fetchall()

    if not client or not therapists:

        return jsonify({'recommendations': []})



    client = dict(client)

    scored = []

    for t in therapists:

        t = dict(t)

        score = 100

        # Caseload penalty

        utilization = (t['caseload'] / max(t['max_caseload'], 1)) * 100

        score -= utilization * 0.5

        # Gender preference

        if client['therapist_gender_pref'] != 'No Preference':

            if t.get('gender') == client['therapist_gender_pref']:

                score += 20

            else:

                score -= 15

        # Language match

        client_lang = client.get('language_pref', 'English')

        t_langs = t.get('languages', 'English').split(',')

        if client_lang in t_langs:

            score += 15

        scored.append({**t, 'match_score': round(score, 1),

                        'utilization': round(utilization, 1)})



    scored.sort(key=lambda x: x['match_score'], reverse=True)

    return jsonify({'recommendations': scored[:5]})



# ─────────────────────────────────────────────

# API: MESSAGES

# ─────────────────────────────────────────────

@app.route('/api/messages', methods=['GET'])

def get_messages():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    user = current_user()

    with get_db() as conn:

        rows = conn.execute('''SELECT m.*, u.full_name as sender_name

            FROM messages m LEFT JOIN users u ON m.sender_id=u.id

            WHERE m.recipient_id=? ORDER BY m.sent_at DESC LIMIT 50''', (user['id'],)).fetchall()

    return jsonify([dict(r) for r in rows])



@app.route('/api/messages', methods=['POST'])

def send_message():

    if not current_user():

        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json or {}

    with get_db() as conn:

        conn.execute('INSERT INTO messages (sender_id,recipient_id,client_id,subject,body,channel) VALUES (?,?,?,?,?,?)',

                     (current_user()['id'], data.get('recipient_id'), data.get('client_id'),

                      data.get('subject',''), data.get('body',''), data.get('channel','internal')))

        conn.commit()

    return jsonify({'success': True})



# ─────────────────────────────────────────────

# LEGACY API ROUTES (keep existing admin working)

# ─────────────────────────────────────────────

@app.route('/api/slides', methods=['GET'])

def get_slides():

    with get_db() as conn:

        rows = conn.execute('SELECT * FROM slides ORDER BY id DESC').fetchall()

    return jsonify([dict(r) for r in rows])



@app.route('/api/slides', methods=['POST'])

def add_slide():

    if not session.get('logged_in'):

        return jsonify({"error": "Unauthorized"}), 401

    headline = request.form.get('headline', '')

    summary = request.form.get('summary', '')

    alignment = request.form.get('alignment', 'center')

    button_name = request.form.get('button_name', '')

    button_link = request.form.get('button_link', '')

    if 'image' not in request.files:

        return jsonify({"error": "No image uploaded"}), 400

    file = request.files['image']

    if file.filename == '':

        return jsonify({"error": "No selected file"}), 400

    public_url = _storage.upload_file(file, file.filename)

    with get_db() as conn:

        conn.execute('INSERT INTO slides (image_path,headline,summary,alignment,button_name,button_link) VALUES (?,?,?,?,?,?)',

                     (public_url, headline, summary, alignment, button_name, button_link))

        conn.commit()

    return jsonify({"success": True}), 201



@app.route('/api/slides/<int:slide_id>', methods=['DELETE'])

def delete_slide(slide_id):

    if not session.get('logged_in'):

        return jsonify({"error": "Unauthorized"}), 401

    with get_db() as conn:

        conn.execute('DELETE FROM slides WHERE id=?', (slide_id,))

        conn.commit()

    return jsonify({"success": True})



@app.route('/api/org', methods=['GET'])

def get_org():

    with get_db() as conn:

        rows = conn.execute('SELECT * FROM org_members ORDER BY sort_order, id').fetchall()

    return jsonify([dict(r) for r in rows])



@app.route('/api/org', methods=['POST'])

def add_org_member():

    if not session.get('logged_in'):

        return jsonify({"error": "Unauthorized"}), 401

    member_id = request.form.get('id')

    name = request.form.get('name', '')

    role = request.form.get('role', '')

    parent_id = request.form.get('parent_id') or None

    node_type = request.form.get('node_type', 'normal')

    sort_order = request.form.get('sort_order', 0)

    summary = request.form.get('summary', '')

    photo_path = None

    if 'photo' in request.files and request.files['photo'].filename:

        file = request.files['photo']

        photo_path = _storage.upload_file(file, file.filename)

    with get_db() as conn:

        if member_id:

            if photo_path:

                conn.execute('UPDATE org_members SET name=?,role=?,photo_path=?,parent_id=?,node_type=?,sort_order=?,summary=? WHERE id=?',

                             (name, role, photo_path, parent_id, node_type, sort_order, summary, member_id))

            else:

                conn.execute('UPDATE org_members SET name=?,role=?,parent_id=?,node_type=?,sort_order=?,summary=? WHERE id=?',

                             (name, role, parent_id, node_type, sort_order, summary, member_id))

        else:

            conn.execute('INSERT INTO org_members (name,role,photo_path,parent_id,node_type,sort_order,summary) VALUES (?,?,?,?,?,?,?)',

                         (name, role, photo_path, parent_id, node_type, sort_order, summary))

        conn.commit()

    return jsonify({"success": True}), 201



@app.route('/api/org/<int:member_id>', methods=['DELETE'])

def delete_org_member(member_id):

    if not session.get('logged_in'):

        return jsonify({"error": "Unauthorized"}), 401

    with get_db() as conn:

        conn.execute('DELETE FROM org_members WHERE id=?', (member_id,))

        conn.commit()

    return jsonify({"success": True})



@app.route('/api/me', methods=['GET'])

def get_me():

    user = current_user()

    if not user:

        return jsonify({'error': 'Not logged in'}), 401

    safe = {k: v for k, v in user.items() if k != 'password_hash'}

    return jsonify(safe)



# ─────────────────────────────────────────────

# STATIC FILES

# ─────────────────────────────────────────────

@app.route('/uploads/<path:filename>')

def uploaded_file(filename):

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)



@app.route('/', defaults={'path': 'index.html'})

@app.route('/<path:path>')

def serve_static(path):

    # Protect portal files

    if path.startswith('portals/') and not session.get('logged_in'):

        return redirect('/login')

    if os.path.exists(path):

        return send_from_directory('.', path)

    return "Not Found", 404




# ─────────────────────────────────────────────
# CRON JOB ENDPOINTS (Triggered by Vercel Cron)
# ─────────────────────────────────────────────

def verify_cron_request():
    auth_header = request.headers.get('Authorization')
    cron_secret = os.getenv('CRON_SECRET')
    if cron_secret and auth_header != f"Bearer {cron_secret}":
        return False
    return True

@app.route('/api/cron/daily-schedule', methods=['GET'])
def cron_daily_schedule():
    if not verify_cron_request():
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Call the existing function that handles daily schedule logic
        notify_daily_schedule()
        return jsonify({'success': True, 'message': 'Daily schedule notifications sent'}), 200
    except Exception as e:
        print(f"[CRON] Daily schedule error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/cron/upcoming-sessions', methods=['GET'])
def cron_upcoming_sessions():
    if not verify_cron_request():
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        now = now_in_eat()
        start_window = (now + timedelta(minutes=25)).isoformat()
        end_window = (now + timedelta(minutes=35)).isoformat()

        with get_db() as conn:
            appts = conn.execute(
                """SELECT a.*, c.full_name as client_name, c.client_code as client_code, u.full_name as therapist_name,
                          r.name as room_name, r.code as room_code, r.color as room_color
                   FROM appointments a
                   LEFT JOIN clients c ON a.client_id=c.id
                   LEFT JOIN users u ON a.therapist_id=u.id
                   LEFT JOIN rooms r ON a.room_id=r.id
                   WHERE a.status IN ('scheduled', 'confirmed')
                   AND a.start_time >= ? AND a.start_time < ?
                   ORDER BY a.start_time ASC""",
                (start_window, end_window)
            ).fetchall()

            count = 0
            for row in appts:
                appt = dict(row)
                therapist_id = appt.get('therapist_id')
                if not therapist_id:
                    continue
                subject = 'Session starting in 30 minutes'
                body = [
                    '⏰ <b>Your next session starts in about 30 minutes</b>',
                    '',
                    f'• <b>Client:</b> {_telegram_safe(appt.get("client_name") or "Client")} <code>{_telegram_safe(appt.get("client_code") or "No code")}</code>',
                    f'• <b>When:</b> {_telegram_safe(format_datetime_readable(appt.get("start_time")))}',
                    f'• <b>Ends:</b> {_telegram_safe(format_datetime_readable(appt.get("end_time")))}',
                    f'• <b>Location:</b> {_telegram_safe(appt.get("location") or "Not specified")}',
                    f'• <b>Room:</b> {_telegram_safe(appt.get("room_name") or appt.get("room_code") or "Unassigned")}',
                    '',
                    'Please review your portal for any last-minute updates.'
                ]
                notify_user(therapist_id, subject, '\n'.join(body))
                count += 1

        return jsonify({'success': True, 'message': f'Sent {count} upcoming session reminders'}), 200
    except Exception as e:
        print(f"[CRON] Upcoming sessions error: {e}")
        return jsonify({'error': str(e)}), 500


# Debug endpoint: echo request details to verify that Vercel is invoking the Python app
@app.route('/api/echo', methods=['GET', 'POST', 'OPTIONS'])
def api_echo():
    # Allow simple OPTIONS preflight responses
    if request.method == 'OPTIONS':
        return ('', 204)
    data = None
    try:
        data = request.get_json(silent=True)
    except Exception:
        data = None
    if not data:
        # fallback to form data
        try:
            data = request.form.to_dict()
        except Exception:
            data = {}
    return jsonify({
        'ok': True,
        'method': request.method,
        'args': request.args.to_dict(),
        'form': data,
        'headers': dict(request.headers)
    })


if __name__ == '__main__':

    app.run(host='0.0.0.0', port=8000, debug=False)











