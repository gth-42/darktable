#!/bin/bash
# Test Archiving System
# Creates dated archive folders with script copies, descriptions, and results

set -e

if [ $# -lt 2 ]; then
    echo "Usage: $0 <test_name> <script.py> [description]"
    echo "Example: $0 state_reuse benchmark_detailed_state_reuse.py 'First detailed timing test with state reuse'"
    exit 1
fi

TEST_NAME="$1"
SCRIPT_PATH="$2"
DESCRIPTION="${3:-No description provided}"

# Get script name without path
SCRIPT_NAME=$(basename "$SCRIPT_PATH")

# Create dated folder name
DATETIME=$(date +"%Y%m%d_%H%M%S")
ARCHIVE_DIR="/mnt/2t4/development/darktable/darktable/src/cli/test/${TEST_NAME}_${DATETIME}"

echo "======================================================================="
echo "Test Archive System"
echo "======================================================================="
echo "Test name:   $TEST_NAME"
echo "Script:      $SCRIPT_NAME"
echo "Archive dir: $ARCHIVE_DIR"
echo ""

# Create archive directory
mkdir -p "$ARCHIVE_DIR"

# Copy the script that will be run
cp "$SCRIPT_PATH" "$ARCHIVE_DIR/$SCRIPT_NAME"
echo "✓ Copied script to archive"

# Create description file
cat > "$ARCHIVE_DIR/test_description.txt" <<EOF
Test Name: $TEST_NAME
Date/Time: $(date "+%Y-%m-%d %H:%M:%S %Z")
Script: $SCRIPT_NAME

Description:
$DESCRIPTION

Environment:
- Hostname: $(hostname)
- Python: $(python --version 2>&1)
- User: $(whoami)
- Working Dir: $(pwd)

System Info:
$(uname -a)

CPU Info:
$(grep "model name" /proc/cpuinfo | head -1 | cut -d: -f2 | xargs)
$(grep "cpu cores" /proc/cpuinfo | head -1 | cut -d: -f2 | xargs) cores

Memory Info:
$(free -h | grep Mem | awk '{print $2 " total, " $3 " used, " $4 " available"}')

EOF
echo "✓ Created test description"

# Activate venv and run the test
echo ""
echo "======================================================================="
echo "Running test..."
echo "======================================================================="
echo ""

source ~/venv/claude1/bin/activate
python "$SCRIPT_PATH"

# Copy result files to archive
echo ""
echo "======================================================================="
echo "Archiving results..."
echo "======================================================================="

# Find and copy result files (look in /tmp for files matching the pattern)
SCRIPT_BASE=$(basename "$SCRIPT_NAME" .py)

# Pattern matching for result files
for pattern in \
    "/tmp/dt_benchmark_${SCRIPT_BASE#benchmark_}*.txt" \
    "/tmp/dt_benchmark_${SCRIPT_BASE#benchmark_}*.csv" \
    "/tmp/dt_benchmark_*${TEST_NAME}*.txt" \
    "/tmp/dt_benchmark_*${TEST_NAME}*.csv"; do

    for file in $pattern; do
        if [ -f "$file" ]; then
            cp "$file" "$ARCHIVE_DIR/"
            echo "✓ Archived: $(basename "$file")"
        fi
    done
done

# Create manifest of archive contents
cat > "$ARCHIVE_DIR/MANIFEST.txt" <<EOF
Test Archive Contents
Generated: $(date "+%Y-%m-%d %H:%M:%S %Z")

Files in this archive:
EOF

ls -lh "$ARCHIVE_DIR" >> "$ARCHIVE_DIR/MANIFEST.txt"

echo ""
echo "======================================================================="
echo "✓ Test complete and archived"
echo "======================================================================="
echo "Archive location: $ARCHIVE_DIR"
echo ""
echo "Contents:"
ls -lh "$ARCHIVE_DIR"
echo ""
