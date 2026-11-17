"""Кідірістерді қию: сөздер арасындағы gap > --gap болса, оны --pad қалдырып қияды.

    python cut.py PROJ [--gap 0.35] [--pad 0.10] [--drop 12.3-14.1 ...]
    кіріс: src.mp4 + words.json  ->  cut.mp4 + words.json (жаңа уақыт), ескісі words_src.json
--drop — қайта бастаған/қате айтылған жерлерді қолмен алып тастау (src секундтарымен).
"""
import argparse, json, os, shutil, subprocess

ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('--gap', type=float, default=0.35)
ap.add_argument('--pad', type=float, default=0.10); ap.add_argument('--drop', nargs='*', default=[])
a = ap.parse_args()
P = os.path.abspath(a.proj); FF = os.environ.get('FFMPEG', 'ffmpeg')
if not os.path.exists(f'{P}/words_src.json'):
    shutil.copy(f'{P}/words.json', f'{P}/words_src.json')
words = json.load(open(f'{P}/words_src.json'))['words']
drops = [tuple(map(float, d.split('-'))) for d in a.drop]
words = [w for w in words if not any(x <= (w['s'] + w['e']) / 2 <= y for x, y in drops)]
segs = []
for w in words:
    s, e = max(0.0, w['s'] - a.pad), w['e'] + a.pad
    if segs and s - segs[-1][1] < a.gap - 2 * a.pad and not any(segs[-1][1] <= x <= s for x, _ in drops):
        segs[-1][1] = max(segs[-1][1], e)
    else:
        if segs and s < segs[-1][1]: s = segs[-1][1]
        segs.append([s, e])
sel = '+'.join(f'between(t,{s:.3f},{e:.3f})' for s, e in segs)
open(f'{P}/.cut_filter', 'w').write(
    f"[0:v]select='{sel}',setpts=N/FRAME_RATE/TB[v];[0:a]aselect='{sel}',asetpts=N/SR/TB[a]")
subprocess.run([FF, '-v', 'error', '-y', '-i', f'{P}/src.mp4', '-filter_complex_script', f'{P}/.cut_filter',
                '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '16', '-preset', 'fast', '-c:a', 'aac',
                '-b:a', '192k', f'{P}/cut.mp4'], check=True)
# уақытты қайта есептеу
out, off = [], 0.0
for s, e in segs:
    for w in words:
        if s <= w['s'] < e:
            out.append(dict(w=w['w'], s=round(w['s'] - s + off, 3), e=round(min(w['e'], e) - s + off, 3)))
    off += e - s
src_len = float(subprocess.run([FF.replace('ffmpeg', 'ffprobe') if FF != 'ffmpeg' else 'ffprobe', '-v', 'error',
                 '-show_entries', 'format=duration', '-of', 'csv=p=0', f'{P}/src.mp4'], capture_output=True, text=True).stdout)
json.dump(dict(text=' '.join(w['w'] for w in out), words=out), open(f'{P}/words.json', 'w'), ensure_ascii=False, indent=1)
print(f'{len(segs)} кесек, {src_len:.1f} с -> {off:.1f} с ({src_len - off:.1f} с қиылды) -> {P}/cut.mp4')
