
// â”€â”€â”€ Globals â”€â”€â”€
let currentUser = null;
let allClients = [];
let allAppointments = [];
let allRooms = [];
let allInvoices = [];
let calDate = new Date();
let calView = 'month';
let selectedAssignClient = null;
let currentDrawerClient = null;
let currentDrawerTab = 'info';
let currentClientData = null;
let currentClientView = null;
let bookVcCurrentDate = new Date();
let bookVcView = 'day';
let bookVcAppointments = [];
let bookVcSelectedStart = null;
let bookVcSelectedEnd = null;
let bookClientSearch = '';

// â”€â”€â”€ Init â”€â”€â”€
async function init() {
  // Clock
  setInterval(() => {
    const now = new Date();
    document.getElementById('topbarClock').textContent = now.toLocaleTimeString('en-US', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
  }, 1000);

  // Date / greeting
  const now = new Date();
  const h = now.getHours();
  const greeting = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
  document.getElementById('dashGreeting').textContent = greeting + '!';
  document.getElementById('dashDate').textContent = now.toLocaleDateString('en-US', {weekday:'long',year:'numeric',month:'long',day:'numeric'});

  // Fetch current user
  try {
    const res = await apiFetch('/api/me');
    if (res.ok) {
      currentUser = await res.json();
      document.getElementById('sidebarName').textContent = currentUser.full_name || currentUser.username;
      document.getElementById('sidebarRole').textContent = currentUser.role;
      document.getElementById('sidebarAvatar').textContent = (currentUser.full_name || currentUser.username)[0].toUpperCase();
    }
  } catch(e){}

  // Nav items
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => showSection(item.dataset.section));
  });

  await loadRooms();
  await loadNewClientBookingTherapists();
  ['nc_book_date','nc_book_start','nc_book_end'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', loadNewClientBookingRoomAvailability);
  });
  await loadDashboard();
  await loadAllClients();
  loadCalendar();
  loadInvoices();
  loadMessages();
  setInterval(() => loadAlerts(), 60000);
}

function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('sec-' + name).classList.add('active');
  document.querySelector(`.nav-item[data-section="${name}"]`)?.classList.add('active');
  const titles = {
    'dashboard':'Dashboard','calendar':'Calendar','clients':'Client Registry',
    'new-client':'Register New Client','assignment':'Smart Assignment',
    'appointments':'Appointments','finance':'Finance','messages':'Messages'
  };
  document.getElementById('topbarTitle').textContent = titles[name] || name;
  if(name==='clients') renderClientsTable();
  if(name==='calendar') renderCalendar();
  if(name==='assignment') loadAssignQueue();
  if(name==='appointments') loadAppointments();
  if(name==='finance') loadInvoices();
  if(name==='messages') loadMessages();
  if(name==='new-client') {
    const today = new Date().toISOString().split('T')[0];
    const bookDate = document.getElementById('nc_book_date');
    if (bookDate && !bookDate.value) bookDate.value = today;
    loadNewClientBookingRoomAvailability();
  }
}

// â”€â”€â”€ Dashboard â”€â”€â”€
async function loadDashboard() {
  try {
    const res = await apiFetch('/api/analytics/dashboard');
    const data = await res.json();
    const s = data.stats;
    document.getElementById('statToday').textContent = s.today_appointments;
    document.getElementById('statPending').textContent = s.pending_assignment;
    document.getElementById('statAlerts').textContent = s.active_alerts;
    document.getElementById('statClients').textContent = s.active_clients;
    document.getElementById('statInvoices').textContent = s.pending_invoices;
    updateAlertBadge(s.active_alerts);

    // Revenue for finance
    document.getElementById('revTotal').textContent = (s.total_revenue||0).toLocaleString();
    document.getElementById('revMonth').textContent = (s.revenue_this_month||0).toLocaleString();
    document.getElementById('revPaidCount').textContent = s.pending_invoices;
  } catch(e){}

  await loadAlerts();
  await loadTodaySchedule();
  await loadPendingQueue();
}

async function loadAlerts() {
  try {
    const res = await apiFetch('/api/alerts');
    const alerts = await res.json();
    updateAlertBadge(alerts.length);
    const el = document.getElementById('riskAlertsList');
    if (!alerts.length) {
      el.innerHTML = `<div style="display:flex;align-items:center;gap:10px;color:var(--success);padding:10px">
        <i class="fa-solid fa-circle-check" style="font-size:20px"></i>
        <span style="font-weight:600">No active risk alerts</span></div>`;
    } else {
      el.innerHTML = alerts.map(a => `
        <div style="display:flex;align-items:center;gap:12px;padding:12px;background:rgba(239,68,68,.04);border-radius:8px;margin-bottom:8px;border:1px solid rgba(239,68,68,.1)">
          <i class="fa-solid fa-user-shield" style="color:var(--danger);font-size:18px"></i>
          <div style="flex:1">
            <div style="font-weight:700;font-size:13px">${a.client_name} <span style="color:var(--text-muted);font-size:11px">${a.client_code}</span></div>
            <div style="font-size:12px;color:var(--text-muted)">${a.alert_type} - ${a.severity} severity - ${formatTime(a.triggered_at)}</div>
          </div>
          <span class="badge badge-red">${a.severity}</span>
          <button class="btn btn-sm btn-ghost" onclick="resolveAlert(${a.id})">Resolve</button>
        </div>`).join('');
    }
  } catch(e){}
}

function updateAlertBadge(count) {
  const badge = document.getElementById('alertBadge');
  if (count > 0) { badge.style.display='flex'; badge.textContent = count; }
  else badge.style.display='none';
}

async function resolveAlert(id) {
  await apiFetch(`/api/alerts/${id}/resolve`, {method:'POST'});
  loadAlerts();
  toast('Alert resolved');
}

async function loadTodaySchedule() {
  const today = new Date().toISOString().split('T')[0];
  try {
    const res = await apiFetch(`/api/appointments?start=${today}&end=${today}`);
    const appts = await res.json();
    const el = document.getElementById('todaySchedule');
    if (!appts.length) {
      el.innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-muted)"><i class="fa-regular fa-calendar-xmark" style="font-size:24px;margin-bottom:8px"></i><p>No appointments today</p></div>`;
    } else {
      el.innerHTML = appts.slice(0,6).map(a => `
        <div class="day-event" onclick="openClientDrawer(${a.client_id})">
          <div class="event-time"><div>${formatApptTime(a.start_time)}</div><div style="font-size:10px;opacity:.7;margin-top:2px">${formatDate(a.start_time)}</div></div>
          <div class="event-info">
            <div class="ev-name"><span>${a.client_name}</span><span class="appt-chip">${a.client_code||'Code'}</span></div>
            <div class="ev-sub">${a.therapist_name || '-'} - ${a.type}</div>
          </div>
          <div class="event-status">${statusBadge(a.status)}</div>
          <div style="display:flex;gap:4px;margin-left:4px">
            <button class="btn btn-sm btn-success" onclick="updateApptStatus(${a.id},'completed')" title="Complete"><i class="fa-solid fa-check"></i></button>
            <button class="btn btn-sm btn-danger" onclick="updateApptStatus(${a.id},'no_show')" title="No Show"><i class="fa-solid fa-xmark"></i></button>
          </div>
        </div>`).join('');
    }
  } catch(e){ document.getElementById('todaySchedule').innerHTML='<p style="color:var(--text-muted)">Failed to load</p>'; }
}

async function loadPendingQueue() {
  try {
    const res = await apiFetch('/api/clients');
    const clients = await res.json();
    const pending = clients.filter(c => ['registered','screening_completed'].includes(c.status) && !c.assigned_therapist_id);
    const el = document.getElementById('pendingQueue');
    if (!pending.length) {
      el.innerHTML = `<div style="text-align:center;padding:20px;color:var(--success);font-size:13px;font-weight:600"><i class="fa-solid fa-circle-check"></i> All clients assigned</div>`;
    } else {
      el.innerHTML = pending.slice(0,5).map(c => `
        <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;background:var(--bg);cursor:pointer;margin-bottom:6px"
             onclick="showSection('assignment');setTimeout(()=>selectAssignClient(${c.id}),400)">
          <div style="width:32px;height:32px;border-radius:50%;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px">${c.full_name[0]}</div>
          <div style="flex:1">
            <div style="font-size:13px;font-weight:700">${c.full_name}</div>
            <div style="font-size:11px;color:var(--text-muted)">${c.client_code} - ${c.status.replace('_',' ')}</div>
          </div>
          <span class="badge badge-orange">${c.risk_level}</span>
        </div>`).join('');
    }
  } catch(e){}
}

// â”€â”€â”€ Calendar â”€â”€â”€
function isClientBookable(client) {
  if (!client) return false;
  const status = String(client.status || '').toLowerCase();
  return client.is_active !== 0 && ['registered', 'screening_completed', 'awaiting_assignment', 'assigned', 'active'].includes(status);
}

function getBookableClients() {
  const busyClientIds = new Set((bookVcAppointments || [])
    .filter(a => !isFinalAppointmentStatus(a.status))
    .map(a => String(a.client_id)));
  return (allClients || [])
    .filter(c => isClientBookable(c) && !busyClientIds.has(String(c.id)))
    .sort((a, b) => (a.full_name || '').localeCompare(b.full_name || ''));
}

function renderBookClientPicker() {
  const list = document.getElementById('bookClientResults');
  const selected = document.getElementById('bookClientSelected');
  const hidden = document.getElementById('bookClient');
  const searchEl = document.getElementById('bookClientSearch');
  if (!list || !selected || !hidden) return;
  const q = String(bookClientSearch || searchEl?.value || '').trim().toLowerCase();
  const clients = getBookableClients().filter(c => {
    if (!q) return true;
    return String(c.full_name || '').toLowerCase().includes(q) || String(c.client_code || '').toLowerCase().includes(q);
  });
  if (!clients.length) {
    list.innerHTML = '<div class="client-picker-empty">No active clients match this search, or they already have an appointment.</div>';
  } else {
    list.innerHTML = clients.slice(0, 12).map(c => `
      <div class="client-picker-item ${String(hidden.value) === String(c.id) ? 'selected' : ''}" onclick="selectBookClient(${c.id})">
        <div class="client-picker-main">
          <div class="client-picker-name">${c.full_name || '-'}</div>
          <div class="client-picker-code">${c.client_code || '-'}</div>
          <div class="client-picker-meta">
            ${statusBadge(c.status)}
            ${riskBadge(c.risk_level || 'low')}
          </div>
        </div>
        <div style="font-size:11px;color:var(--text-muted);font-weight:700">Active</div>
      </div>`).join('');
  }
  const selectedClient = (allClients || []).find(c => String(c.id) === String(hidden.value));
  if (selectedClient) {
    selected.style.display = 'block';
    selected.textContent = `${selectedClient.full_name}  ${selectedClient.client_code || 'No code'}  ${String(selectedClient.status || '').replace(/_/g, ' ')}`;
  } else {
    selected.style.display = 'none';
    selected.textContent = '';
  }
}

function selectBookClient(id) {
  const client = (allClients || []).find(c => String(c.id) === String(id));
  if (!client) return;
  const searchEl = document.getElementById('bookClientSearch');
  const hidden = document.getElementById('bookClient');
  if (hidden) hidden.value = client.id;
  if (searchEl) searchEl.value = `${client.full_name || ''}${client.client_code ? ` (${client.client_code})` : ''}`.trim();
  bookClientSearch = searchEl?.value || '';
  renderBookClientPicker();
}

function filterBookClients() {
  bookClientSearch = document.getElementById('bookClientSearch')?.value || '';
  const hidden = document.getElementById('bookClient');
  if (hidden && hidden.value && !bookClientSearch.trim()) hidden.value = '';
  renderBookClientPicker();
}

function bookVcInit() {
  bookVcCurrentDate = new Date();
  bookVcSelectedStart = null;
  bookVcSelectedEnd = null;
  const lbl = document.getElementById('bookVcSelectedLabel');
  if (lbl) lbl.style.display = 'none';
  bookVcFetchData();
}

async function bookVcFetchData() {
  try {
    const r = await apiFetch('/api/appointments');
    bookVcAppointments = await r.json();
    renderBookClientPicker();
    bookVcRender();
  } catch (e) {}
}

function bookVcNav(dir) {
  if (bookVcView === 'day') bookVcCurrentDate.setDate(bookVcCurrentDate.getDate() + dir);
  else bookVcCurrentDate.setDate(bookVcCurrentDate.getDate() + (dir * 7));
  bookVcSelectedStart = null;
  bookVcSelectedEnd = null;
  const lbl = document.getElementById('bookVcSelectedLabel');
  if (lbl) lbl.style.display = 'none';
  bookVcRender();
}

function bookVcSetView(view) {
  bookVcView = view;
  document.getElementById('bookVcBtnDay')?.classList.toggle('active', view === 'day');
  document.getElementById('bookVcBtnWeek')?.classList.toggle('active', view === 'week');
  bookVcRender();
}

