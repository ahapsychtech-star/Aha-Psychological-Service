"""
storage.py  Supabase Storage adapter for Aha Psychological Service
Uploads files to Supabase Storage bucket and returns a public URL.
Falls back to local disk if Supabase credentials are missing (dev mode).
"""
import os
import uuid

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')
BUCKET = 'uploads'

_client = None

def _get_client():
    global _client
    if _client is not None:
        return _client
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    try:
        from supabase import create_client
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _client
    except Exception as e:
        print(f'[STORAGE] Supabase client init failed: {e}')
        return None


def upload_file(file_obj, filename):
    """
    Upload a Werkzeug FileStorage object to Supabase Storage.
    Returns the public URL of the uploaded file.
    Falls back to local upload if Supabase is not configured.
    """
    from werkzeug.utils import secure_filename

    safe_name = secure_filename(filename)
    # Add a UUID prefix to avoid collisions
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"

    client = _get_client()
    if client:
        try:
            file_bytes = file_obj.read()
            content_type = file_obj.content_type or 'application/octet-stream'
            client.storage.from_(BUCKET).upload(
                path=unique_name,
                file=file_bytes,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            public_url = client.storage.from_(BUCKET).get_public_url(unique_name)
            return public_url
        except Exception as e:
            print(f'[STORAGE] Supabase upload failed: {e}. Falling back to local disk.')

    # Fallback: save locally
    local_dir = 'uploads'
    os.makedirs(local_dir, exist_ok=True)
    local_path = os.path.join(local_dir, unique_name)
    file_obj.seek(0)
    file_obj.save(local_path)
    return f'/uploads/{unique_name}'
