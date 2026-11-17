"""max_broll рендер.

    python render.py PROJ                 # толық рендер -> PROJ/out/final.mp4
    python render.py PROJ --dry           # уақыт кестесі: оқиғалар мен субтитр фразалары (рендерсіз)
    python render.py PROJ --test 3 18 42  # сол секундтардағы кадрлар -> PROJ/test/t_*.jpg
    python render.py PROJ --from 10 --to 30   # үзінді (out/part.mp4)

PROJ ішінде: cut.mp4 (болмаса src.mp4), words.json, plan.py, broll/…
"""
import argparse, json, os, re, subprocess, sys, importlib.util
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
KIT = os.path.dirname(HERE)
FF = os.environ.get('FFMPEG', 'ffmpeg')
W, H, FPS = 1080, 1920, 30
HALF = 960

# ---------- стиль (референс DfTXUsdomUW өлшемдері, 1080×1920) ----------
GOLD = (246, 183, 60)
WHITE = (255, 255, 255)
SUB_SIZE = 72          # негізгі субтитр
SUB_SMALL = 0.74       # кілт сөз тұрған фразадағы қосалқы жолдар
SUB_BIG = 1.55         # кілт сөз
FADE = 0.12            # сөздің пайда болуы
PILL_FILL = (24, 24, 24, 225); PILL_LINE = (70, 70, 70, 255)
BLUR_DIM = 0.42        # блюр фонның жарықтығы
BLUR_IN = 0.25         # блюрға кіру уақыты

_fc = {}
def font(weight, size):
    k = (weight, int(size))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(f'{KIT}/fonts/Montserrat-{weight}.ttf', int(size))
    return _fc[k]


def norm(s):
    return re.sub(r'[^\w-]', '', s.lower().replace('ё', 'е'))


# ---------- видео оқу ----------
class Reader:
    """ffmpeg арқылы видеоны/суретті берілген өлшемге cover-fit етіп кадрлап оқиды."""
    def __init__(self, path, w, h, start=0.0, fit='cover', dur=None):
        self.w, self.h, self.last, self.i = w, h, None, 0
        self.img = None
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.jpg', '.jpeg', '.png', '.webp'):
            im = Image.open(path).convert('RGB')
            s = max(w / im.width, h / im.height) * 1.12
            self.img = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
            self.kb_frames = max(1, int((dur or 3.0) * FPS))
            return
        vf = (f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}' if fit == 'cover' else
              f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black')
        cmd = [FF, '-v', 'error', '-ss', f'{start:.3f}', '-i', path, '-an', '-vf', f'{vf},fps={FPS},format=rgb24',
               '-f', 'rawvideo', '-']
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=w * h * 3 * 4)

    def read(self):
        if self.img is not None:   # Ken Burns: 1.00 -> 1.08 баяу зум
            k = min(1.0, self.i / self.kb_frames); self.i += 1
            z = 1.0 + 0.08 * k
            # кесу терезесі суреттің ортасында (сурет кадрдан 1,12 есе үлкен дайындалған)
            sw = self.img.width / (1.12 * z); sh = self.img.height / (1.12 * z)
            x0, y0 = (self.img.width - sw) / 2, (self.img.height - sh) / 2
            return self.img.resize((self.w, self.h), Image.BILINEAR, box=(x0, y0, x0 + sw, y0 + sh))
        buf = self.p.stdout.read(self.w * self.h * 3)
        if len(buf) == self.w * self.h * 3:
            self.last = Image.frombytes('RGB', (self.w, self.h), buf)
        elif self.last is None:
            self.last = Image.new('RGB', (self.w, self.h), (0, 0, 0))
        return self.last

    def close(self):
        if self.img is None and self.p.poll() is None:
            self.p.kill()


def probe_dur(path):
    out = subprocess.run([FF.replace('ffmpeg', 'ffprobe') if FF != 'ffmpeg' else 'ffprobe', '-v', 'error',
                          '-show_entries', 'format=duration', '-of', 'csv=p=0', path], capture_output=True, text=True)
    return float(out.stdout.strip())


