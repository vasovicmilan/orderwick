#!/bin/bash
# Records Claude's player on a virtual screen (Linux, needs xvfb + ffmpeg):
#   tools/record_agent.sh out.mp4 <Orderwick --agent options...>
# The virtual screen is exactly the window size, so the recording shows the whole game and nothing else.
OUT=$1; shift
SIZE=${SIZE:-1280x800}
DISP=${DISP:-:77}
Xvfb $DISP -screen 0 ${SIZE}x24 >/dev/null 2>&1 & XV=$!
sleep 2
export DISPLAY=$DISP
# Sound: the game plays into a file (SDL "disk" driver, real time), the file is added to the video at the end.
RAW="${OUT%.*}.raw"; rm -f "$RAW"
export SDL_AUDIODRIVER=disk SDL_DISKAUDIOFILE="$RAW"
T0=$(date +%s.%N)
ffmpeg -loglevel error -y -f x11grab -framerate 20 -video_size $SIZE -i $DISP -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p "$OUT" & FF=$!
sleep 1
${ORDERWICK_CMD:-python3 main.py} --agent --size $SIZE "$@"
CODE=$?
sleep 2; kill -INT $FF; wait $FF; kill $XV
if [ -s "$RAW" ]; then
  # the sound starts when the game starts: shift it by the time the recording was already running
  BORN=$(stat -c %W "$RAW"); [ "$BORN" = "0" ] && BORN=$(echo "$T0 + 2" | bc)
  OFFSET=$(printf "%.3f" "$(echo "$BORN - $T0" | bc)")
  ffmpeg -loglevel error -y -i "$OUT" -itsoffset "$OFFSET" -f s16le -ar 44100 -ac 2 -i "$RAW" -map 0:v -map 1:a \
    -c:v copy -c:a aac -b:a 160k -shortest "${OUT%.*}.sound.mp4" 2>/dev/null \
    || ffmpeg -loglevel error -y -i "$OUT" -itsoffset "$OFFSET" -f s16le -ar 44100 -ac 2 -i "$RAW" -map 0:v -map 1:a -c:v copy -c:a aac -b:a 160k -shortest "${OUT%.*}.sound.mp4"
fi
exit $CODE
