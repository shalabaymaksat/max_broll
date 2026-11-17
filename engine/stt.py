"""Жергілікті Whisper транскрипция (API жоқ). Mac arm64 — mlx-whisper, басқа жерде faster-whisper.

    python stt.py PROJ [--lang kk] [--prompt "Ла Масия, Месси, брендинг"] [--model large-v3]
    -> PROJ/words.json {"text", "words":[{w,s,e}]}   (кіріс: PROJ/src.mp4)
"""
import argparse, json, os, platform, subprocess

ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('--lang', default='kk')
ap.add_argument('--prompt', default=None); ap.add_argument('--model', default=os.environ.get('MB_WHISPER', 'large-v3'))
ap.add_argument('--src', default='src.mp4')
a = ap.parse_args()
P = os.path.abspath(a.proj); FF = os.environ.get('FFMPEG', 'ffmpeg')
wav = f'{P}/voice16k.wav'
subprocess.run([FF, '-v', 'error', '-y', '-i', f'{P}/{a.src}', '-ac', '1', '-ar', '16000', wav], check=True)
lang = None if a.lang == 'auto' else a.lang
words, texts = [], []
use_mlx = platform.system() == 'Darwin' and platform.machine() == 'arm64'
if use_mlx:
    try:
        import mlx_whisper
    except ImportError:
        use_mlx = False
if use_mlx:
    r = mlx_whisper.transcribe(wav, path_or_hf_repo=f'mlx-community/whisper-{a.model}-mlx', language=lang,
                               word_timestamps=True, initial_prompt=a.prompt, condition_on_previous_text=False)
    for sg in r['segments']:
        texts.append(sg['text'].strip())
        words += [dict(w=w['word'].strip(), s=round(w['start'], 3), e=round(w['end'], 3)) for w in sg.get('words', [])]
else:
    from faster_whisper import WhisperModel
    m = WhisperModel(a.model, device='cpu', compute_type='int8', cpu_threads=os.cpu_count() or 4)
    segs, _ = m.transcribe(wav, language=lang, word_timestamps=True, initial_prompt=a.prompt,
                           vad_filter=True, condition_on_previous_text=False, beam_size=5)
    for sg in segs:
        texts.append(sg.text.strip())
        words += [dict(w=w.word.strip(), s=round(w.start, 3), e=round(w.end, 3)) for w in sg.words or []]
words = [w for w in words if w['w']]
json.dump(dict(text=' '.join(texts), words=words), open(f'{P}/words.json', 'w'), ensure_ascii=False, indent=1)
print('\n'.join(texts))
print(f'{len(words)} сөз -> {P}/words.json')
