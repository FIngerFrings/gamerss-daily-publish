#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GAMERSS_DIR="${GAMERSS_DIR:-$SCRIPT_DIR}"
XHS_DIR="${XHS_DIR:-$HOME/.openclaw/workspace/skills/xiaohongshu-skills-main}"

cd "$GAMERSS_DIR"

# Run the GameRSS script
"$GAMERSS_DIR/.venv/bin/python" main.py

# Find the latest news folder generated in this run
LATEST_FOLDER=$(find . -maxdepth 1 -type d -name 'news_*' -mmin -10 | sed 's|^\./||' | sort | tail -1)

if [ -z "$LATEST_FOLDER" ]; then
    echo "No newly generated news folder found"
    exit 1
fi

echo "Publishing from folder: $LATEST_FOLDER"

# Get the txt filename for title and content
TXT_FILE=$(ls "$LATEST_FOLDER"/每日游讯*.txt 2>/dev/null | head -1)

if [ -z "$TXT_FILE" ]; then
    echo "No txt file found"
    exit 1
fi

# Build a fixed Xiaohongshu title from the date suffix in the digest filename
DATE_SUFFIX=$(basename "$TXT_FILE" .txt | sed 's/^.*｜ *//')
TITLE="每日游讯 ｜ $DATE_SUFFIX"

# Create a temporary title file
TITLE_FILE="$LATEST_FOLDER/title.txt"
echo "$TITLE" > "$TITLE_FILE"

# Create content file from the final digest and keep a hard safety cap
CONTENT_FILE="$LATEST_FOLDER/content.txt"
"$GAMERSS_DIR/.venv/bin/python" -c "
with open('$TXT_FILE', 'r', encoding='utf-8') as f:
    content = f.read().strip()
content = content[:950]
with open('$CONTENT_FILE', 'w', encoding='utf-8') as f:
    f.write(content)
"

# Get absolute paths
ABS_TXT_FILE="$GAMERSS_DIR/$TXT_FILE"
ABS_TITLE_FILE="$GAMERSS_DIR/$LATEST_FOLDER/title.txt"
ABS_CONTENT_FILE="$GAMERSS_DIR/$LATEST_FOLDER/content.txt"

echo "Title: $TITLE"
echo "Content file: $ABS_CONTENT_FILE"

# Get list of images in order (cover first, then 01-10)
IMAGES=()
for img in "$LATEST_FOLDER"/封面.png "$LATEST_FOLDER"/[0-9][0-9]_*.png; do
    if [ -f "$img" ]; then
        IMAGES+=("$GAMERSS_DIR/$img")
    fi
done

if [ ${#IMAGES[@]} -eq 0 ]; then
    echo "No png images found in $LATEST_FOLDER"
    exit 1
fi

echo "Images: ${IMAGES[*]}"

# Activate venv and publish
if [ ! -d "$XHS_DIR" ]; then
    echo "XHS_DIR does not exist: $XHS_DIR"
    exit 1
fi

cd "$XHS_DIR"
source .venv/bin/activate

python scripts/cli.py publish \
    --title-file "$ABS_TITLE_FILE" \
    --content-file "$ABS_CONTENT_FILE" \
    --images "${IMAGES[@]}"

echo "Published successfully!"
