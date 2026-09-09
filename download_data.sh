#!/usr/bin/env bash
# Fetch the clips. They are attached to a GitHub Release rather than committed,
# because video does not belong in git history.
set -euo pipefail

REPO="${AVSYNC_REPO:-sunayana-moro/avsync-assignment}"
TAG="${AVSYNC_TAG:-data-v1}"

mkdir -p data
cd data

for f in dev.tar.gz heldout.tar.gz; do
  if [ -d "${f%%.*}" ]; then
    echo "${f%%.*}/ already present, skipping"
    continue
  fi
  echo "Downloading $f ..."
  url="https://github.com/${REPO}/releases/download/${TAG}/${f}"
  if command -v curl >/dev/null 2>&1; then
    curl -fL --retry 3 -o "$f" "$url"
  else
    wget --tries=3 -O "$f" "$url"
  fi
  echo "Extracting $f ..."
  tar xzf "$f"
  rm -f "$f"
done

cd ..
echo ""
echo "Done."
echo "  dev clips:      $(ls data/dev/*.mp4 2>/dev/null | wc -l)  (labels.json included)"
echo "  held-out clips: $(ls data/heldout/*.mp4 2>/dev/null | wc -l)  (no labels -- this is what we score)"