# ---------- жоспар ----------
def load_plan(P):
    spec = importlib.util.spec_from_file_location('plan', f'{P}/plan.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def load_words(P, plan):
    ws = json.load(open(f'{P}/words.json'))['words']
    fix = getattr(plan, 'FIX', {})
    for w in ws:
        k = w['w']
        bare = k.strip('.,!?;:«»"')
        if bare in fix:
            w['w'] = k.replace(bare, fix[bare])
    return ws


def find(words, stem, cur):
    st = [norm(x) for x in stem.split()]
    for i in range(cur, len(words)):
        if all(i + j < len(words) and norm(words[i + j]['w']).startswith(st[j]) for j in range(len(st))):
            return i
    return None


def build_phrases(words, maxw=3, maxc=24, gap=0.32):
    ph, cur = [], []
    for i, w in enumerate(words):
        if cur:
            prev = words[cur[-1]]
            if (len(cur) >= maxw or w['s'] - prev['e'] > gap or re.search(r'[.,!?;:]$', prev['w'])
                    or sum(len(words[j]['w']) + 1 for j in cur) + len(w['w']) > maxc):
                ph.append(cur); cur = []
        cur.append(i)
    if cur: ph.append(cur)
    out = []
    for k, idx in enumerate(ph):
        s = words[idx[0]]['s']; e = words[idx[-1]]['e']
        nxt = words[ph[k + 1][0]]['s'] if k + 1 < len(ph) else e + 0.6
        out.append(dict(idx=idx, s=s, e=min(nxt, e + 0.45)))
    return out


def sentences_zoom(words, pattern):
    """Сөйлем сайын кадр масштабы (таза кесу): pattern=[1.0, 1.2, 1.2] қайталанады."""
    z, k = [], 0
    for w in words:
        z.append(pattern[k % len(pattern)])
        if re.search(r'[.!?]$', w['w']): k += 1
    return z


def resolve(plan, words, total):
    evs, cur, log = [], 0, []
    def t_of(word, at, cur):
        if at is not None: return at, cur
        i = find(words, word, cur)
        if i is None:
            log.append(f'!! табылмады: «{word}» (#{cur} сөзден кейін)'); return None, cur
        return words[i]['s'], i + 1
    raw = list(plan.EVENTS)
    for ev in raw:
        ev = dict(ev)
        t, cur = t_of(ev['word'], ev.get('at'), cur)
        if t is None: continue
        ev['s'] = t
        if ev['kind'] == 'board':
            its = []
            if ev.get('at') is None: cur -= 1   # бірінші жол тақырыппен бір сөзде болуы мүмкін
            for it in ev['items']:
                ti, cur = t_of(it['word'], it.get('at'), cur)
                if ti is None: continue
                its.append(dict(it, s=ti))
            ev['items'] = its
            end = (its[-1]['s'] if its else t) + ev['hold']
        elif ev['kind'] == 'term':
            th = []
            for wd, txt in ev['then']:
                ti, cur = t_of(wd, None, cur)
                if ti is not None: th.append((ti, txt))
            ev['then'] = th
            end = (th[-1][0] if th else t) + ev['hold']
        else:
            if ev.get('dur') or ev.get('at') is not None:
                end = t + (ev.get('dur') or 1.6)
            else:   # сөз тұрған фраза біткенше, кемінде 0,9 с, ең көбі 2,6 с
                j = cur - 1
                while j + 1 < len(words) and words[j + 1]['s'] - words[j]['e'] < 0.3 and \
                        not re.search(r'[.,!?]$', words[j]['w']) and words[j]['e'] - t < 1.6:
                    j += 1
                end = min(max(words[j]['e'] + 0.1, t + 0.9), t + 2.6)
        if ev.get('until'):
            tu, _ = t_of(ev['until'], None, cur)
            if tu is not None: end = tu
        ev['e'] = min(end, total)
        evs.append(ev)
    evs.sort(key=lambda e: e['s'])
    for a, b in zip(evs, evs[1:]):
        if a['e'] > b['s']: a['e'] = b['s']
    return evs, log


# ---------- сурет салу ----------
def rounded(im, r):
    m = Image.new('L', im.size, 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, im.width - 1, im.height - 1), r, fill=255)
    out = im.convert('RGBA'); out.putalpha(m); return out


def shadowed(layer, r=9, op=0.6, dy=3):
    a = layer.split()[-1].filter(ImageFilter.GaussianBlur(r)).point(lambda v: int(v * op))
    sh = Image.new('RGBA', layer.size, (0, 0, 0, 0)); sh.putalpha(a)
    base = Image.new('RGBA', layer.size, (0, 0, 0, 0)); base.alpha_composite(sh, (0, dy)); base.alpha_composite(layer)
    return base


def text_w(f, s):
    return f.getlength(s)


