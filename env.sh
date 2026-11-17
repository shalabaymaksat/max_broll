# source <kit>/env.sh — әр Bash командасының басында (shell күйі сақталмайды)
#   K — kit түбірі, E — engine, PY — python (numpy, Pillow, mlx-whisper/faster-whisper)
K="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"; export K E="$K/engine"
# Mac (Максат): дайын venv мен ffmpeg
[ -x "$HOME/Downloads/video_tools/.venv/bin/python" ] && export PY="$HOME/Downloads/video_tools/.venv/bin/python" || export PY=python3
[ -x "$HOME/Downloads/groq_stt/bin/ffmpeg" ] && ! command -v ffmpeg >/dev/null && export PATH="$HOME/Downloads/groq_stt/bin:$PATH"
true