function bookVcGetWeekDays(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  const days = [];
  for (let i = 0; i < 5; i++) {
    const nd = new Date(monday);
    nd.setDate(monday.getDate() + i);
    days.push(nd);
  }
  return days;
}

function bookVcRender() {
  const grid = document.getElementById('bookVcGrid');
  const label = document.getElementById('bookVcDateLabel');
  if (!grid || !label) return;
  const days = bookVcView === 'day' ? [bookVcCurrentDate] : bookVcGetWeekDays(bookVcCurrentDate);
  label.textContent = bookVcView === 'day'
    ? days[0].toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric', year:'numeric'})
    : `${days[0].toLocaleDateString('en-US', {month:'short', day:'numeric'})} - ${days[4].toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'})}`;
  let html = `<div class="vc-time-col"><div class="vc-day-header">Time</div>`;
  for (let h = 8; h <= 19; h++) {
    const hour = h > 12 ? h - 12 : h;
    html += `<div class="vc-time-slot">${hour} ${h >= 12 ? 'PM' : 'AM'}</div>`;
  }
  html += `</div><div class="vc-days">`;
  days.forEach(day => {
    html += `<div class="vc-day-col"><div class="vc-day-header">${day.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'})}</div>`;
    for (let h = 8; h <= 19; h++) {
      const slotStart = new Date(day);
      slotStart.setHours(h, 0, 0, 0);
      const slotEnd = new Date(day);
      slotEnd.setHours(h + 1, 0, 0, 0);
      const slotStartStr = slotStart.toISOString();
      const slotEndStr = slotEnd.toISOString();
      const isBusy = bookVcAppointments.some(a => {
        if (['cancelled', 'no_show', 'terminated'].includes(String(a.status || '').toLowerCase())) return false;
        const aStart = new Date(a.start_time);
        const aEnd = new Date(a.end_time || a.start_time);
        return aStart < slotEnd && aEnd > slotStart;
      });
      let cls = 'vc-slot available';
      if (isBusy) cls = 'vc-slot busy';
      if (bookVcSelectedStart === slotStartStr) cls += ' selected';
      html += `<div class="${cls}" data-start="${slotStartStr}" data-end="${slotEndStr}" onclick="bookVcSlotClick(this, ${isBusy})"></div>`;
    }
    html += `</div>`;
  });
  html += `</div>`;
  grid.innerHTML = html;
}

