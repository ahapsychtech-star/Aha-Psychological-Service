import ast
import re

NEW_NOTIFY = r'''
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
        
    text = f"🔔 <b>{subject}</b>\n\n{body}"
    
    # Build inline button specific to the user role
    role = user['role']
    base_url = 'https://aha-psychological-service.vercel.app'
    portal = f"{base_url}/portals/{role}_portal.html" if role in ('therapist', 'receptionist', 'admin') else base_url
    
    markup = {
        'inline_keyboard': [
            [{'text': '🌐 Open Portal', 'web_app': {'url': portal}}]
        ]
    }
    
    send_telegram_message(chat_id, text, parse_mode='HTML', reply_markup=markup)
'''

with open('app.py', encoding='utf-8') as f:
    content = f.read()

# Replace build_appointment_message
start_marker = '\ndef build_appointment_message'
start_idx = content.find(start_marker)
if start_idx != -1:
    next_def = re.search(r'\ndef notify_appointment_update', content[start_idx+1:])
    if next_def:
        end_idx = start_idx + 1 + next_def.start()
        # Find the end of notify_user block too
        notify_user_start = content.find('\ndef notify_user')
        if notify_user_start != -1:
            notify_roles_start = re.search(r'\ndef notify_roles', content[notify_user_start+1:])
            if notify_roles_start:
                notify_user_end = notify_user_start + 1 + notify_roles_start.start()
                
                # Do the replacements
                # 1. Replace notify_user
                content = content[:notify_user_start] + content[notify_user_end:] 
                # 2. Replace build_appointment_message (and inject notify_user after it)
                start_idx = content.find(start_marker)
                next_def = re.search(r'\ndef notify_appointment_update', content[start_idx+1:])
                end_idx = start_idx + 1 + next_def.start()
                
                content = content[:start_idx] + '\n' + NEW_NOTIFY + '\n' + content[end_idx:]

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated message formatter and notification helper!")
