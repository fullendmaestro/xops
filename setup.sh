#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$SCRIPT_DIR/tashi-tools"

echo "=== Tashi Vertex Webots Starter Kit Setup ==="
echo

# Check for Rust
if ! command -v cargo &> /dev/null; then
    echo "ERROR: Rust/Cargo not found. Install from https://rustup.rs"
    exit 1
fi

# Find CMake (prefer pip-installed version)
CMAKE_BIN=""
if [ -x "$HOME/.local/bin/cmake" ]; then
    CMAKE_BIN="$HOME/.local/bin/cmake"
elif command -v cmake &> /dev/null; then
    CMAKE_BIN="cmake"
fi

if [ -z "$CMAKE_BIN" ]; then
    echo "ERROR: CMake not found. Install CMake 4.0+:"
    echo "  pip install cmake"
    exit 1
fi

CMAKE_VERSION=$($CMAKE_BIN --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
CMAKE_MAJOR=$(echo $CMAKE_VERSION | cut -d. -f1)
if [ "$CMAKE_MAJOR" -lt 4 ]; then
    echo "WARNING: CMake $CMAKE_VERSION found, but 4.0+ required."
    echo "  pip install cmake --upgrade"
    exit 1
fi
echo "Using CMake $CMAKE_VERSION at $CMAKE_BIN"

echo
echo "[1/3] Building Tashi tools..."
cd "$TOOLS_DIR"
CMAKE="$CMAKE_BIN" cargo build --release

echo
echo "[2/3] Setting up library..."
TARGET_LIB_DIR="$TOOLS_DIR/target/release/lib"
mkdir -p "$TARGET_LIB_DIR"

# Find and copy the library
LIB_FILE=$(find "$TOOLS_DIR/target/release/build" -name "libtashi-vertex.so" -o -name "libtashi-vertex.dylib" -o -name "tashi-vertex.dll" 2>/dev/null | head -1)
if [ -n "$LIB_FILE" ]; then
    cp "$LIB_FILE" "$TARGET_LIB_DIR/"
    echo "  Library installed to: $TARGET_LIB_DIR"
else
    echo "  WARNING: Library not found in build output"
fi

export LD_LIBRARY_PATH="$TARGET_LIB_DIR:$LD_LIBRARY_PATH"
export DYLD_LIBRARY_PATH="$TARGET_LIB_DIR:$DYLD_LIBRARY_PATH"

echo
echo "[3/3] Generating swarm configuration..."
if command -v python3 &> /dev/null; then
    python3 "$SCRIPT_DIR/utils/generate_config.py"
elif command -v python &> /dev/null; then
    python "$SCRIPT_DIR/utils/generate_config.py"
else
    echo "ERROR: python/python3 not found for config generation"
    exit 1
fi

echo
echo "=== Setup Complete ==="
echo
echo "To run: Open Webots, load worlds/sample.wbt, press Play"