function bookVcSlotClick(el, isBusy) {
  if (isBusy) return;
  const start = el.dataset.start;
  const end = el.dataset.end;
  bookVcSelectedStart = start;
  bookVcSelectedEnd = end;
  const dateEl = document.getElementById('bookDate');
  const startEl = document.getElementById('bookStart');
  const endEl = document.getElementById('bookEnd');
  const dtEl = document.getElementById('bookVcDateTime');
  const endHiddenEl = document.getElementById('bookVcEndTime');
  if (dateEl) dateEl.value = start.slice(0, 10);
  if (startEl) startEl.value = start.slice(11, 16);
  if (endEl) endEl.value = end.slice(11, 16);
  if (dtEl) dtEl.value = start;
  if (endHiddenEl) endHiddenEl.value = end;
  const lbl = document.getElementById('bookVcSelectedLabel');
  if (lbl) {
    lbl.textContent = `Selected: ${new Date(start).toLocaleString('en-US', {weekday:'short', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'})} - ${new Date(end).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;
    lbl.style.display = 'block';
  }
  loadBookingRoomAvailability();
  bookVcRender();
}

function loadCalendar() { renderCalendar(); }

function switchView(v) {
  calView = v;
  document.querySelectorAll('.cal-view-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('view'+v.charAt(0).toUpperCase()+v.slice(1)).classList.add('active');
  renderCalendar();
}

function renderCalendar() {
  if (calView === 'month') renderMonthView();
  else if (calView === 'week') renderWeekView();
  else renderDayView();
}

async function renderMonthView() {
  const y = calDate.getFullYear(), m = calDate.getMonth();
  document.getElementById('calTitle').textContent = new Date(y,m,1).toLocaleDateString('en-US',{month:'long',year:'numeric'});
  document.getElementById('calPrev').onclick = () => { calDate = new Date(y, m-1, 1); renderCalendar(); };
  document.getElementById('calNext').onclick = () => { calDate = new Date(y, m+1, 1); renderCalendar(); };

  // Fetch appointments for this month
  const start = new Date(y,m,1).toISOString().split('T')[0];
  const end = new Date(y,m+1,0).toISOString().split('T')[0];
  let appts = [];
  try { const r = await apiFetch(`/api/appointments?start=${start}&end=${end}`); appts = await r.json(); } catch(e){}

  const apptMap = {};
  appts.forEach(a => {
    const d = a.start_time ? a.start_time.split('T')[0] : a.start_time?.split(' ')[0];
    if (!apptMap[d]) apptMap[d] = [];
    apptMap[d].push(a);
  });

  const firstDay = new Date(y,m,1).getDay();
  const daysInMonth = new Date(y,m+1,0).getDate();
  const today = new Date().toDateString();

  let html = `<div class="cal-grid">
    ${['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d=>`<div class="cal-day-header">${d}</div>`).join('')}`;

  for (let i = 0; i < firstDay; i++) html += `<div class="cal-day other-month"><div class="cal-day-num"></div></div>`;

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const isToday = new Date(y,m,d).toDateString() === today;
    const dayAppts = apptMap[dateStr] || [];
    html += `<div class="cal-day${isToday?' today':''}" onclick="showDayDetail('${dateStr}','${new Date(y,m,d).toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric'})}')">
      <div class="cal-day-num">${d}</div>
      ${dayAppts.slice(0,2).map(a=>{ const visual = appointmentVisual(a); return `<span class="cal-appt-dot ${visual.cls}" style="background:${visual.palette.base};color:#fff">${a.client_name?.split(' ')[0]||'Appt'}</span>`; }).join('')}
      ${dayAppts.length>2?`<span style="font-size:10px;color:var(--text-muted)">+${dayAppts.length-2} more</span>`:''}
    </div>`;
  }
  html += '</div>';
  document.getElementById('calContainer').innerHTML = html;
}

async function renderWeekView() {
  const d = new Date(calDate);
  d.setDate(d.getDate() - d.getDay());
  const weekStart = new Date(d);
  const weekEnd = new Date(d); weekEnd.setDate(weekEnd.getDate()+6);

  document.getElementById('calTitle').textContent = `${weekStart.toLocaleDateString('en-US',{month:'short',day:'numeric'})} - ${weekEnd.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})}`;
  document.getElementById('calPrev').onclick = () => { calDate = new Date(calDate); calDate.setDate(calDate.getDate()-7); renderCalendar(); };
  document.getElementById('calNext').onclick = () => { calDate = new Date(calDate); calDate.setDate(calDate.getDate()+7); renderCalendar(); };

  const days = [];
  for(let i=0;i<7;i++) { const dd=new Date(weekStart); dd.setDate(dd.getDate()+i); days.push(dd); }

  const start = weekStart.toISOString().split('T')[0];
  const end = weekEnd.toISOString().split('T')[0];
  let appts = [];
  try { const r = await apiFetch(`/api/appointments?start=${start}&end=${end}`); appts = await r.json(); } catch(e){}

  const apptMap = {};
  appts.forEach(a => {
    const dt = a.start_time || '';
    const dateKey = dt.includes('T') ? dt.split('T')[0] : dt.split(' ')[0];
    if (!apptMap[dateKey]) apptMap[dateKey] = [];
    apptMap[dateKey].push(a);
  });

  const colors = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ef4444','#06b6d4','#ec4899','#f97316'];
  const hours = [];
  for(let h=7;h<20;h++) hours.push(h);

  let html = `<div class="week-grid">
    <div class="week-header" style="background:var(--surface)"></div>
    ${days.map((day,i)=>`<div class="week-header">${day.toLocaleDateString('en-US',{weekday:'short'})} ${day.getDate()}</div>`).join('')}`;

  hours.forEach(h => {
    html += `<div class="week-time">${h<12?h+' AM':h===12?'12 PM':(h-12)+' PM'}</div>`;
    days.forEach((day,di) => {
      const dateKey = day.toISOString().split('T')[0];
      const cellAppts = (apptMap[dateKey]||[]).filter(a => {
        const t = a.start_time||'';
        const hr = parseInt(t.includes('T')?t.split('T')[1]:t.split(' ')[1]);
        return hr === h;
      });
      html += `<div class="week-cell">${cellAppts.map((a,ai)=>`<div class="week-appt" style="background:${appointmentVisual(a).palette.base}" onclick='alert("${a.client_name} with ${a.therapist_name}")'>${a.client_name?.split(' ')[0]}</div>`).join('')}</div>`;
    });
  });
  html += '</div>';
  document.getElementById('calContainer').innerHTML = html;
}

async function renderDayView() {
  const dateStr = calDate.toISOString().split('T')[0];
  document.getElementById('calTitle').textContent = calDate.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'});
  document.getElementById('calPrev').onclick = () => { calDate.setDate(calDate.getDate()-1); renderCalendar(); };
  document.getElementById('calNext').onclick = () => { calDate.setDate(calDate.getDate()+1); renderCalendar(); };
  await showDayDetail(dateStr, calDate.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric'}));
  document.getElementById('calContainer').innerHTML = '';
}

async function showDayDetail(dateStr, label) {
  const panel = document.getElementById('dayDetailPanel');
  document.getElementById('dayDetailTitle').textContent = label;
  panel.style.display='block';
  try {
    const r = await apiFetch(`/api/appointments?start=${dateStr}&end=${dateStr}`);
    const appts = await r.json();
    if (!appts.length) {
      document.getElementById('dayDetailList').innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-muted)"><i class="fa-regular fa-calendar" style="font-size:28px;margin-bottom:8px"></i><p style="font-weight:600">No appointments this day</p><p style="font-size:12px;margin-top:4px">Use the appointment panel to book, change, or cancel a slot.</p></div>`;
    } else {
      document.getElementById('dayDetailList').innerHTML = appts.map(a => `
        <div class="day-event">
          <div class="event-time">${formatApptTime(a.start_time)}</div>
          <div class="event-info">
            <div class="ev-name">${a.client_name}</div>
            <div class="ev-sub">${a.therapist_name || '-'} - ${a.type} - ${a.location || '-'}</div>
          </div>
          <div class="event-status" onclick="event.stopPropagation()">
            <button class="btn btn-ghost btn-sm" onclick="openClientDrawer(${a.client_id})"><i class="fa-regular fa-user"></i>Client</button>
            <div class="event-actions">
              <button class="btn btn-success btn-sm" onclick="updateApptStatus(${a.id},'completed')"><i class="fa-solid fa-check"></i></button>
              <button class="btn btn-outline btn-sm" onclick="changeAppt(${a.id},'temporary')"><i class="fa-solid fa-clock-rotate-left"></i></button>
              <button class="btn btn-gold btn-sm" onclick="changeAppt(${a.id},'permanent')"><i class="fa-solid fa-calendar-days"></i></button>
              <button class="btn btn-danger btn-sm" onclick="updateApptStatus(${a.id},'cancelled')"><i class="fa-solid fa-ban"></i></button>
            </div>
          </div>
        </div>`).join('');
    }
  } catch(e){}
}

// â”€â”€â”€ Clients â”€â”€â”€
async function loadAllClients() {
  try {
    const r = await apiFetch('/api/clients');
    allClients = await r.json();
    renderClientsTable();
  } catch(e){}
}

function filterClients() { renderClientsTable(); }

function renderClientsTable() {
  const q = (document.getElementById('clientSearch')?.value||'').toLowerCase();
  const st = document.getElementById('filterStatus')?.value||'';
  const risk = document.getElementById('filterRisk')?.value||'';
  const filtered = allClients.filter(c =>
    (!q || c.full_name?.toLowerCase().includes(q) || c.client_code?.toLowerCase().includes(q) || c.phone?.includes(q)) &&
    (!st || c.status === st) && (!risk || c.risk_level === risk));
  const tb = document.getElementById('clientsTableBody');
  if (!tb) return;
  if (!filtered.length) { tb.innerHTML=`<tr><td colspan="8" style="text-align:center;padding:30px;color:var(--text-muted)">No clients found</td></tr>`; return; }
  tb.innerHTML = filtered.map(c => `
    <tr style="cursor:pointer" onclick="openClientDrawer(${c.id})">
      <td><span style="font-family:monospace;font-size:12px;font-weight:700;color:var(--navy)">${c.client_code||'-'}</span></td>
      <td><strong>${c.full_name}</strong></td>
      <td>${c.phone||'-'}</td>
      <td>${statusBadge(c.status)}</td>
      <td>${riskBadge(c.risk_level)}</td>
      <td style="font-size:12px;color:var(--text-muted)">${formatDate(c.registration_date)}</td>
      <td style="font-size:13px">${c.therapist_name||'<span style="color:var(--text-muted)">Unassigned</span>'}</td>
      <td onclick="event.stopPropagation()" style="display:flex;gap:4px">
        <button class="btn btn-sm btn-ghost" onclick="openClientDrawer(${c.id})"><i class="fa-solid fa-eye"></i></button>
        <button class="btn btn-sm btn-gold" onclick="selectAndAssign(${c.id})"><i class="fa-solid fa-user-check"></i></button>
      </td>
    </tr>`).join('');
}

async function openClientDrawer(cid) {
  currentDrawerClient = cid;
  currentDrawerTab = 'info';
  document.getElementById('clientDrawer').classList.add('open');
  document.getElementById('clientDrawerOverlay').classList.add('active');
  document.getElementById('drawerClientName').textContent = 'Loading...';
  document.getElementById('drawerContent').innerHTML = `<div class="skel" style="height:200px"></div>`;
  try {
    const r = await apiFetch(`/api/clients/${cid}`);
    const data = await r.json();
    document.getElementById('drawerClientName').textContent = data.client.full_name;
    switchDrawerTab('info', data);
  } catch(e){}
}

function closeClientDrawer() {
  document.getElementById('clientDrawer').classList.remove('open');
  document.getElementById('clientDrawerOverlay').classList.remove('active');
}

function switchDrawerTab(tab, data) {
  currentDrawerTab = tab;
  document.querySelectorAll('#drawerTabs button').forEach(b => {
    b.className = b.textContent.trim().toLowerCase().startsWith(tab.charAt(0).toUpperCase()+tab.slice(1)) ? 'btn btn-primary btn-sm' : 'btn btn-ghost btn-sm';
  });
  if (!data) { apiFetch(`/api/clients/${currentDrawerClient}`).then(r=>r.json()).then(d => renderDrawerTab(tab,d)); return; }
  renderDrawerTab(tab, data);
}

function renderDrawerTab(tab, data) {
  const c = data.client;
  const el = document.getElementById('drawerContent');
  if (tab==='info') {
    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:20px;padding:16px;background:var(--bg);border-radius:12px">
        <div style="width:56px;height:56px;border-radius:50%;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800">${c.full_name[0]}</div>
        <div><div style="font-size:17px;font-weight:800">${c.full_name}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${c.client_code} - Registered ${formatDate(c.registration_date)}</div>
          <div style="margin-top:6px;display:flex;gap:6px">${statusBadge(c.status)}${riskBadge(c.risk_level)}</div></div>
      </div>
      ${infoRow('Phone',c.phone)}${infoRow('Email',c.email)}${infoRow('Gender',c.gender)}
      ${infoRow('Date of Birth',c.date_of_birth)}${infoRow('Address',c.address)}
      <div style="margin:14px 0;border-top:1px solid var(--border);padding-top:14px;font-size:13px;font-weight:700;color:var(--text-muted)">EMERGENCY CONTACT</div>
      ${infoRow('Name',c.emergency_contact_name)}${infoRow('Phone',c.emergency_contact_phone)}
      <div style="margin:14px 0;border-top:1px solid var(--border);padding-top:14px;font-size:13px;font-weight:700;color:var(--text-muted)">PREFERENCES</div>
      ${infoRow('Language',c.language_pref)}${infoRow('Therapist Preference',c.therapist_gender_pref)}
      ${infoRow('Intake Source',c.intake_source)}${infoRow('Assigned Therapist',c.therapist_name||'Unassigned')}
      <div style="display:flex;gap:8px;margin-top:16px">
        <button class="btn btn-gold btn-sm" onclick="selectAndAssign(${c.id})"><i class="fa-solid fa-user-check"></i>Assign Therapist</button>
        <button class="btn btn-outline btn-sm" onclick="openInvoiceForClient(${c.id})"><i class="fa-solid fa-file-invoice"></i>Create Invoice</button>
      </div>`;
  } else if (tab==='journey') {
    const j = data.journey;
    el.innerHTML = j.length ? `<div class="timeline">${j.map(e=>`
      <div class="timeline-item">
        <div class="timeline-dot"><i class="fa-solid fa-arrow-right" style="font-size:10px"></i></div>
        <div class="timeline-content">
          <div class="timeline-date">${formatDate(e.changed_at)} by ${e.changed_by_name||'System'}</div>
          <div class="timeline-text">${e.stage.replace(/_/g,' ').toUpperCase()}</div>
          ${e.notes?`<div style="font-size:12px;color:var(--text-muted);margin-top:4px">${e.notes}</div>`:''}
        </div>
      </div>`).join('')}</div>` : '<p style="color:var(--text-muted)">No journey records.</p>';
  } else if (tab==='appointments') {
    const a = data.appointments;
    el.innerHTML = a.length ? `<div style="display:flex;flex-direction:column;gap:8px">${a.map(ap=>`
      <div style="padding:12px;border-radius:8px;background:var(--bg);display:flex;align-items:center;gap:10px">
        <i class="fa-solid fa-calendar" style="color:var(--navy)"></i>
        <div><div style="font-size:13px;font-weight:700">${formatDate(ap.start_time)}</div>
          <div style="font-size:12px;color:var(--text-muted)">${ap.type} with ${ap.therapist_name||'TBA'}</div></div>
        <div style="margin-left:auto">${statusBadge(ap.status)}</div>
      </div>`).join('')}</div>` : '<p style="color:var(--text-muted)">No appointments.</p>';
  } else if (tab==='finance') {
    const inv = data.invoices;
    el.innerHTML = inv.length ? `<div>${inv.map(i=>`
      <div style="padding:12px;border-radius:8px;background:var(--bg);margin-bottom:8px;display:flex;align-items:center;gap:10px">
        <i class="fa-solid fa-file-invoice-dollar" style="color:var(--navy)"></i>
        <div><div style="font-size:13px;font-weight:700">ETB ${(i.amount||0).toLocaleString()}</div>
          <div style="font-size:12px;color:var(--text-muted)">Due: ${formatDate(i.due_date)}</div></div>
        <div style="margin-left:auto">${invStatusBadge(i.status)}</div>
        ${i.status==='pending'?`<button class="btn btn-sm btn-success" onclick="openPaymentFor(${i.id},${i.client_id})">Pay</button>`:''}
      </div>`).join('')}</div>` : '<p style="color:var(--text-muted)">No invoices.</p>';
  }
}

function infoRow(label, val) {
  return `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
    <span style="font-size:12px;font-weight:700;color:var(--text-muted)">${label.toUpperCase()}</span>
    <span style="font-size:13px;font-weight:600">${val||'-'}</span>
  </div>`;
}

// â”€â”€â”€ New Client â”€â”€â”€
function formatDate(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch (e) {
    return String(value);
  }
}

function formatApptTime(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return String(value);
  }
}

function formatTime(value) {
  if (!value) return '-';
  try {
    return `${formatDate(value)} ${new Date(value).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
  } catch (e) {
    return String(value);
  }
}

function toast(message, isError = false) {
  const host = document.getElementById('toastContainer');
  if (!host) return;
  const node = document.createElement('div');
  node.className = 'toast' + (isError ? ' error' : '');
  node.innerHTML = `<i class="fa-solid ${isError ? 'fa-circle-xmark' : 'fa-circle-check'} toast-icon"></i><span class="toast-text">${message}</span>`;
  host.appendChild(node);
  setTimeout(() => node.classList.add('show'), 30);
  setTimeout(() => {
    node.classList.remove('show');
    setTimeout(() => node.remove(), 350);
  }, 3200);
}

function updateAlertBadge(count) {
  const badge = document.getElementById('alertBadge');
  if (!badge) return;
  if (count > 0) {
    badge.style.display = 'flex';
    badge.textContent = count;
  } else {
    badge.style.display = 'none';
  }
}

function statusBadge(status) {
  const map = {
    registered: 'blue',
    screening_completed: 'indigo',
    awaiting_assignment: 'orange',
    assigned: 'teal',
    active: 'green',
    completed: 'gray',
    terminated: 'red',
    cancelled: 'red',
    scheduled: 'blue',
    no_show: 'orange',
    paid: 'green',
    partial: 'indigo',
    pending: 'gray'
  };
  return `<span class="badge badge-${map[status] || 'gray'}">${String(status || 'unknown').replace(/_/g, ' ')}</span>`;
}

function riskBadge(level) {
  const map = { low: 'green', medium: 'orange', high: 'red' };
  return `<span class="badge badge-${map[level] || 'gray'}">${level || 'low'}</span>`;
}

function invStatusBadge(status) {
  const map = { pending: 'orange', paid: 'green', partial: 'indigo', overdue: 'red' };
  return `<span class="badge badge-${map[status] || 'gray'}">${String(status || 'pending').replace(/_/g, ' ')}</span>`;
}

function hashHue(seed) {
  const text = String(seed || '0');
  let hash = 0;
  for (let i = 0; i < text.length; i++) hash = ((hash << 5) - hash) + text.charCodeAt(i);
  return Math.abs(hash) % 360;
}

function appointmentPalette(seed) {
  const hue = hashHue(seed);
  return {
    base: `hsl(${hue} 72% 46%)`,
    dark: `hsl(${hue} 72% 34%)`,
    soft: `hsla(${hue}, 72%, 46%, .16)`,
    softStrong: `hsla(${hue}, 72%, 46%, .24)`
  };
}

function appointmentVisual(a) {
  const pal = appointmentPalette(a.therapist_id || a.therapist_name || 'appt');
  const status = String(a.status || '').toLowerCase();
  const scope = String(a.change_scope || '').toLowerCase();
  if (status === 'cancelled') {
    return { palette: { base: 'hsl(215 15% 58%)', dark: 'hsl(215 15% 40%)', soft: 'rgba(148,163,184,.14)', softStrong: 'rgba(148,163,184,.22)' }, cls: 'appt-cancelled', label: 'Cancelled' };
  }
  if (scope === 'temporary') {
    return { palette: { base: 'hsl(45 95% 52%)', dark: 'hsl(38 92% 40%)', soft: 'rgba(245,158,11,.14)', softStrong: 'rgba(245,158,11,.22)' }, cls: 'appt-temporary', label: 'Temporary change' };
  }
  if (scope === 'permanent') {
    return { palette: { base: 'hsl(45 90% 48%)', dark: 'hsl(40 86% 36%)', soft: 'rgba(255,191,0,.15)', softStrong: 'rgba(255,191,0,.25)' }, cls: '', label: 'Permanent change' };
  }
  return { palette: pal, cls: '', label: a.therapist_name || 'Therapist' };
}

function roomLabel(a) {
  return a?.room_name || a?.room_code || 'Room not set';
}

function isFinalAppointmentStatus(status) {
  return ['completed', 'cancelled', 'no_show'].includes(String(status || '').toLowerCase());
}

function formatRoomOption(room) {
  return `${room?.name || 'Room'}${room?.code ? ` (${room.code})` : ''}`;
}

function formatRoomChip(room, state = 'available') {
  const label = formatRoomOption(room);
  const color = room?.color || 'var(--navy)';
  const baseBg = state === 'busy' ? `${color}12` : `${color}18`;
  const cls = state === 'busy' ? 'busy' : state === 'selected' ? 'selected' : 'available';
  return `<span class="room-chip ${cls}" style="border-color:${color};color:${color};background:${baseBg}">${label}</span>`;
}

async function loadRooms() {
  try {
    const r = await apiFetch('/api/rooms');
    allRooms = await r.json();
    const roomSelect = document.getElementById('nc_book_room');
    if (roomSelect) {
      roomSelect.innerHTML = '<option value="">Auto-assign best available room</option>' + allRooms.map(room => `<option value="${room.id}">${formatRoomOption(room)}</option>`).join('');
    }
  } catch (e) {
    allRooms = [];
  }
}

async function loadNewClientBookingTherapists() {
  try {
    const r = await apiFetch('/api/users');
    const users = await r.json();
    const therapists = users.filter(u => u.role === 'therapist' && u.is_active);
    const sel = document.getElementById('nc_book_therapist');
    if (sel) {
      sel.innerHTML = '<option value="">Select therapist...</option>' + therapists.map(t => `<option value="${t.id}">${t.full_name}${t.specialization ? ` - ${t.specialization}` : ''}</option>`).join('');
    }
  } catch (e) {}
}

async function ncLoadRooms() {
  const roomSelect = document.getElementById('nc_book_room');
  if (!roomSelect) return;
  const date  = document.getElementById('nc_book_date')?.value;
  const start = document.getElementById('nc_book_start')?.value;
  const end   = document.getElementById('nc_book_end')?.value || start;
  if (!date || !start) {
    roomSelect.innerHTML = '<option value="">Auto-assign best available room</option>';
    return;
  }
  try {
    const params = new URLSearchParams({ start: `${date}T${start}:00`, end: `${date}T${end}:00` });
    const r = await apiFetch(`/api/rooms/available?${params.toString()}`);
    const data = await r.json();
    const available = data.rooms || [];
    const all = data.all_rooms || available;
    const availIds = new Set(available.map(rm => String(rm.id)));
    roomSelect.innerHTML = '<option value="">Auto-assign best available room</option>' +
      all.map(rm => {
        const ok = availIds.has(String(rm.id));
        return `<option value="${rm.id}" ${ok ? '' : 'disabled'}>${rm.name || `Room ${rm.id}`}${ok ? ' ✓' : ' — busy'}</option>`;
      }).join('');
  } catch(e) {
    roomSelect.innerHTML = '<option value="">Auto-assign best available room</option>';
  }
}

async function loadNewClientBookingRoomAvailability() {
  const roomSelect = document.getElementById('nc_book_room');
  if (!roomSelect) return;
  const date = document.getElementById('nc_book_date')?.value;
  const start = document.getElementById('nc_book_start')?.value;
  const end = document.getElementById('nc_book_end')?.value || start;
  if (!date || !start) {
    roomSelect.innerHTML = '<option value="">Choose a date and time first</option>';
    return;
  }
  try {
    const params = new URLSearchParams({ start: `${date}T${start}:00`, end: `${date}T${end}:00` });
    const r = await apiFetch(`/api/rooms/available?${params.toString()}`);
    const data = await r.json();
    const available = data.rooms || [];
    const availableIds = new Set(available.map(room => String(room.id)));
    roomSelect.innerHTML = '<option value="">Auto-assign best available room</option>' + allRooms.map(room => {
      const isAvail = availableIds.has(String(room.id));
      return `<option value="${room.id}" ${isAvail ? '' : 'disabled'}>${formatRoomOption(room)}${isAvail ? '' : ' - busy'}</option>`;
    }).join('');
  } catch (e) {}
}

async function loadBookingRoomAvailability() {
  const roomSelect = document.getElementById('bookRoom');
  const panel = document.getElementById('bookRoomChips');
  if (!roomSelect || !panel) return;
  const date = document.getElementById('bookDate')?.value;
  const start = document.getElementById('bookStart')?.value;
  const end = document.getElementById('bookEnd')?.value || start;
  if (!date || !start) {
    roomSelect.innerHTML = '<option value="">Choose a date and time first</option>';
    panel.innerHTML = '<span class="room-chip neutral">Pick a date and time to see room availability</span>';
    return;
  }
  try {
    const params = new URLSearchParams({ start: `${date}T${start}:00`, end: `${date}T${end}:00` });
    const r = await apiFetch(`/api/rooms/available?${params.toString()}`);
    const data = await r.json();
    const available = data.rooms || [];
    const availableIds = new Set(available.map(room => String(room.id)));
    roomSelect.innerHTML = '<option value="">Auto-assign best available room</option>' + allRooms.map(room => {
      const isAvail = availableIds.has(String(room.id));
      return `<option value="${room.id}" ${isAvail ? '' : 'disabled'}>${formatRoomOption(room)}${isAvail ? '' : ' - busy'}</option>`;
    }).join('');
    panel.innerHTML = available.length
      ? available.map(room => formatRoomChip(room, 'available')).join('')
      : '<span class="room-chip busy">No therapy room is free for this slot</span>';
  } catch (e) {
    roomSelect.innerHTML = '<option value="">Room availability unavailable</option>';
    panel.innerHTML = '<span class="room-chip neutral">Room availability could not be loaded</span>';
  }
}

async function loadRoomAvailability(startValue, endValue, selectedRoomId) {
  const panel = document.getElementById('apptRoomChips');
  const roomSelect = document.getElementById('apptEditorRoom');
  if (!panel || !roomSelect) return;
  if (!startValue) {
    panel.innerHTML = '<span class="room-chip neutral">Pick a date and time to check availability</span>';
    roomSelect.innerHTML = '<option value="">Select a room after choosing a time</option>';
    return;
  }
  try {
    const params = new URLSearchParams({ start: startValue, end: endValue || startValue });
    const apptId = document.getElementById('apptEditorId')?.value;
    if (apptId) params.set('appointment_id', apptId);
    const r = await apiFetch(`/api/rooms/available?${params.toString()}`);
    const data = await r.json();
    const available = data.rooms || [];
    const availableIds = new Set(available.map(room => String(room.id)));
    roomSelect.innerHTML = '<option value="">Auto-assign best available room</option>' + allRooms.map(room => {
      const isAvail = availableIds.has(String(room.id));
      const isSelected = String(selectedRoomId || roomSelect.value) === String(room.id);
      return `<option value="${room.id}" ${isSelected ? 'selected' : ''} ${isAvail ? '' : 'disabled'}>${formatRoomOption(room)}${isAvail ? '' : ' - busy'}</option>`;
    }).join('');
    panel.innerHTML = available.length
      ? available.map(room => formatRoomChip(room, String(selectedRoomId || roomSelect.value) === String(room.id) ? 'selected' : 'available')).join('')
      : '<span class="room-chip busy">No rooms are available for this slot</span>';
  } catch (e) {
    panel.innerHTML = '<span class="room-chip neutral">Room availability could not be loaded</span>';
  }
}

function refreshAppointmentRoomAvailability() {
  const startValue = document.getElementById('apptEditorDateTime')?.value;
  const endValue = document.getElementById('apptEditorEndTime')?.value || startValue;
  const roomSelect = document.getElementById('apptEditorRoom');
  loadRoomAvailability(startValue, endValue, roomSelect?.value);
}

function setApptEditorMode(mode) {
  const scope = mode === 'permanent' ? 'permanent' : 'temporary';
  document.getElementById('apptEditorScope').value = scope;
  document.getElementById('apptEditorStatus').value = mode === 'cancelled' ? 'cancelled' : (mode === 'no_show' ? 'no_show' : 'scheduled');
  document.getElementById('apptModeTemp')?.classList.toggle('active', mode === 'temporary');
  document.getElementById('apptModePerm')?.classList.toggle('active', mode === 'permanent');
  document.getElementById('apptModeCancel')?.classList.toggle('active', mode === 'cancelled');
  document.getElementById('apptModeNoShow')?.classList.toggle('active', mode === 'no_show');
  const saveBtn = document.getElementById('apptEditorSaveBtn');
  const note = document.getElementById('apptEditorNote');
  const timeGroup = document.querySelector('.appt-editor-time-group');
  if (timeGroup) timeGroup.classList.toggle('appt-editor-hidden', mode === 'cancelled' || mode === 'no_show');
  if (mode === 'cancelled') {
    if (note) note.innerHTML = '<strong>Cancellation:</strong> add the reason so reception and Telegram get the same update.';
    if (saveBtn) {
      saveBtn.textContent = 'Cancel Session';
      saveBtn.className = 'btn btn-danger appt-editor-save';
    }
  } else if (mode === 'no_show') {
    if (note) note.innerHTML = '<strong>No-show:</strong> record the reason and notify the team without changing the date.';
    if (saveBtn) {
      saveBtn.textContent = 'Mark No-show';
      saveBtn.className = 'btn btn-warning appt-editor-save';
    }
  } else {
    if (note) note.innerHTML = mode === 'permanent'
      ? '<strong>Permanent change:</strong> updates this session and the recurring pattern.'
      : '<strong>Temporary change:</strong> updates this appointment only.';
    if (saveBtn) {
      saveBtn.textContent = mode === 'permanent' ? 'Save Permanent Change' : 'Save Temporary Change';
      saveBtn.className = 'btn btn-danger appt-editor-save';
    }
  }
}

function openAppointmentEditor(apptId, mode = 'temporary') {
  const appt = allAppointments.find(a => String(a.id) === String(apptId));
  if (!appt) {
    toast('Appointment not found', true);
    return;
  }
  document.getElementById('apptEditorId').value = appt.id;
  document.getElementById('apptEditorDateTime').value = appt.start_time ? new Date(appt.start_time).toISOString().slice(0, 16) : '';
  document.getElementById('apptEditorEndTime').value = appt.end_time ? new Date(appt.end_time).toISOString().slice(0, 16) : '';
  document.getElementById('apptEditorReason').value = appt.change_reason || appt.cancel_reason || '';
  document.getElementById('apptEditorRoom').value = appt.room_id || '';
  document.getElementById('apptEditorOverlay').classList.add('active');
  document.getElementById('apptEditorModal').classList.add('active');
  vcInit();
  setTimeout(vcRender, 100);
  setApptEditorMode(mode);
  document.getElementById('apptEditorTitle').textContent = `${appt.client_name || 'Session'}${appt.client_code ? ' - ' + appt.client_code : ''}`;
  document.getElementById('apptEditorSubtitle').textContent = `${formatDate(appt.start_time)} ${formatApptTime(appt.start_time)} - ${appt.location || 'Location not set'} - ${roomLabel(appt)} - ${appt.therapist_name || 'Therapist'}`;
  refreshAppointmentRoomAvailability();
}

function closeAppointmentEditor() {
  document.getElementById('apptEditorOverlay').classList.remove('active');
  document.getElementById('apptEditorModal').classList.remove('active');
}

async function saveAppointmentEditor() {
  const id = document.getElementById('apptEditorId').value;
  const scope = document.getElementById('apptEditorScope').value || 'temporary';
  const status = document.getElementById('apptEditorStatus').value || 'scheduled';
  const reason = document.getElementById('apptEditorReason').value.trim();
  const roomId = document.getElementById('apptEditorRoom')?.value || '';
  if (!id) {
    toast('No appointment selected', true);
    return;
  }
  const body = { reason };
  if (status === 'cancelled') {
    if (!reason) {
      toast('Please add a cancellation reason', true);
      return;
    }
    body.status = 'cancelled';
    body.cancel_reason = reason;
    body.action = 'cancelled';
  } else if (status === 'no_show') {
    if (!reason) {
      toast('Please add a no-show reason', true);
      return;
    }
    body.status = 'no_show';
    body.reason = reason;
    body.action = 'no_show';
  } else {
    const dt = document.getElementById('apptEditorDateTime').value;
    if (!dt) {
      toast('Please choose a new date and time', true);
      return;
    }
    body.start_time = new Date(dt).toISOString();
    const end = document.getElementById('apptEditorEndTime').value;
    if (end) body.end_time = new Date(end).toISOString();
    if (roomId) body.room_id = roomId;
    body.change_reason = reason;
    body.change_scope = scope;
    body.action = 'changed';
  }
  const r = await apiFetch(`/api/appointments/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const d = await r.json();
  if (d.success) {
    closeAppointmentEditor();
    toast(status === 'cancelled' ? 'Appointment cancelled' : (scope === 'permanent' ? 'Permanent change saved' : 'Temporary change saved'));
    loadTodaySchedule();
    loadAppointments();
    renderCalendar();
  } else {
    toast(d.error || 'Update failed', true);
  }
}

async function loadAppointments() {
  const startEl = document.getElementById('apptFilterStart');
  const endEl = document.getElementById('apptFilterEnd');
  if (startEl && !startEl.value) {
    const today = new Date();
    const future = new Date(today);
    future.setMonth(future.getMonth() + 6);
    startEl.value = today.toISOString().split('T')[0];
    if (endEl && !endEl.value) endEl.value = future.toISOString().split('T')[0];
  }
  const start = startEl?.value;
  const end = endEl?.value;
  const status = document.getElementById('apptFilterStatus')?.value;
  const params = new URLSearchParams();
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  try {
    const r = await apiFetch(`/api/appointments?${params.toString()}`);
    const data = await r.json();
    const unique = [];
    const seen = new Set();
    for (const appt of data) {
      const key = String(appt.id || `${appt.client_id}-${appt.start_time}`);
      if (seen.has(key)) continue;
      seen.add(key);
      unique.push(appt);
    }
    allAppointments = unique;
    const filtered = (status ? unique.filter(a => a.status === status) : unique).sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
    const tb = document.getElementById('apptTableBody');
    if (!tb) return;
    if (!filtered.length) {
      tb.innerHTML = `<tr><td colspan="7" style="text-align:center;padding:30px;color:var(--text-muted)">No appointments found</td></tr>`;
      return;
    }
    tb.innerHTML = filtered.map(a => {
      const visual = appointmentVisual(a);
      return `
        <tr style="box-shadow:inset 4px 0 0 ${visual.palette.base}">
          <td style="border-left:4px solid ${visual.palette.base}">
            <div style="font-weight:700">${formatDate(a.start_time)}</div>
            <div style="font-size:11px;color:var(--text-muted)">${formatApptTime(a.start_time)}</div>
          </td>
          <td>
            <button class="btn btn-ghost btn-sm" style="padding:0;background:none;border:none;color:var(--navy);font-weight:800" onclick="openClientDrawer(${a.client_id});event.stopPropagation()">${a.client_name || '-'}</button>
            <div style="font-size:11px;color:var(--text-muted);margin-top:3px">${a.client_code || ''}</div>
          </td>
          <td><span class="appt-color-chip" style="background:${visual.palette.base}">${a.therapist_name || '-'}</span></td>
          <td>
            <span class="badge badge-blue">${a.type}</span>
            ${a.change_scope ? ` <span class="badge badge-${a.change_scope === 'permanent' ? 'gold' : 'orange'}">${a.change_scope}</span>` : ''}
            <div style="margin-top:4px"><span class="badge badge-gray">${roomLabel(a)}</span></div>
          </td>
          <td>${statusBadge(a.status)}</td>
          <td>${a.location || '-'}</td>
          <td style="display:flex;gap:4px;flex-wrap:wrap">
            ${isFinalAppointmentStatus(a.status)
              ? `<span style="font-size:12px;color:var(--text-muted);font-weight:600;padding:6px 0">Finalized</span>`
              : `<button class="btn btn-sm btn-outline" onclick="changeAppt(${a.id},'temporary')" title="Temporary change"><i class="fa-solid fa-clock-rotate-left"></i></button>
                 <button class="btn btn-sm btn-gold" onclick="changeAppt(${a.id},'permanent')" title="Permanent change"><i class="fa-solid fa-calendar-days"></i></button>
                 <button class="btn btn-sm btn-warning" onclick="changeAppt(${a.id},'no_show')" title="No-show"><i class="fa-solid fa-user-slash"></i></button>
                 <button class="btn btn-sm btn-danger" onclick="changeAppt(${a.id},'cancelled')" title="Cancel"><i class="fa-solid fa-ban"></i></button>`}
          </td>
        </tr>`;
    }).join('');
  } catch (e) {}
}

async function updateApptStatus(id, status) {
  if (status === 'cancelled') {
    openAppointmentEditor(id, 'cancelled');
    return;
  }
  await apiFetch(`/api/appointments/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, action: status })
  });
  toast('Appointment updated');
  loadTodaySchedule();
  loadAppointments();
  renderCalendar();
}

