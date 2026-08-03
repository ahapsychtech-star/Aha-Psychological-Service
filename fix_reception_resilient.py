import re

with open('portals/reception_portal.html', encoding='utf-8') as f:
    content = f.read()

# 1. Fix showDayDetail merging and add Book Follow-up button
# Replace the old loop with one that updates allAppointments and adds the follow-up button
# We'll use regex to make it resilient to fetch vs apiFetch

show_day_detail_pattern = r"const r = await (fetch|apiFetch)\(`/api/appointments\?start=\$\{dateStr\}&end=\$\{dateStr\}`\);\s+const appts = await r\.json\(\);"

merge_code = r'''const r = await \1(`/api/appointments?start=${dateStr}&end=${dateStr}`);
    const appts = await r.json();
    
    // Fix: Merge into allAppointments so the edit modal can find them
    if (Array.isArray(appts)) {
        appts.forEach(a => {
          const idx = allAppointments.findIndex(existing => String(existing.id) === String(a.id));
          if (idx > -1) allAppointments[idx] = a;
          else allAppointments.push(a);
        });
    }'''

content = re.sub(show_day_detail_pattern, merge_code, content, count=1)


# 2. Add Book Follow-up to the event actions in showDayDetail
event_actions_pattern = r'(<button class="btn btn-gold btn-sm" onclick="openAppointmentEditor\(\$\{a\.id\},(?:.*?)\)"><i class="fa-solid fa-calendar-days"></i></button>)'

follow_up_btn = r'<button class="btn btn-primary btn-sm" onclick="bookFollowUp(${a.client_id}, ${a.therapist_id})" title="Book Follow-up"><i class="fa-solid fa-calendar-plus"></i></button>\n            \1'

content = re.sub(event_actions_pattern, follow_up_btn, content, count=1)


# 3. Add bookFollowUp function (before openAppointmentEditor)
follow_up_fn = r'''
function bookFollowUp(clientId, therapistId) {
  openBookModal();
  setTimeout(() => {
    // Force the first step to select the client
    const searchInput = document.getElementById('clientSearchInput');
    if (searchInput) {
      const client = allClients.find(c => String(c.id) === String(clientId));
      if (client) {
        searchInput.value = client.full_name;
        selectClient(clientId);
        if (therapistId) {
            const th = document.getElementById('vcFilterTherapist');
            if (th) th.value = therapistId;
        }
      }
    }
  }, 300);
}
'''
if 'function bookFollowUp' not in content:
    content = content.replace('function openAppointmentEditor(', follow_up_fn + '\nfunction openAppointmentEditor(')


# 4. Mobile Responsiveness CSS
mobile_css = r'''
/* Mobile Responsiveness for Modals and Calendar */
@media (max-width: 768px) {
  .modal-content {
    width: 95%;
    margin: 10% auto;
    max-height: 85vh;
    overflow-y: auto;
  }
  .cal-day-header {
    font-size: 10px;
    padding: 4px;
  }
  .cal-day-num {
    font-size: 12px;
  }
  .cal-appt-dot {
    font-size: 9px;
    padding: 2px 4px;
    margin: 1px 0;
  }
  .day-event {
    flex-direction: column;
    align-items: flex-start;
  }
  .event-status {
    width: 100%;
    margin-top: 10px;
    justify-content: space-between;
  }
  .event-actions {
    flex-wrap: wrap;
    gap: 4px;
  }
  .header-actions {
    flex-direction: column;
    gap: 8px;
  }
}
'''
if '@media (max-width: 768px)' not in content:
    content = content.replace('</style>', mobile_css + '\n</style>')

with open('portals/reception_portal.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated reception_portal.html")
