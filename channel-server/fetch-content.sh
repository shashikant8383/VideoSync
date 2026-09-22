#!/bin/bash
#
# Builds three playlists of real animated content.
#
# Sources are Blender Foundation open movies (Creative Commons BY),
# pulled from archive.org. Only short excerpts are taken: placing -ss
# before -i makes ffmpeg seek with HTTP range requests, so it downloads
# roughly the excerpt rather than the whole film. That matters - the full
# files are 60-100MB each and this machine is short on disk.
#
# Every clip is encoded to identical parameters because the channel
# engine concatenates them. Mismatched codecs, resolution, frame rate or
# audio layout are the usual reason a channel dies at a clip boundary.

set -euo pipefail

cd "$(dirname "$0")"

CLIP_SECONDS=60
WIDTH=1280
HEIGHT=720
FPS=25

BBB="https://archive.org/download/BigBuckBunny_124/Content/big_buck_bunny_720p_surround.mp4"
SINTEL="https://archive.org/download/Sintel/sintel-2048-surround_512kb.mp4"
ED="https://archive.org/download/ElephantsDream/ed_hd.mp4"

# channel_dir | clip_name | source_url | start_offset_seconds
# Pipe-delimited because the URLs contain colons.
CLIPS=(
  "cartoons|01-big-buck-bunny|$BBB|70"
  "cartoons|02-sintel|$SINTEL|130"
  "cartoons|03-elephants-dream|$ED|95"

  "shorts|01-big-buck-bunny|$BBB|250"
  "shorts|02-sintel|$SINTEL|370"
  "shorts|03-elephants-dream|$ED|310"

  "classics|01-big-buck-bunny|$BBB|430"
  "classics|02-sintel|$SINTEL|610"
  "classics|03-elephants-dream|$ED|490"
)

for entry in "${CLIPS[@]}"; do
  IFS='|' read -r channel name url start <<< "$entry"

  mkdir -p "content/${channel}"

  out="content/${channel}/${name}.mp4"

  if [ -f "$out" ]; then
    echo "exists, skipping: $out"
    continue
  fi

  echo "Fetching ${channel}/${name} (${CLIP_SECONDS}s from ${start}s)..."

  ffmpeg -y -loglevel error \
    -ss "$start" \
    -i "$url" \
    -t "$CLIP_SECONDS" \
    -vf "scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2,fps=${FPS}" \
    -c:v libx264 -preset veryfast -profile:v main -pix_fmt yuv420p \
    -g 50 -keyint_min 50 -sc_threshold 0 \
    -b:v 2000k -maxrate 2000k -bufsize 4000k \
    -c:a aac -b:a 128k -ar 48000 -ac 2 \
    "$out"
done

# Write a concat list per channel.
for dir in content/*/; do
  [ -d "$dir" ] || continue

  channel=$(basename "$dir")

  # Skip the original test-pattern content if it is still around.
  ls "${dir}"*.mp4 >/dev/null 2>&1 || continue

  : > "${dir}playlist.txt"

  for f in "${dir}"*.mp4; do
    echo "file '$(basename "$f")'" >> "${dir}playlist.txt"
  done

  echo
  echo "${channel}:"
  cat "${dir}playlist.txt" | sed 's/^/    /'
done

echo
du -sh content/* 2>/dev/null