function changeAppt(id, scope = 'temporary') {
  openAppointmentEditor(id, scope);
}

function openBookModal() {
  const overlay = document.getElementById('bookOverlay');
  const modal = document.getElementById('bookModal');
  if (overlay) overlay.classList.add('active');
  if (modal) modal.classList.add('active');
  bookClientSearch = '';
  bookVcView = 'day';
  const today = new Date();
  const max = new Date(today);
  max.setMonth(max.getMonth() + 6);
  const bookDate = document.getElementById('bookDate');
  if (bookDate) {
    bookDate.value = today.toISOString().split('T')[0];
    bookDate.min = today.toISOString().split('T')[0];
    bookDate.max = max.toISOString().split('T')[0];
  }
  const hiddenClient = document.getElementById('bookClient');
  if (hiddenClient) hiddenClient.value = '';
  const searchEl = document.getElementById('bookClientSearch');
  if (searchEl) searchEl.value = '';
  const selectedEl = document.getElementById('bookClientSelected');
  if (selectedEl) {
    selectedEl.textContent = '';
    selectedEl.style.display = 'none';
  }
  const therapistSel = document.getElementById('bookTherapist');
  apiFetch('/api/users').then(r => r.json()).then(users => {
    const therapists = users.filter(u => u.role === 'therapist' && u.is_active);
    if (therapistSel) therapistSel.innerHTML = '<option value="">Select therapist...</option>' + therapists.map(t => `<option value="${t.id}">${t.full_name}</option>`).join('');
  }).catch(() => {});
  bookVcInit();
  loadRooms().then(() => loadBookingRoomAvailability());
  ['bookDate', 'bookStart', 'bookEnd'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.onchange = loadBookingRoomAvailability;
  });
  renderBookClientPicker();
}

