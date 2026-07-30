import re

with open('portals/reception_portal.html', encoding='utf-8') as f:
    content = f.read()

# 1. Fix showDayDetail merging and add Book Follow-up button
# Replace the old loop with one that updates allAppointments and adds the follow-up button
old_show = r'''async function showDayDetail(dateStr, label) {
  const panel = document.getElementById('dayDetailPanel');
  document.getElementById('dayDetailTitle').textContent = label;
  panel.style.display='block';
  try {
    const r = await apiFetch(`/api/appointments?start=${dateStr}&end=${dateStr}`);
    const appts = await r.json();'''

new_show = r'''async function showDayDetail(dateStr, label) {
  const panel = document.getElementById('dayDetailPanel');
  document.getElementById('dayDetailTitle').textContent = label;
  panel.style.display='block';
  try {
    const r = await apiFetch(`/api/appointments?start=${dateStr}&end=${dateStr}`);
    const appts = await r.json();
    
    // Fix: Merge into allAppointments so the edit modal can find them
    appts.forEach(a => {
      const idx = allAppointments.findIndex(existing => String(existing.id) === String(a.id));
      if (idx > -1) allAppointments[idx] = a;
      else allAppointments.push(a);
    });
'''
content = content.replace(old_show, new_show, 1) # Only replace first occurrence


# 2. Add Book Follow-up to the event actions in showDayDetail
old_event = r'''<div class="event-actions">
              <button class="btn btn-success btn-sm" onclick="updateApptStatus(${a.id},'completed')"><i class="fa-solid fa-check"></i></button>
              <button class="btn btn-outline btn-sm" onclick="changeAppt(${a.id},'temporary')"><i class="fa-solid fa-clock-rotate-left"></i></button>
              <button class="btn btn-gold btn-sm" onclick="changeAppt(${a.id},'permanent')"><i class="fa-solid fa-calendar-days"></i></button>
              <button class="btn btn-danger btn-sm" onclick="updateApptStatus(${a.id},'cancelled')"><i class="fa-solid fa-ban"></i></button>
            </div>'''

new_event = r'''<div class="event-actions">
              <button class="btn btn-primary btn-sm" onclick="bookFollowUp(${a.client_id}, ${a.therapist_id})" title="Book Follow-up"><i class="fa-solid fa-calendar-plus"></i></button>
              <button class="btn btn-success btn-sm" onclick="updateApptStatus(${a.id},'completed')" title="Complete"><i class="fa-solid fa-check"></i></button>
              <button class="btn btn-outline btn-sm" onclick="changeAppt(${a.id},'temporary')" title="Temporary Change"><i class="fa-solid fa-clock-rotate-left"></i></button>
              <button class="btn btn-gold btn-sm" onclick="changeAppt(${a.id},'permanent')" title="Permanent Change"><i class="fa-solid fa-calendar-days"></i></button>
              <button class="btn btn-danger btn-sm" onclick="updateApptStatus(${a.id},'cancelled')" title="Cancel"><i class="fa-solid fa-ban"></i></button>
            </div>'''
content = content.replace(old_event, new_event, 1)

# 3. Add bookFollowUp function
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
            document.getElementById('vcFilterTherapist').value = therapistId;
        }
      }
    }
  }, 300);
}
'''
content = content.replace('function changeAppt(id, scope', follow_up_fn + '\nfunction changeAppt(id, scope')


# 4. Delete the duplicated showDayDetail at the end of the file
# It starts around line 3393.
content = re.sub(r'async function showDayDetail.*?</script>', '</script>', content, flags=re.DOTALL)


# 5. Mobile Responsiveness CSS
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
content = content.replace('</style>', mobile_css + '\n</style>')

with open('portals/reception_portal.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated reception_portal.html")
