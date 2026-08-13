import re
with open(r'portals\reception_portal.html', 'r', encoding='utf-8') as f:
    content = f.read()
raw = re.findall(r"(?<!\w)fetch\('/api/", content)
raw2 = re.findall(r"(?<!\w)fetch\(`/api/", content)
print('Remaining raw fetch calls:', len(raw) + len(raw2))