function closeBookModal() {
  document.getElementById('bookOverlay')?.classList.remove('active');
  document.getElementById('bookModal')?.classList.remove('active');
}

async function bookAppointment() {
  const cid = document.getElementById('bookClient').value;
  const tid = document.getElementById('bookTherapist').value;
  const date = document.getElementById('bookDate').value || document.getElementById('bookVcDateTime').value?.slice?.(0, 10);
  const start = document.getElementById('bookStart').value || document.getElementById('bookVcDateTime').value?.slice?.(11, 16);
  const end = document.getElementById('bookEnd').value || document.getElementById('bookVcEndTime').value?.slice?.(11, 16);
  if (!cid || !tid || !date || !start) {
    toast('Please fill all required fields', true);
    return;
  }
  const body = {
    client_id: cid,
    therapist_id: tid,
    start_time: `${date}T${start}:00`,
    end_time: `${date}T${end || start}:00`,
    type: document.getElementById('bookType').value,
    location: document.getElementById('bookLocation').value,
    notes: document.getElementById('bookNotes').value,
    is_recurring: document.getElementById('bookRecurring').checked
  };
  const roomId = document.getElementById('bookRoom')?.value || '';
  if (roomId) body.room_id = roomId;
  const r = await apiFetch('/api/appointments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const d = await r.json();
  if (d.success) {
    closeBookModal();
    toast('Appointment booked!');
    loadTodaySchedule();
    loadAppointments();
    renderCalendar();
  } else {
    toast(d.error || 'Booking failed', true);
  }
}

function switchFinTab(tab) {
  const invoices = document.getElementById('finInvoices');
  const revenue = document.getElementById('finRevenue');
  if (invoices) invoices.style.display = tab === 'invoices' ? 'block' : 'none';
  if (revenue) revenue.style.display = tab === 'revenue' ? 'block' : 'none';
}

async function loadInvoices() {
  try {
    const r = await apiFetch('/api/invoices');
    allInvoices = await r.json();
    const tb = document.getElementById('invoiceTableBody');
    if (!tb) return;
    if (!allInvoices.length) {
      tb.innerHTML = `<tr><td colspan="6" style="text-align:center;padding:30px;color:var(--text-muted)">No invoices found</td></tr>`;
      return;
    }
    tb.innerHTML = allInvoices.map(i => `
      <tr>
        <td><strong>${i.client_name || '-'}</strong><br><span style="font-size:11px;color:var(--text-muted)">${i.client_code || ''}</span></td>
        <td>${i.service_name || '-'}</td>
        <td style="font-weight:700">ETB ${(i.amount || 0).toLocaleString()}</td>
        <td>${invStatusBadge(i.status)}</td>
        <td style="font-size:12px;color:var(--text-muted)">${formatDate(i.due_date)}</td>
        <td>${i.status === 'pending'
          ? `<button class="btn btn-sm btn-success" onclick="openPaymentFor(${i.id},${i.client_id})"><i class="fa-solid fa-credit-card"></i>Pay</button>`
          : '<span style="color:var(--text-muted);font-size:12px">Settled</span>'}</td>
      </tr>`).join('');
  } catch (e) {}
}

function openInvoiceModal() {
  document.getElementById('invoiceOverlay')?.classList.add('active');
  document.getElementById('invoiceModal')?.classList.add('active');
  const sel = document.getElementById('invClient');
  if (sel) sel.innerHTML = '<option value="">Select client...</option>' + allClients.map(c => `<option value="${c.id}">${c.full_name} (${c.client_code})</option>`).join('');
  apiFetch('/api/services').then(r => r.json()).then(services => {
    const svc = document.getElementById('invService');
    if (!svc) return;
    svc.innerHTML = '<option value="">Select service...</option>' + services.map(s => `<option value="${s.id}" data-price="${s.price}">${s.name} (ETB ${s.price})</option>`).join('');
    svc.onchange = function () {
      const opt = this.options[this.selectedIndex];
      if (opt?.dataset?.price) document.getElementById('invAmount').value = opt.dataset.price;
    };
  }).catch(() => {});
}

function closeInvoiceModal() {
  document.getElementById('invoiceOverlay')?.classList.remove('active');
  document.getElementById('invoiceModal')?.classList.remove('active');
}

async function createInvoice() {
  const body = {
    client_id: document.getElementById('invClient').value,
    service_id: document.getElementById('invService').value,
    amount: document.getElementById('invAmount').value,
    notes: document.getElementById('invNotes').value
  };
  const r = await apiFetch('/api/invoices', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const d = await r.json();
  if (d.success) {
    closeInvoiceModal();
    toast('Invoice created!');
    loadInvoices();
  } else {
    toast(d.error || 'Failed', true);
  }
}

function openPaymentFor(invoiceId, clientId) {
  document.getElementById('payInvoiceId').value = invoiceId;
  document.getElementById('payClientId').value = clientId;
  document.getElementById('paymentOverlay')?.classList.add('active');
  document.getElementById('paymentModal')?.classList.add('active');
}

function openInvoiceForClient(cid) {
  closeClientDrawer();
  showSection('finance');
  setTimeout(() => openInvoiceModal(), 300);
}

function closePaymentModal() {
  document.getElementById('paymentOverlay')?.classList.remove('active');
  document.getElementById('paymentModal')?.classList.remove('active');
}

async function submitPayment() {
  const body = {
    invoice_id: document.getElementById('payInvoiceId').value,
    client_id: document.getElementById('payClientId').value,
    amount_paid: document.getElementById('payAmount').value,
    payment_method: document.getElementById('payMethod').value,
    invoice_status: document.getElementById('payStatus').value,
    notes: document.getElementById('payNotes').value
  };
  const r = await apiFetch('/api/payments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const d = await r.json();
  if (d.success) {
    closePaymentModal();
    toast('Payment recorded!');
    loadInvoices();
  } else {
    toast(d.error || 'Failed', true);
  }
}

function parseNotificationBody(message) {
  const lines = String(message?.body || '').split(/\r?\n/);
  const fields = {};
  for (const line of lines) {
    const match = line.match(/^([^:]+):\s*(.*)$/);
    if (match) fields[match[1].trim().toLowerCase()] = match[2].trim();
  }
  return { lines, fields };
}

function notificationTone(subject = '') {
  const s = String(subject).toLowerCase();
  if (s.includes('completed')) return { icon: 'fa-circle-check', color: 'var(--success)', bg: 'rgba(16,185,129,.1)', badge: 'badge-green', label: 'Completed' };
  if (s.includes('cancel')) return { icon: 'fa-ban', color: 'var(--danger)', bg: 'rgba(239,68,68,.1)', badge: 'badge-red', label: 'Cancelled' };
  if (s.includes('resched') || s.includes('change')) return { icon: 'fa-arrows-rotate', color: 'var(--info)', bg: 'rgba(59,130,246,.1)', badge: 'badge-blue', label: 'Rescheduled' };
  if (s.includes('no-show')) return { icon: 'fa-triangle-exclamation', color: 'var(--warning)', bg: 'rgba(245,158,11,.12)', badge: 'badge-orange', label: 'No Show' };
  if (s.includes('pending')) return { icon: 'fa-clock', color: 'var(--text-muted)', bg: 'rgba(100,116,139,.1)', badge: 'badge-gray', label: 'Pending' };
  return { icon: 'fa-bell', color: 'var(--navy)', bg: 'rgba(4,48,105,.08)', badge: 'badge-indigo', label: 'Update' };
}

function notificationCard(message) {
  const parsed = parseNotificationBody(message);
  const tone = notificationTone(message.subject || '');
  const f = parsed.fields;
  const bodyDetails = [
    f['date/time'] || f['new date/time'] || f['previous date/time'] || '',
    f['end time'] || f['new end time'] || '',
    f['reason'] || '',
    f['scope'] || ''
  ].filter(Boolean).join(' - ');
  const rows = [
    ['Client code', f['client code'] || '-'],
    ['Therapist', f['therapist'] || '-'],
    ['Room', f['room'] || '-'],
    ['Appointment date', f['date/time'] || f['new date/time'] || '-'],
    ['Time', f['date/time'] || f['new date/time'] || '-'],
    ['Action performed', message.subject || 'Notification'],
    ['Reason', f['reason'] || 'Not provided'],
    ['Timestamp', formatDate(message.sent_at)]
  ];
  return `
    <div class="notify-card">
      <div class="notify-head">
        <div class="notify-icon" style="background:${tone.bg};color:${tone.color}">
          <i class="fa-solid ${tone.icon}"></i>
        </div>
        <div class="notify-main">
          <div class="notify-title-row">
            <div class="notify-title">${message.subject || 'Notification'}</div>
            <div class="notify-time">${formatDate(message.sent_at)}</div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
            <span class="badge ${tone.badge}">${tone.label}</span>
            <span class="badge badge-gray">${message.sender_name || 'System'}</span>
          </div>
          ${bodyDetails ? `<div class="notify-body" style="margin-top:10px">${bodyDetails}</div>` : ''}
        </div>
      </div>
      <div class="notify-grid">
        ${rows.map(([label, value]) => `
          <div class="notify-field">
            <div class="notify-field-label">${label}</div>
            <div class="notify-field-value">${value || '-'}</div>
          </div>`).join('')}
      </div>
      <div class="notify-footer">
        ${f['current status'] ? `<span class="badge badge-indigo">Current status: ${f['current status']}</span>` : ''}
        ${f['scope'] ? `<span class="badge badge-gold">${f['scope']}</span>` : ''}
        ${f['previous date/time'] ? `<span class="badge badge-gray">Previous slot recorded</span>` : ''}
      </div>
    </div>`;
}

async function loadMessages() {
  try {
    const r = await apiFetch('/api/messages');
    const msgs = await r.json();
    const list = document.getElementById('msgList');
    if (list) list.innerHTML = msgs.map(m => notificationCard(m)).join('') || '<p style="text-align:center;color:var(--text-muted);padding:20px">No messages</p>';
    const usersRes = await apiFetch('/api/users');
    const users = await usersRes.json();
    const to = document.getElementById('msgTo');
    if (to) to.innerHTML = '<option value="">Select recipient...</option>' + users.map(u => `<option value="${u.id}">${u.full_name} (${u.role})</option>`).join('');
  } catch (e) {}
}

function showCompose() {}

async function sendMsg() {
  const body = {
    recipient_id: document.getElementById('msgTo').value,
    subject: document.getElementById('msgSubject').value,
    body: document.getElementById('msgBody').value
  };
  if (!body.recipient_id || !body.subject) {
    toast('Fill all fields', true);
    return;
  }
  const r = await apiFetch('/api/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const d = await r.json();
  if (d.success) {
    toast('Message sent!');
    document.getElementById('msgSubject').value = '';
    document.getElementById('msgBody').value = '';
    loadMessages();
  } else {
    toast(d.error || 'Failed', true);
  }
}

let currentStep = 1;

function nextStep(step) {
  if (step > 1 && !validateStep(currentStep)) return;
  currentStep = step;
  document.querySelectorAll('.step-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('step'+step).classList.add('active');

  [1,2,3].forEach(i => {
    const dot = document.getElementById('step'+i+'dot');
    dot.className = 'step-dot' + (i < step ? ' done' : i === step ? ' active' : '');
    if (i < 3) document.getElementById('line'+i).className = 'step-line' + (i < step ? ' done' : '');
  });

  if (step === 2) {
    loadNewClientBookingTherapists();
    ncVcInit();
  }
  if (step === 3) buildReview();
}

function validateStep(step) {
  if (step === 1) {
    const required = ['nc_name','nc_dob','nc_gender','nc_phone'];
    for (const id of required) {
      if (!document.getElementById(id)?.value.trim()) {
        toast('Please fill Name, Date of Birth, Gender, and Phone', true);
        return false;
      }
    }
  }
  if (step === 2) {
    if (document.getElementById('nc_book_now')?.checked) {
      if (!document.getElementById('nc_book_therapist')?.value) {
        toast('Please select a therapist for the appointment', true);
        return false;
      }
      if (!document.getElementById('nc_book_date')?.value) {
        toast('Please click a time slot on the calendar to select date & time', true);
        return false;
      }
    }
  }
  return true;
}

function buildReview() {
  const rows = [
    ['Full Name', document.getElementById('nc_name')?.value || '-'],
    ['Date of Birth', document.getElementById('nc_dob')?.value || '-'],
    ['Gender', document.getElementById('nc_gender')?.value || '-'],
    ['Phone', document.getElementById('nc_phone')?.value || '-'],
    ['Presenting Concerns', document.getElementById('nc_concerns')?.value || '-'],
  ];
  document.getElementById('reviewContent').innerHTML = rows.map(([l,v])=>
    `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
      <span style="font-size:12px;font-weight:700;color:var(--text-muted)">${l}</span>
      <span style="font-size:13px;font-weight:600;max-width:60%;text-align:right;word-break:break-word">${v}</span>
    </div>`).join('');

  const bookNow = document.getElementById('nc_book_now')?.checked;
  const recurSel = document.getElementById('nc_recur');
  const recurLabel = recurSel?.options[recurSel.selectedIndex]?.text || 'Does not repeat';
  const startDt = document.getElementById('nc_book_date')?.value;
  const startTm = document.getElementById('nc_book_start')?.value;
  const endTm   = document.getElementById('nc_book_end')?.value;
  const appt = {
    therapist: document.getElementById('nc_book_therapist')?.selectedOptions?.[0]?.textContent || 'Not selected',
    date: startDt || 'Not selected',
    time: (startTm && endTm) ? `${startTm} – ${endTm}` : 'Not selected',
    location: document.getElementById('nc_book_location')?.value || 'In-Person',
    recur: recurLabel,
    notes: document.getElementById('nc_book_notes')?.value || 'None'
  };
  document.getElementById('reviewAppointmentContent').innerHTML = `
    <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:10px">
      <div>
        <div style="font-size:11px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--text-muted)">First Appointment</div>
        <div style="font-size:15px;font-weight:800;color:var(--navy);margin-top:2px">Booking Summary</div>
      </div>
      <span class="badge badge-${bookNow ? 'green' : 'gray'}">${bookNow ? 'Will be booked' : 'Not scheduled'}</span>
    </div>
    ${bookNow ? `<div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;font-size:13px">
      <div><strong style="color:var(--navy)">Therapist:</strong> ${appt.therapist}</div>
      <div><strong style="color:var(--navy)">Location:</strong> ${appt.location}</div>
      <div><strong style="color:var(--navy)">Date:</strong> ${appt.date}</div>
      <div><strong style="color:var(--navy)">Time:</strong> ${appt.time}</div>
      <div style="grid-column:1/-1"><strong style="color:var(--navy)">Schedule:</strong> ${appt.recur}</div>
      <div style="grid-column:1/-1"><strong style="color:var(--navy)">Notes:</strong> ${appt.notes}</div>
    </div>` : '<p style="color:var(--text-muted);font-size:13px;margin:0">No appointment will be created.</p>'}`;
}

async function registerClient() {
  const btn = document.getElementById('registerBtn');
  btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Registering...';
  btn.disabled = true;

  const concerns = document.getElementById('nc_concerns')?.value || '';
  const extraNotes = document.getElementById('nc_notes')?.value || '';
  const notesStr = [
    concerns ? `Presenting Concerns:\n${concerns}` : '',
    extraNotes ? `Notes:\n${extraNotes}` : ''
  ].filter(Boolean).join('\n\n');

  const therapistId = document.getElementById('nc_book_therapist')?.value || null;

  const body = {
    full_name: document.getElementById('nc_name')?.value || '',
    date_of_birth: document.getElementById('nc_dob')?.value || '',
    gender: document.getElementById('nc_gender')?.value || '',
    phone: document.getElementById('nc_phone')?.value || '',
    email: '', address: '',
    emergency_contact_name: '', emergency_contact_phone: '',
    language_pref: 'English',
    therapist_gender_pref: document.getElementById('nc_genderpref')?.value || 'No Preference',
    intake_source: 'Walk-in',
    notes: notesStr,
    assigned_therapist_id: therapistId ? parseInt(therapistId) : null
  };

  try {
    const r = await apiFetch('/api/clients', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data = await r.json();

    if (!data.success) {
      toast(data.error || 'Registration failed', true);
      btn.innerHTML = '<i class="fa-solid fa-user-check"></i> Register Client';
      btn.disabled = false;
      return;
    }

    if (document.getElementById('nc_book_now')?.checked) {
      const date = document.getElementById('nc_book_date')?.value;
      const start = document.getElementById('nc_book_start')?.value;
      const end = document.getElementById('nc_book_end')?.value;
      const location = document.getElementById('nc_book_location')?.value || 'In-Person';
      const notes = document.getElementById('nc_book_notes')?.value || '';
      const recurVal = document.getElementById('nc_recur')?.value || 'none';

      if (therapistId && date && start) {
        const dates = [date];
        if (recurVal !== 'none') {
          const parts = recurVal.split('_');
          const interval = parts[0] === 'biweekly' ? 14 : 7;
          const count = parseInt(parts[1]) || 4;
          const base = new Date(date);
          for (let i = 1; i < count; i++) {
            const next = new Date(base);
            next.setDate(base.getDate() + interval * i);
            dates.push(next.toISOString().slice(0,10));
          }
        }
        for (const d of dates) {
          try {
            await apiFetch('/api/appointments', {
              method: 'POST',
              headers: {'Content-Type':'application/json'},
              body: JSON.stringify({
                client_id: data.client_id,
                therapist_id: parseInt(therapistId),
                start_time: `${d}T${start}:00`,
                end_time: `${d}T${end || start}:00`,
                type: 'individual',
                location: location,
                notes: notes,
                room_id: document.getElementById('nc_book_room')?.value || ''
              })
            });
          } catch(e) { console.error('Appt error:', e); }
        }
      }
    }

    document.querySelectorAll('.step-panel').forEach(p => p.classList.remove('active'));
    document.getElementById('step4').classList.add('active');
    document.getElementById('newClientCode').textContent = data.client_code;
    // Show/hide assign therapist button based on whether one was already chosen
    const assignBtn = document.getElementById('step4AssignBtn');
    const assignMsg = document.getElementById('step4AssignMsg');
    if (therapistId) {
      if (assignBtn) assignBtn.style.display = 'none';
      if (assignMsg) assignMsg.style.display = 'block';
    } else {
      if (assignBtn) assignBtn.style.display = '';
      if (assignMsg) assignMsg.style.display = 'none';
    }
    await loadAllClients();
    toast('Client registered successfully!');
  } catch(e) {
    console.error(e);
    toast('Registration failed', true);
  }

  btn.innerHTML = '<i class="fa-solid fa-user-check"></i> Register Client';
  btn.disabled = false;
}

function resetClientForm() {
  ['nc_name','nc_dob','nc_phone','nc_email','nc_concerns','nc_notes','nc_book_notes'].forEach(id => { const el=document.getElementById(id); if(el) el.value=''; });
  ['nc_book_therapist','nc_book_location'].forEach(id => { const el=document.getElementById(id); if(el) el.value=''; });
  const bookNow = document.getElementById('nc_book_now'); if(bookNow) bookNow.checked=false;
  const bookFields = document.getElementById('ncBookFields'); if(bookFields) bookFields.style.display='none';
  const lbl = document.getElementById('ncVcSelectedLabel'); if(lbl) lbl.style.display='none';
  ncVcAppointments = [];
  ncVcSelectedStart = null;
  ncVcSelectedEnd = null;
  document.getElementById('nc_book_date').value = '';
  document.getElementById('nc_book_start').value = '';
  document.getElementById('nc_book_end').value = '';
  ncVcRender();
  currentStep = 1;
  nextStep(1);
}

// ─── New Client Mini Visual Calendar (ncVc) ───
let ncVcCurrentDate = new Date();
let ncVcView = 'week';
let ncVcAppointments = [];
let ncVcSelectedStart = null;
let ncVcSelectedEnd = null;

function ncVcInit() {
  ncVcCurrentDate = new Date();
  ncVcSelectedStart = null;
  ncVcSelectedEnd = null;
  const lbl = document.getElementById('ncVcSelectedLabel');
  if (lbl) lbl.style.display = 'none';
  document.getElementById('nc_book_date').value = '';
  document.getElementById('nc_book_start').value = '';
  document.getElementById('nc_book_end').value = '';
  ncVcFetchData();
}

async function ncVcFetchData() {
  const therapistId = document.getElementById('nc_book_therapist')?.value;
  try {
    const r = await apiFetch('/api/appointments');
    const all = await r.json();
    ncVcAppointments = therapistId ? all.filter(a => String(a.therapist_id) === String(therapistId)) : all;
  } catch(e) {
    ncVcAppointments = [];
  }
  ncVcRender();
}

function ncVcNav(dir) {
  if (ncVcView === 'day') ncVcCurrentDate.setDate(ncVcCurrentDate.getDate() + dir);
  else ncVcCurrentDate.setDate(ncVcCurrentDate.getDate() + (dir * 7));
  ncVcSelectedStart = null;
  ncVcSelectedEnd = null;
  const lbl = document.getElementById('ncVcSelectedLabel');
  if (lbl) lbl.style.display = 'none';
  ncVcFetchData();
}

function ncVcSetView(view) {
  ncVcView = view;
  document.getElementById('ncVcBtnDay')?.classList.toggle('active', view === 'day');
  document.getElementById('ncVcBtnWeek')?.classList.toggle('active', view === 'week');
  ncVcRender();
}

function ncVcGetWeekDays(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  const days = [];
  for (let i = 0; i < 7; i++) {
    const nd = new Date(monday);
    nd.setDate(monday.getDate() + i);
    days.push(nd);
  }
  return days;
}

function ncVcRender() {
  const grid = document.getElementById('ncVcGrid');
  const label = document.getElementById('ncVcDateLabel');
  if (!grid || !label) return;
  const days = ncVcView === 'day' ? [ncVcCurrentDate] : ncVcGetWeekDays(ncVcCurrentDate);
  label.textContent = ncVcView === 'day'
    ? days[0].toLocaleDateString('en-US', {weekday:'long', month:'long', day:'numeric', year:'numeric'})
    : `${days[0].toLocaleDateString('en-US', {month:'short', day:'numeric'})} – ${days[6].toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'})}`;
  let html = `<div class="vc-time-col"><div class="vc-day-header">Time</div>`;
  for (let h = 8; h <= 19; h++) {
    const hour = h > 12 ? h - 12 : h;
    html += `<div class="vc-time-slot">${hour} ${h >= 12 ? 'PM' : 'AM'}</div>`;
  }
  html += `</div><div class="vc-days">`;
  const today = new Date();
  days.forEach(day => {
    const isToday = day.toDateString() === today.toDateString();
    html += `<div class="vc-day-col"><div class="vc-day-header" style="${isToday ? 'color:var(--primary);font-weight:800' : ''}">${day.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'})}</div>`;
    for (let h = 8; h <= 19; h++) {
      const slotStart = new Date(day);
      slotStart.setHours(h, 0, 0, 0);
      const slotEnd = new Date(day);
      slotEnd.setHours(h + 1, 0, 0, 0);
      const slotStartStr = slotStart.toISOString();
      const slotEndStr = slotEnd.toISOString();
      const isPast = slotStart < today;
      const isBusy = ncVcAppointments.some(a => {
        if (['cancelled','no_show','terminated'].includes(String(a.status||'').toLowerCase())) return false;
        const aStart = new Date(a.start_time);
        const aEnd = new Date(a.end_time || a.start_time);
        return aStart < slotEnd && aEnd > slotStart;
      });
      let cls = 'vc-slot';
      if (isPast) cls += ' busy';
      else if (isBusy) cls += ' busy';
      else cls += ' available';
      if (ncVcSelectedStart === slotStartStr) cls += ' selected';
      const onclick = (!isPast && !isBusy) ? `onclick="ncVcSlotClick(this)"` : '';
      html += `<div class="${cls}" data-start="${slotStartStr}" data-end="${slotEndStr}" ${onclick}></div>`;
    }
    html += `</div>`;
  });
  html += `</div>`;
  grid.innerHTML = html;
}

function ncVcSlotClick(el) {
  const start = el.dataset.start;
  const end   = el.dataset.end;
  ncVcSelectedStart = start;
  ncVcSelectedEnd   = end;
  const dateHidden  = document.getElementById('nc_book_date');
  const startHidden = document.getElementById('nc_book_start');
  const endHidden   = document.getElementById('nc_book_end');
  if (dateHidden)  dateHidden.value  = start.slice(0, 10);
  if (startHidden) startHidden.value = start.slice(11, 16);
  if (endHidden)   endHidden.value   = end.slice(11, 16);
  const lbl = document.getElementById('ncVcSelectedLabel');
  if (lbl) {
    const startFmt = new Date(start).toLocaleString('en-US', {weekday:'short', month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'});
    const endFmt   = new Date(end).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
    lbl.innerHTML = `<i class="fa-solid fa-calendar-check" style="color:var(--success)"></i> <strong>${startFmt}</strong> – <strong>${endFmt}</strong>`;
    lbl.style.display = 'block';
  }
  ncVcRender();
  ncLoadRooms();
}


// â”€â”€â”€ Smart Assignment â”€â”€â”€
async function loadAssignQueue() {
  try {
    const r = await apiFetch('/api/clients');
    const clients = await r.json();
    const pending = clients.filter(c => ['registered','screening_completed','awaiting_assignment'].includes(c.status) && !c.assigned_therapist_id);
    const el = document.getElementById('assignQueue');
    if (!pending.length) {
      el.innerHTML = `<div style="text-align:center;padding:30px;color:var(--success)"><i class="fa-solid fa-circle-check" style="font-size:32px;margin-bottom:10px"></i><p style="font-weight:700">All clients assigned!</p></div>`;
    } else {
      el.innerHTML = pending.map(c => `
        <div class="queue-card" id="qc-${c.id}" onclick="selectAssignClient(${c.id})">
          <div class="queue-name">${c.full_name} <span class="queue-code">${c.client_code}</span></div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:6px">
            ${riskBadge(c.risk_level)}<span class="badge badge-blue">${c.language_pref}</span>
            <span class="badge badge-gray">${c.therapist_gender_pref}</span>
          </div>
        </div>`).join('');
    }
  } catch(e){}
}

async function selectAssignClient(cid) {
  selectedAssignClient = cid;
  document.querySelectorAll('.queue-card').forEach(c => c.classList.remove('selected'));
  document.getElementById('qc-'+cid)?.classList.add('selected');

  document.getElementById('recPlaceholder').style.display='none';
  document.getElementById('recResults').style.display='block';
  document.getElementById('recList').innerHTML = '<div style="text-align:center;padding:30px"><i class="fa-solid fa-spinner fa-spin" style="font-size:24px;color:var(--navy)"></i><p style="margin-top:10px;color:var(--text-muted)">Analyzing match criteria...</p></div>';

  const client = allClients.find(c=>c.id===cid);
  if(client) document.getElementById('selectedClientBadge').innerHTML = `<span style="font-size:13px;font-weight:700;color:var(--navy)">${client.full_name}</span>`;

  try {
    const r = await apiFetch('/api/assign/recommend', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:cid})});
    const data = await r.json();
    const recs = data.recommendations;
    if (!recs.length) { document.getElementById('recList').innerHTML='<p style="color:var(--text-muted);text-align:center;padding:20px">No therapists available</p>'; return; }
    document.getElementById('recList').innerHTML = recs.map(t => {
      const score = t.match_score;
      const cls = score>=80?'match-high':score>=60?'match-mid':'match-low';
      const fillColor = score>=80?'var(--success)':score>=60?'var(--warning)':'var(--danger)';
      const pct = Math.min(100,(t.caseload/Math.max(t.max_caseload,1))*100);
      return `<div class="rec-card">
        <div class="rec-header">
          <div class="rec-avatar">${(t.full_name||'?')[0]}</div>
          <div>
            <div style="font-size:15px;font-weight:800;line-height:1.25">${t.full_name}</div>
            <div style="font-size:12px;color:var(--text-muted);margin-top:2px;line-height:1.5">${t.specialization||'General Counseling'}</div>
            <div style="display:flex;gap:6px;margin-top:6px;flex-wrap:wrap">
              ${(t.languages||'English').split(',').map(l=>`<span class="badge badge-teal">${l.trim()}</span>`).join('')}
              ${t.gender?`<span class="badge badge-blue">${t.gender}</span>`:''}
            </div>
          </div>
          <div style="text-align:right">
            <div class="match-badge ${cls}">${score}% fit</div>
            <div style="font-size:11px;color:var(--text-muted);margin-top:6px">Caseload ${t.caseload}/${t.max_caseload}</div>
          </div>
        </div>
        <div style="padding:12px;border-radius:12px;background:rgba(4,48,105,.03);border:1px solid rgba(4,48,105,.06)">
          <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px">
            <div><div style="font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Specialization</div><div style="font-size:12.5px;font-weight:700;color:var(--navy);margin-top:2px">${t.specialization||'General Counseling'}</div></div>
            <div><div style="font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Languages</div><div style="font-size:12.5px;font-weight:700;color:var(--navy);margin-top:2px">${(t.languages||'English').split(',').map(l=>l.trim()).join(', ')}</div></div>
            <div><div style="font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Gender</div><div style="font-size:12.5px;font-weight:700;color:var(--navy);margin-top:2px">${t.gender||'Any'}</div></div>
            <div><div style="font-size:10px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--muted)">Capacity</div><div style="font-size:12.5px;font-weight:700;color:var(--navy);margin-top:2px">${t.caseload}/${t.max_caseload}</div></div>
          </div>
          <div class="caseload-bar" style="margin-top:10px"><div class="caseload-fill" style="width:${pct}%;background:${fillColor}"></div></div>
        </div>
        <button class="btn btn-primary" onclick="assignTherapist(${cid},${t.id})"><i class="fa-solid fa-user-check"></i>Assign ${t.full_name.split(' ')[0]}</button>
      </div>`}).join('');
    document.getElementById('assignmentModal').classList.add('active');
  } catch(e) {
    console.error('Error loading recommendations', e);
  }
}

async function assignTherapist(clientId, therapistId) {
  try {
    const r = await apiFetch(`/api/clients/${clientId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ assigned_therapist_id: therapistId })
    });
    const d = await r.json();
    if (d.success) {
      toast('Therapist assigned successfully!');
      await loadAllClients();
      await loadAssignQueue();
      document.getElementById('recPlaceholder').style.display = 'flex';
      document.getElementById('recResults').style.display = 'none';
      selectedAssignClient = null;
      document.getElementById('assignmentModal').classList.remove('active');
    } else {
      toast(d.error || 'Assignment failed', true);
    }
  } catch(e) {
    toast('Assignment failed', true);
  }
}

async function showSectionClient(id, tab) {
  currentClientView = id;
  const el = document.getElementById('cd-content');
  if(!currentClientData || currentClientData.client.id !== id) {
    try {
      const r = await apiFetch(`/api/reception/clients/${id}`);
      currentClientData = await r.json();
    } catch(e){
      el.innerHTML = '<p style="color:red">Failed to load client details</p>';
      return;
    }
  }
  const data = currentClientData;
  const c = data.client;

  if (tab==='profile') {
    const c = data.client;
    el.innerHTML = `
      <div style="display:flex;align-items:center;gap:14px;margin-bottom:20px;padding:16px;background:var(--bg);border-radius:12px">
        <div style="width:56px;height:56px;border-radius:50%;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-size:22px;font-weight:800">${c.full_name[0]}</div>
        <div><div style="font-size:17px;font-weight:800">${c.full_name}</div>
          <div style="font-size:12px;color:var(--text-muted);margin-top:2px">${c.client_code} • Registered ${formatDate(c.registration_date)}</div>
          <div style="margin-top:6px;display:flex;gap:6px">${statusBadge(c.status)}${riskBadge(c.risk_level)}</div></div>
      </div>
      ${infoRow('Language',c.language_pref)}${infoRow('Therapist Preference',c.therapist_gender_pref)}
      ${infoRow('Intake Source',c.intake_source)}${infoRow('Assigned Therapist',c.therapist_name||'Unassigned')}
      <div style="display:flex;gap:8px;margin-top:16px">
        <button class="btn btn-gold btn-sm" onclick="selectAndAssign(${c.id})"><i class="fa-solid fa-user-check"></i>Assign Therapist</button>
        <button class="btn btn-outline btn-sm" onclick="openInvoiceForClient(${c.id})"><i class="fa-solid fa-file-invoice"></i>Create Invoice</button>
      </div>`;
  } else if (tab==='journey') {
    const j = data.journey;
    el.innerHTML = j.length ? `<div class="timeline">${j.map(e=>`
      <div class="timeline-item">
        <div class="timeline-dot"><i class="fa-solid fa-arrow-right" style="font-size:10px"></i></div>
        <div class="timeline-content">
          <div class="timeline-date">${formatDate(e.changed_at)} by ${e.changed_by_name||'System'}</div>
          <div class="timeline-text">${e.stage.replace(/_/g,' ').toUpperCase()}</div>
          ${e.notes?`<div style="font-size:12px;color:var(--text-muted);margin-top:4px">${e.notes}</div>`:''}
        </div>
      </div>`).join('')}</div>` : '<p style="color:var(--text-muted)">No journey records.</p>';
  } else if (tab==='appointments') {
    const a = data.appointments;
    el.innerHTML = a.length ? `<div style="display:flex;flex-direction:column;gap:8px">${a.map(ap=>`
      <div style="padding:12px;border-radius:8px;background:var(--bg);display:flex;align-items:center;gap:10px">
        <i class="fa-solid fa-calendar" style="color:var(--navy)"></i>
        <div><div style="font-size:13px;font-weight:700">${formatDate(ap.start_time)}</div>
          <div style="font-size:12px;color:var(--text-muted)">${ap.type} with ${ap.therapist_name||'TBA'}</div></div>
        <div style="margin-left:auto">${statusBadge(ap.status)}</div>
      </div>`).join('')}</div>` : '<p style="color:var(--text-muted)">No appointments.</p>';
  } else if (tab==='finance') {
    const inv = data.invoices;
    el.innerHTML = inv.length ? `<div>${inv.map(i=>`
      <div style="padding:12px;border-radius:8px;background:var(--bg);margin-bottom:8px;display:flex;align-items:center;gap:10px">
        <i class="fa-solid fa-file-invoice-dollar" style="color:var(--navy)"></i>
        <div><div style="font-size:13px;font-weight:700">ETB ${(i.amount||0).toLocaleString()}</div>
          <div style="font-size:12px;color:var(--text-muted)">Due: ${formatDate(i.due_date)}</div></div>
        <div style="margin-left:auto">${invStatusBadge(i.status)}</div>
        ${i.status==='pending'?`<button class="btn btn-sm btn-success" onclick="openPaymentFor(${i.id},${i.client_id})">Pay</button>`:''}
      </div>`).join('')}</div>` : '<p style="color:var(--text-muted)">No invoices.</p>';
  }
}

// ── VISUAL CALENDAR LOGIC ──
let vcCurrentDate = new Date();
let vcView = 'day'; // 'day' or 'week'
let vcAppointments = [];
let vcSelectedStart = null;
let vcSelectedEnd = null;
let vcPollingInterval = null;

function vcInit() {
  vcCurrentDate = new Date();
  vcSelectedStart = null;
  vcSelectedEnd = null;
  document.getElementById('vcSelectedLabel').style.display = 'none';
  vcFetchData();
  
  if(!vcPollingInterval) {
    vcPollingInterval = setInterval(() => {
      const modal = document.getElementById('apptEditorModal');
      if(modal && modal.classList.contains('open') || modal.classList.contains('active')) {
        vcFetchData(true);
      }
    }, 15000); // Poll every 15s when open
  }
}

async function vcFetchData(silent = false) {
  try {
    const r = await apiFetch('/api/appointments');
    vcAppointments = await r.json();
    vcRender();
  } catch(e) {}
}

function vcNav(dir) {
  if(vcView === 'day') {
    vcCurrentDate.setDate(vcCurrentDate.getDate() + dir);
  } else {
    vcCurrentDate.setDate(vcCurrentDate.getDate() + (dir * 7));
  }
  vcSelectedStart = null;
  vcSelectedEnd = null;
  document.getElementById('vcSelectedLabel').style.display = 'none';
  document.getElementById('apptEditorDateTime').value = '';
  document.getElementById('apptEditorEndTime').value = '';
  vcRender();
}

function vcSetView(view) {
  vcView = view;
  document.getElementById('vcBtnDay').classList.toggle('active', view === 'day');
  document.getElementById('vcBtnWeek').classList.toggle('active', view === 'week');
  vcRender();
}

function vcGetWeekDays(date) {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Adjust when day is Sunday
  const monday = new Date(d.setDate(diff));
  
  const days = [];
  for(let i=0; i<5; i++) { // Monday to Friday
    const nd = new Date(monday);
    nd.setDate(monday.getDate() + i);
    days.push(nd);
  }
  return days;
}

function vcRender() {
  const grid = document.getElementById('vcGrid');
  const label = document.getElementById('vcDateLabel');
  
  const days = vcView === 'day' ? [vcCurrentDate] : vcGetWeekDays(vcCurrentDate);
  
  if(vcView === 'day') {
    label.textContent = days[0].toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric', year:'numeric'});
  } else {
    label.textContent = `${days[0].toLocaleDateString('en-US', {month:'short', day:'numeric'})} - ${days[4].toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'})}`;
  }
  
  let html = `<div class="vc-time-col"><div class="vc-day-header">Time</div>`;
  for(let h=8; h<=19; h++) { // 8 AM to 7 PM
    const ampm = h >= 12 ? 'PM' : 'AM';
    const hour = h > 12 ? h - 12 : h;
    html += `<div class="vc-time-slot">${hour} ${ampm}</div>`;
  }
  html += `</div><div class="vc-days">`;
  
  days.forEach((d, dIdx) => {
    const dateStr = d.toISOString().split('T')[0];
    const dayName = d.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'});
    
    html += `<div class="vc-day-col">
               <div class="vc-day-header">${dayName}</div>`;
               
    for(let h=8; h<=19; h++) {
      const slotStart = new Date(d);
      slotStart.setHours(h, 0, 0, 0);
      const slotEnd = new Date(d);
      slotEnd.setHours(h+1, 0, 0, 0);
      
      const slotStartStr = slotStart.toISOString();
      const slotEndStr = slotEnd.toISOString();
      
      // Check busy
      const isBusy = vcAppointments.some(a => {
        if(['cancelled','no_show','terminated'].includes(a.status)) return false;
        // Ignore the appointment currently being edited
        if(document.getElementById('apptEditorId') && document.getElementById('apptEditorId').value == a.id) return false;
        
        const aStart = new Date(a.start_time);
        const aEnd = new Date(a.end_time);
        return (aStart < slotEnd && aEnd > slotStart);
      });
      
      let cls = 'vc-slot available';
      if(isBusy) cls = 'vc-slot busy';
      if(vcSelectedStart === slotStartStr) cls += ' selected';
      
      html += `<div class="${cls}" data-start="${slotStartStr}" data-end="${slotEndStr}" onclick="vcSlotClick(this, ${isBusy})"></div>`;
    }
    
    // Render existing appts as absolute blocks
    const dayAppts = vcAppointments.filter(a => {
      if(['cancelled','no_show','terminated'].includes(a.status)) return false;
      const aDate = a.start_time.split('T')[0];
      return aDate === dateStr;
    });
    
    dayAppts.forEach(a => {
      const aStart = new Date(a.start_time);
      const aEnd = new Date(a.end_time);
      if(aStart.getHours() < 8 || aStart.getHours() > 19) return;
      
      const top = (aStart.getHours() - 8 + aStart.getMinutes()/60) * 40;
      const height = ((aEnd - aStart) / (1000 * 60 * 60)) * 40;
      
      // If editing this appt, make it semi-transparent
      const isEditing = document.getElementById('apptEditorId') && document.getElementById('apptEditorId').value == a.id;
      const opacity = isEditing ? '0.4' : '1';
      const border = isEditing ? '2px dashed var(--danger)' : 'none';
      
      html += `<div class="vc-appt" style="top:${top+32}px;height:${height}px;background:var(--navy);opacity:${opacity};border:${border}">
                 ${isEditing ? 'Editing...' : 'Booked'}
               </div>`;
    });
    
    html += `</div>`;
  });
  
  html += `</div>`;
  grid.innerHTML = html;
  
  // Render current time line
  const now = new Date();
  if(vcView === 'day' && days[0].toDateString() === now.toDateString()) {
    if(now.getHours() >= 8 && now.getHours() <= 19) {
      const top = (now.getHours() - 8 + now.getMinutes()/60) * 40;
      const daysWrap = grid.querySelector('.vc-days');
      if(daysWrap) {
        daysWrap.innerHTML += `<div class="vc-current-time" style="top:${top+32}px"></div>`;
      }
    }
  }
}

function vcSlotClick(el, isBusy) {
  if(isBusy) return;
  const start = el.dataset.start;
  const end = el.dataset.end;
  
  vcSelectedStart = start;
  vcSelectedEnd = end;
  
  document.getElementById('apptEditorDateTime').value = start.slice(0,16);
  document.getElementById('apptEditorEndTime').value = end.slice(0,16);
  
  const dStart = new Date(start);
  const dEnd = new Date(end);
  const formatted = `${dStart.toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'})}, ${dStart.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})} - ${dEnd.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;
  
  const sl = document.getElementById('vcSelectedLabel');
  sl.textContent = `Selected: ${formatted}`;
  sl.style.display = 'block';
  
  vcRender();
}

// Visual Calendar: modal hook removed (handled inline)

async function loadTodaySchedule() {
  const today = new Date().toISOString().split('T')[0];
  try {
    const res = await apiFetch(`/api/appointments?start=${today}&end=${today}`);
    const appts = (await res.json()).sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
    const el = document.getElementById('todaySchedule');
    if (!el) return;
    if (!appts.length) {
      el.innerHTML = `<div style="text-align:center;padding:20px;color:var(--text-muted)"><i class="fa-regular fa-calendar-xmark" style="font-size:24px;margin-bottom:8px"></i><p>No appointments today</p></div>`;
      return;
    }
    el.innerHTML = appts.slice(0, 6).map(a => {
      const visual = appointmentVisual(a);
      return `
        <div class="day-event" onclick="openClientDrawer(${a.client_id})" style="box-shadow:inset 4px 0 0 ${visual.palette.base}">
          <div class="event-time"><div>${formatApptTime(a.start_time)}</div><div style="font-size:10px;opacity:.7;margin-top:2px">${formatDate(a.start_time)}</div></div>
          <div class="event-info">
            <div class="ev-name"><span>${a.client_name || '-'}</span><span class="appt-chip">${a.client_code || 'Code'}</span></div>
            <div class="ev-sub">${a.therapist_name || '-'} - ${a.type || 'Appointment'}</div>
          </div>
          <div class="event-status">${statusBadge(a.status)}</div>
          ${isFinalAppointmentStatus(a.status) ? '<span class="badge badge-gray">Final</span>' : `<div style="display:flex;gap:4px;margin-left:4px">
            <button class="btn btn-sm btn-success" onclick="event.stopPropagation();updateApptStatus(${a.id},'completed')" title="Complete"><i class="fa-solid fa-check"></i></button>
            <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();updateApptStatus(${a.id},'no_show')" title="No Show"><i class="fa-solid fa-xmark"></i></button>
          </div>`}
        </div>`;
    }).join('');
  } catch (e) {
    const el = document.getElementById('todaySchedule');
    if (el) el.innerHTML = '<p style="color:var(--text-muted)">Failed to load</p>';
  }
}

async function loadPendingQueue() {
  try {
    const res = await apiFetch('/api/clients');
    const clients = await res.json();
    const pending = clients.filter(c => ['registered', 'screening_completed', 'awaiting_assignment'].includes(c.status) && !c.assigned_therapist_id);
    const el = document.getElementById('pendingQueue');
    if (!el) return;
    if (!pending.length) {
      el.innerHTML = `<div style="text-align:center;padding:20px;color:var(--success);font-size:13px;font-weight:600"><i class="fa-solid fa-circle-check"></i> All clients assigned</div>`;
      return;
    }
    el.innerHTML = pending.slice(0, 5).map(c => `
      <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;background:var(--bg);cursor:pointer;margin-bottom:6px"
           onclick="showSection('assignment');setTimeout(()=>selectAssignClient(${c.id}),400)">
        <div style="width:32px;height:32px;border-radius:50%;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px">${(c.full_name || '?')[0]}</div>
        <div style="flex:1">
          <div style="font-size:13px;font-weight:700">${c.full_name || '-'}</div>
          <div style="font-size:11px;color:var(--text-muted)">${c.client_code || '-'} - ${String(c.status || '').replace(/_/g, ' ')}</div>
        </div>
        <span class="badge badge-orange">${c.risk_level || 'low'}</span>
      </div>`).join('');
  } catch (e) {}
}

async function showDayDetail(dateStr, label) {
  const panel = document.getElementById('dayDetailPanel');
  const title = document.getElementById('dayDetailTitle');
  const list = document.getElementById('dayDetailList');
  if (!panel || !title || !list) return;
  title.textContent = label;
  panel.style.display = 'block';
  try {
    const r = await apiFetch(`/api/appointments?start=${dateStr}&end=${dateStr}`);
    const appts = (await r.json()).sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
    if (!appts.length) {
      list.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-muted)"><i class="fa-regular fa-calendar" style="font-size:28px;margin-bottom:8px"></i><p style="font-weight:600">No appointments this day</p><p style="font-size:12px;margin-top:4px">Use the appointment panel to book, change, or cancel a slot.</p></div>`;
      return;
    }
    list.innerHTML = appts.map(a => `
      <div class="day-event" style="box-shadow:inset 4px 0 0 ${appointmentVisual(a).palette.base}">
        <div class="event-time">${formatApptTime(a.start_time)}</div>
        <div class="event-info">
          <div class="ev-name">${a.client_name || '-'}</div>
          <div class="ev-sub">${a.therapist_name || '-'} - ${a.type || 'Appointment'} - ${a.location || '-'}</div>
        </div>
        <div class="event-status" onclick="event.stopPropagation()">
          <button class="btn btn-ghost btn-sm" onclick="openClientDrawer(${a.client_id})"><i class="fa-regular fa-user"></i>Client</button>
          ${isFinalAppointmentStatus(a.status) ? '<span class="badge badge-gray">Final</span>' : `<div class="event-actions">
            <button class="btn btn-success btn-sm" onclick="updateApptStatus(${a.id},'completed')"><i class="fa-solid fa-check"></i></button>
            <button class="btn btn-outline btn-sm" onclick="changeAppt(${a.id},'temporary')"><i class="fa-solid fa-clock-rotate-left"></i></button>
            <button class="btn btn-gold btn-sm" onclick="changeAppt(${a.id},'permanent')"><i class="fa-solid fa-calendar-days"></i></button>
            <button class="btn btn-danger btn-sm" onclick="changeAppt(${a.id},'cancelled')"><i class="fa-solid fa-ban"></i></button>
          </div>`}
        </div>
      </div>`).join('');
  } catch (e) {}
}

init();
