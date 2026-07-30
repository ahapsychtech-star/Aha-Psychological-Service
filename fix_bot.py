#!/usr/bin/env python3
"""
Rewrite handle_telegram_update cleanly.
Finds the function by name, replaces it, verifies syntax, writes back.
"""
import ast, re

NEW_FUNCTION = r'''
def handle_telegram_update(update):
    PORTAL_URL = 'https://aha-psychological-service.vercel.app'

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

    def portal_btn(label='🌐 Open Portal'):
        return kb([[(label, f'WEBAPP:{PORTAL_URL}')]])

    def main_menu_kb():
        return kb(
            [('📅 Appointments', '/appointments'), ('👤 Profile', '/profile')],
            [('❓ Help', '/help'), ('📞 Contact', '/contact')],
            [(f'🌐 Open Portal', f'WEBAPP:{PORTAL_URL}')]
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
                main_menu_kb())
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
                kb([[(f'🌐 Open Portal', f'URL:{PORTAL_URL}')]]))
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
                    kb([[(f'🌐 Get New Code', f'URL:{PORTAL_URL}')]]))
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
            kb([[(f'🌐 Open Portal', f'URL:{PORTAL_URL}')]]))
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
                portal_btn('📅 Schedule on Portal'))
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

        msg(chat_id, '\n'.join(lines_out), portal_btn('📅 Full Schedule on Portal'))
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
                [(f'🌐 Edit Profile on Portal', f'URL:{PORTAL_URL}')]
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
            main_menu_kb())
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
            portal_btn('🌐 Visit Website'))
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
            main_menu_kb())
        return True

    # default / unknown
    msg(chat_id,
        f"👋 Hi <b>{user.get('full_name') or user.get('username')}</b>!\n\n"
        f"I did not recognise that command. Use the menu below 👇",
        main_menu_kb())
    return True

'''

with open('app.py', encoding='utf-8') as f:
    content = f.read()

# Find the start of handle_telegram_update
start_marker = '\ndef handle_telegram_update(update):'
start_idx = content.find(start_marker)
if start_idx == -1:
    print('ERROR: Could not find handle_telegram_update')
    exit(1)

# Find the next top-level function after it
# (def at column 0, not inside a class or other function)
search_from = start_idx + len(start_marker)
next_def = re.search(r'\ndef [a-zA-Z]', content[search_from:])
if not next_def:
    print('ERROR: Could not find next function after handle_telegram_update')
    exit(1)

end_idx = search_from + next_def.start()

# Replace the old function with new one
new_content = content[:start_idx] + NEW_FUNCTION + content[end_idx:]

# Verify syntax
try:
    ast.parse(new_content)
    print('Syntax OK')
except SyntaxError as e:
    print(f'SYNTAX ERROR: {e}')
    exit(1)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

# Verify functions still exist
with open('app.py', encoding='utf-8') as f:
    lines = f.readlines()

print(f'Total lines: {len(lines)}')
for i, l in enumerate(lines, 1):
    if any(x in l for x in ['def handle_telegram_update', 'def telegram_polling_loop', 'def start_telegram_polling']):
        print(f'  Line {i}: {l.rstrip()}')
print('Done.')
