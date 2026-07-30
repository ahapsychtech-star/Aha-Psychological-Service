import ast

CRON_ENDPOINTS = r'''
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
        # We need to find appointments starting in exactly 30 minutes
        # Since cron runs every 10 mins, we check if start_time is between 25 and 35 mins from now
        now = datetime.now()
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
                   AND a.start_time >= ? AND a.start_time <= ?""",
                (start_window, end_window)
            ).fetchall()
            
            count = 0
            for row in appts:
                appt = dict(row)
                therapist_id = appt.get('therapist_id')
                if therapist_id:
                    # Send telegram notification
                    time_str = appt.get('start_time', '')[11:16] if appt.get('start_time') else 'soon'
                    subject = "Session starting in 30 minutes"
                    body = build_appointment_message(appt, 'reminder')
                    notify_user(therapist_id, subject, body)
                    count += 1
                    
        return jsonify({'success': True, 'message': f'Sent {count} upcoming session reminders'}), 200
    except Exception as e:
        print(f"[CRON] Upcoming sessions error: {e}")
        return jsonify({'error': str(e)}), 500
'''

with open('app.py', encoding='utf-8') as f:
    content = f.read()

# Insert before the catch-all error handlers or app.run
insert_idx = content.find('@app.errorhandler(404)')
if insert_idx == -1:
    insert_idx = content.find("if __name__ == '__main__':")

if insert_idx != -1:
    new_content = content[:insert_idx] + CRON_ENDPOINTS + '\n\n' + content[insert_idx:]
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Added Cron endpoints!")
else:
    print("Could not find insertion point!")
