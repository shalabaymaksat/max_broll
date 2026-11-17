# max_broll

Talking-head видеоны рилске айналдыратын Claude Code скилі мен рендер қозғалтқышы: сөзбе-сөз субтитр (кілт сөз алтын/үлкен), айтылған тақырыпқа сай **сплит B-roll** (жоғарыда B-roll, төменде спикер), рейтинг/тізім **тақтасы** және **термин** карточкалары блюр фон үстінде.

Референс талдауы: [reference/ANALYSIS.md](reference/ANALYSIS.md) · Нұсқаулық: [SKILL.md](SKILL.md)

```bash
git clone https://github.com/shalabaymaksat/max_broll ~/Downloads/max_broll
ln -s ~/Downloads/max_broll ~/.claude/skills/max_broll
source ~/Downloads/max_broll/env.sh
P=~/Downloads/my_reel; mkdir -p $P/broll && ln -s /path/video.mp4 $P/src.mp4 && cp $K/templates/plan.py $P/
$PY $E/stt.py $P --prompt "терминдер"   # words.json
$PY $E/cut.py $P                        # cut.mp4 (кідірістер қиылған)
# plan.py толтыр -> тексер -> рендер
$PY $E/render.py $P --dry
$PY $E/render.py $P --test 3 12 20
$PY $E/render.py $P                     # out/final.mp4
```

Талап: Python 3.10+, `numpy`, `Pillow`, `mlx-whisper` (Mac arm64) немесе `faster-whisper`, ffmpeg. Қаріп — Montserrat (OFL, `fonts/`).
