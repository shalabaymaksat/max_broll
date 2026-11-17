"""B-roll жүктеу (міндетті емес): Pexels API, тегін кілт — https://www.pexels.com/api/
    PEXELS_API_KEY=… python fetch.py PROJ "football academy training" academy [--photo] [--n 1]
    -> PROJ/broll/academy.mp4 (немесе .jpg). Сұрау ағылшынша, нақты зат/әрекет атымен.
Нақты адам/бренд (Месси, Барселона) Pexels-те болмайды — оны пайдаланушыдан сұра.
"""
import argparse, json, os, urllib.parse, urllib.request

ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('query'); ap.add_argument('name')
ap.add_argument('--photo', action='store_true'); ap.add_argument('--n', type=int, default=1)
a = ap.parse_args()
key = os.environ.get('PEXELS_API_KEY')
if not key: raise SystemExit('PEXELS_API_KEY жоқ — B-roll-ды пайдаланушыдан сұра (PROJ/broll/ ішіне салсын)')
q = urllib.parse.quote(a.query)
url = (f'https://api.pexels.com/v1/search?query={q}&per_page={a.n}' if a.photo else
       f'https://api.pexels.com/videos/search?query={q}&per_page={a.n}&size=medium')
req = urllib.request.Request(url, headers={'Authorization': key, 'User-Agent': 'max_broll'})
data = json.load(urllib.request.urlopen(req))
os.makedirs(f'{a.proj}/broll', exist_ok=True)
items = data.get('photos' if a.photo else 'videos', [])
for k, it in enumerate(items):
    sfx = '' if k == 0 else f'_{k + 1}'
    if a.photo:
        src, ext = it['src']['large2x'], '.jpg'
    else:
        files = sorted((f for f in it['video_files'] if f.get('height')), key=lambda f: abs(f['height'] - 1080))
        src, ext = files[0]['link'], '.mp4'
    out = f'{a.proj}/broll/{a.name}{sfx}{ext}'
    urllib.request.urlretrieve(src, out); print(out)
if not items: print('!! табылмады:', a.query)
