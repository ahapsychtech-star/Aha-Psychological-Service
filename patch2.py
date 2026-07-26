import sys

filepath = 'portals/therapist_portal.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

old_fn = '''host.innerHTML = items.map(([key, value]) => `
    <div style="padding:14px;border:1px solid var(--border);border-radius:12px;background:#fff">
      <div style="font-size:11px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:6px">${key}</div>
      <div style="font-size:14px;font-weight:600;color:var(--text);white-space:pre-wrap;line-height:1.7">${Array.isArray(value) ? value.join(', ') : String(value)}</div>
    </div>`).join('');'''

new_fn = '''host.innerHTML = items.map(([key, value]) => `
    <div class="print-q" style="padding:14px;border:1px solid var(--border);border-radius:12px;background:#fff">
      <div class="print-q-label" style="font-size:11px;font-weight:800;letter-spacing:1px;text-transform:uppercase;color:var(--muted);margin-bottom:6px">${key}</div>
      <div class="print-q-ans" style="font-size:14px;font-weight:600;color:var(--text);white-space:pre-wrap;line-height:1.7">${Array.isArray(value) ? value.join(', ') : String(value)}</div>
    </div>`).join('');'''

if old_fn in content:
    content = content.replace(old_fn, new_fn)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
        print("Patched successfully")
else:
    print("Could not find block to replace.")
