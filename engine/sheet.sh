#!/bin/bash
# Тексеру парағы: әр 0,5 с кадр, уақыт белгісімен, 6×4 тор -> <video>_sheets/s_NN.jpg
# bash sheet.sh out/final.mp4 [fps=2]
V="$1"; F="${2:-2}"; D="${V%.*}_sheets"; mkdir -p "$D"
ffmpeg -v error -y -i "$V" -vf "fps=$F,scale=270:480,drawtext=text='%{pts\:hms}':x=6:y=6:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=6x4" -q:v 3 "$D/s_%02d.jpg" 2>&1 | grep -v Fontconfig
ls "$D"/*.jpg