def draw_phrase(canvas, words, ph, t, keys, cy, scale=1.0):
    """Фраза орнында тұрады (толық фраза бойынша ортаға), әр сөз айтылғанда FADE ішінде пайда болады.
    Кілт сөз (keys) бөлек ортаңғы жолда үлкен (big — ақ, gold — алтын)."""
    idx = ph['idx']
    kinds = [keys.get(norm(words[i]['w']), next((v for k, v in keys.items() if ' ' not in k and norm(words[i]['w']).startswith(k)), None)) for i in idx]
    # көп сөзді кілт (мыс. 'бірінші орында')
    for k, v in keys.items():
        if ' ' in k:
            st = k.split()
            for a in range(len(idx) - len(st) + 1):
                if all(norm(words[idx[a + j]]['w']).startswith(st[j]) for j in range(len(st))):
                    for j in range(len(st)): kinds[a + j] = v
    if any(kinds):
        f0 = next(n for n, k in enumerate(kinds) if k); f1 = max(n for n, k in enumerate(kinds) if k)
        lines = [(list(range(0, f0)), SUB_SMALL, None), (list(range(f0, f1 + 1)), SUB_BIG, 'emph'),
                 (list(range(f1 + 1, len(idx))), SUB_SMALL, None)]
        lines = [l for l in lines if l[0]]
    else:
        lines = [(list(range(len(idx))), 1.0, None)]
    base = SUB_SIZE * scale
    lay, y = [], 0
    for ids, sc, tag in lines:
        size = base * sc
        weight = 'ExtraBold' if tag else 'Bold'
        f = font(weight, size)
        txt = ' '.join(words[idx[n]]['w'] for n in ids)
        while text_w(f, txt) > 940 and size > 30:
            size *= 0.92; f = font(weight, size)
        lay.append((ids, f, size, y, text_w(f, txt))); y += size * 1.18
    total_h = y
    layer = Image.new('RGBA', (W, int(total_h + 60)), (0, 0, 0, 0)); d = ImageDraw.Draw(layer)
    for ids, f, size, ly, tw in lay:
        x = (W - tw) / 2
        for n in ids:
            w = words[idx[n]]
            a = max(0.0, min(1.0, (t - w['s']) / FADE))
            col = GOLD if kinds[n] == 'gold' else WHITE
            if a > 0:
                d.text((x, ly + 20), w['w'], font=f, fill=col + (int(255 * a),))
            x += text_w(f, w['w'] + ' ')
    layer = shadowed(layer)
    canvas.alpha_composite(layer, (0, int(cy - total_h / 2 - 20)))


def pill(label, w, h, hl, alpha, size):
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if hl:
        d.rounded_rectangle((0, 0, w - 1, h - 1), 18, fill=GOLD + (255,))
        col = (20, 20, 20, 255)
    else:
        d.rounded_rectangle((0, 0, w - 1, h - 1), 18, fill=PILL_FILL, outline=PILL_LINE, width=2)
        col = WHITE + (255,)
    f = font('ExtraBold', size)
    tw = text_w(f, label)
    d.text(((w - tw) / 2, (h - size * 1.2) / 2), label, font=f, fill=col)
    if alpha < 1:
        a = im.split()[-1].point(lambda v: int(v * alpha)); im.putalpha(a)
    return im


def ease(x):
    x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3


def blurred(frame):
    small = frame.resize((W // 6, H // 6), Image.BILINEAR).filter(ImageFilter.GaussianBlur(5))
    b = small.resize((W, H), Image.BILINEAR)
    return Image.eval(b, lambda v: int(v * BLUR_DIM))


class Renderer:
    def __init__(self, P, plan, words, total):
        self.P, self.plan, self.words, self.total = P, plan, words, total
        self.keys = {norm(k) if ' ' not in k else ' '.join(norm(x) for x in k.split()): v
                     for k, v in getattr(plan, 'KEYS', {}).items()}
        self.phrases = build_phrases(words, **getattr(plan, 'PHRASE', {}))
        z = getattr(plan, 'ZOOM', {})
        self.zpat = z.get('pattern', [1.0, 1.2, 1.2]); self.face_y = z.get('face_y', 760)
        self.wzoom = sentences_zoom(words, self.zpat)
        self.split_y = getattr(plan, 'SPLIT_Y', 470)
        self.sub_y = getattr(plan, 'SUB_Y', 470)
        self.events, self.log = resolve(plan, words, total)
        self.readers = {}

    def media(self, path):
        return path if os.path.isabs(path) else f'{self.P}/{path}'

    def zoom_at(self, t):
        z = self.zpat[0]
        for w, zz in zip(self.words, self.wzoom):
            if w['s'] - 0.05 > t: break
            z = zz
        return z

    def reader(self, key, path, w, h, start, dur, fit='cover'):
        if key not in self.readers:
            self.readers[key] = Reader(self.media(path), w, h, start, fit, dur)
        return self.readers[key]

    def gc(self, t):
        for k in list(self.readers):
            ev = self.events[k[0]]
            if t >= ev['e'] + 0.05:
                self.readers.pop(k).close()

    def frame(self, spk, t):
        z = self.zoom_at(t)
        if z != 1.0:
            cw, ch = W / z, H / z; cy = min(max(self.face_y, ch / 2), H - ch / 2)
            spk_z = spk.resize((W, H), Image.BILINEAR, box=((W - cw) / 2, cy - ch / 2, (W + cw) / 2, cy + ch / 2))
        else:
            spk_z = spk
        ev, ei = None, None
        for n, e in enumerate(self.events):
            if e['s'] <= t < e['e']: ev, ei = e, n; break
        canvas = spk_z.convert('RGBA'); sub_y, sub_sc = self.sub_y, 1.0
        if ev and ev['kind'] in ('split', 'split2'):
            canvas = Image.new('RGBA', (W, H), (0, 0, 0, 255))
            dur = ev['e'] - ev['s']
            if ev['kind'] == 'split':
                r = self.reader((ei, 0), ev['media'][0], W, HALF, ev['src_in'][0], dur, ev.get('fit', 'cover'))
                canvas.paste(r.read(), (0, 0))
            else:
                hh = HALF // 2 - 4
                for k in range(2):
                    r = self.reader((ei, k), ev['media'][k], W, hh, ev['src_in'][k], dur)
                    canvas.paste(r.read(), (0, k * (hh + 8)))
            canvas.paste(spk.crop((0, self.split_y, W, self.split_y + HALF)), (0, HALF))
            sub_y = HALF - 8
        elif ev and ev['kind'] in ('board', 'term'):
            k = ease((t - ev['s']) / BLUR_IN)
            bl = blurred(spk_z)
            canvas = Image.blend(spk_z, bl, k).convert('RGBA') if k < 1 else bl.convert('RGBA')
            sub_y, sub_sc = 1330, 0.82
            (self.draw_board if ev['kind'] == 'board' else self.draw_term)(canvas, ev, ei, t)
        for ph in self.phrases:
            if ph['s'] <= t < ph['e']:
                draw_phrase(canvas, self.words, ph, t, self.keys, sub_y, sub_sc); break
        return canvas.convert('RGB')

    def draw_term(self, canvas, ev, ei, t):
        rows = [(ev['s'], ev['text'], GOLD)] + [(ti, tx, WHITE) for ti, tx in ev['then']]
        y = 600 if len(rows) > 1 else 700
        for ts, txt, col in rows:
            a = ease((t - ts) / 0.3)
            if a <= 0: break
            size = 78
            f = font('ExtraBold', size)
            while text_w(f, txt) > 960: size -= 3; f = font('ExtraBold', size)
            lay = Image.new('RGBA', (W, size + 60), (0, 0, 0, 0))
            c = tuple(int(150 + (v - 150) * a) for v in col)   # сұр елестен түске
            ImageDraw.Draw(lay).text(((W - text_w(f, txt)) / 2, 20), txt, font=f, fill=c + (int(255 * min(1, a * 1.6)),))
            canvas.alpha_composite(shadowed(lay, 10, 0.5), (0, int(y - 20 + (1 - a) * 14)))
            y += size * 1.45

    def draw_board(self, canvas, ev, ei, t):
        items = ev['items']; n = len(items)
        has_media = any(it.get('media') for it in items)
        shown = [it for it in items if it['s'] <= t]
        big = n <= 3 and not has_media
        ph_, step, fsz = (128, 150, 58) if big else (88, 112, 50)
        pw = 860 if not big else 860
        # тақырып: медиасыз тақтада тұрақты; медиалы тақтада бірінші жол шыққанша
        title_on = not has_media or not shown
        top = 600 if big else (470 if has_media else 560)
        if title_on:
            a = ease((t - ev['s']) / 0.3)
            f = font('ExtraBold', 76)
            lay = Image.new('RGBA', (W, 140), (0, 0, 0, 0))
            c = tuple(int(150 + (v - 150) * a) for v in GOLD)
            ty = 410 if (big or not has_media) else 540
            if not has_media and not big: ty = 400
            ImageDraw.Draw(lay).text(((W - text_w(f, ev['title'])) / 2, 20), ev['title'], font=f, fill=c + (int(255 * a),))
            canvas.alpha_composite(shadowed(lay, 10, 0.5), (0, ty - 20 - 38))
        if has_media and shown:
            cur = max((k for k, it in enumerate(items) if it['s'] <= t and it.get('media')), default=None)
            if cur is not None:
                it = items[cur]
                r = self.reader((ei, 'm', cur), it['media'], 900, 360, it.get('src_in', 0.0), ev['e'] - it['s'])
                img = rounded(r.read(), 26)
                a = ease((t - it['s']) / 0.18)
                if a < 1: img.putalpha(img.split()[-1].point(lambda v: int(v * a)))
                canvas.alpha_composite(img, (90, 60))
        for k, it in enumerate(items):
            a = ease((t - it['s']) / 0.25)
            if a <= 0: continue
            im = pill(it['label'], pw, ph_, it.get('hl') and t >= it['s'], a, fsz)
            canvas.alpha_composite(im, ((W - pw) // 2, int(top + k * step + (1 - a) * 18)))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('proj')
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--test', nargs='*', type=float)
    ap.add_argument('--from', dest='t0', type=float, default=0.0); ap.add_argument('--to', dest='t1', type=float)
    a = ap.parse_args()
    P = os.path.abspath(a.proj)
    src = f'{P}/cut.mp4' if os.path.exists(f'{P}/cut.mp4') else f'{P}/src.mp4'
    plan = load_plan(P); words = load_words(P, plan); total = probe_dur(src)
    R = Renderer(P, plan, words, total)
    for l in R.log: print(l)
    if a.dry:
        for e in R.events:
            extra = ' | '.join(f"{i['label']}@{i['s']:.2f}" for i in e.get('items', [])) or \
                    ' | '.join(f'{x}@{s:.2f}' for s, x in e.get('then', [])) or ', '.join(map(str, e.get('media', [])))
            print(f"{e['s']:7.2f}-{e['e']:7.2f} {e['kind']:6} «{e['word']}» {e.get('title') or e.get('text') or ''} {extra}")
        cover = sum(e['e'] - e['s'] for e in R.events)
        print(f'B-roll/графика үлесі: {cover / total * 100:.0f}% ({cover:.1f} / {total:.1f} с), фраза: {len(R.phrases)}')
        return
    if a.test is not None:
        os.makedirs(f'{P}/test', exist_ok=True)
        for t in a.test:
            spk = Reader(src, W, H, t).read()
            R.readers.clear()
            # B-roll кадры дәл сол сәтте болуы үшін оқиға медиасын t-ге дейін алға жылжытамыз
            for n, e in enumerate(R.events):
                if e['s'] <= t < e['e']:
                    for k, m in enumerate(e.get('media', [])):
                        hh = HALF if e['kind'] == 'split' else HALF // 2 - 4
                        R.readers[(n, k)] = Reader(R.media(m), W, hh, e['src_in'][k] + (t - e['s']), e.get('fit', 'cover'), e['e'] - e['s'])
            R.frame(spk, t).save(f'{P}/test/t_{t:06.2f}.jpg', quality=88)
            for r in R.readers.values(): r.close()
            R.readers.clear()
            print(f'{P}/test/t_{t:06.2f}.jpg')
        return
    t0, t1 = a.t0, a.t1 or total
    os.makedirs(f'{P}/out', exist_ok=True)
    name = 'final' if (t0 == 0 and a.t1 is None) else 'part'
    tmp = f'{P}/out/{name}.noaudio.mp4'
    spk_r = Reader(src, W, H, t0)
    enc = subprocess.Popen([FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                            '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', tmp],
                           stdin=subprocess.PIPE)
    nfr = int(round((t1 - t0) * FPS))
    for i in range(nfr):
        t = t0 + i / FPS
        enc.stdin.write(R.frame(spk_r.read(), t).tobytes())
        R.gc(t)
        if i % (FPS * 5) == 0: print(f'{t:7.1f} / {t1:.1f} с', flush=True)
    enc.stdin.close(); enc.wait(); spk_r.close()
    out = f'{P}/out/{name}.mp4'
    subprocess.run([FF, '-v', 'error', '-y', '-i', tmp, '-ss', f'{t0:.3f}', '-t', f'{t1 - t0:.3f}', '-i', src,
                    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', out], check=True)
    os.remove(tmp)
    print('DONE', out)


if __name__ == '__main__':
    main()
