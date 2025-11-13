#!/bin/bash
set -e

echo "Building darktable Python API..."

# Get package config flags
GLIB_CFLAGS=$(pkg-config --cflags glib-2.0)
GLIB_LIBS=$(pkg-config --libs glib-2.0)
GTK_CFLAGS=$(pkg-config --cflags gtk+-3.0)
RSVG_CFLAGS=$(pkg-config --cflags librsvg-2.0)
JSON_CFLAGS=$(pkg-config --cflags json-glib-1.0)

# Compile the shim library
echo "1. Compiling dt_api_shim.c..."
gcc -shared -fPIC \
    -o libdt_api_shim.so \
    dt_api_shim.c \
    -I/mnt/2t4/development/darktable/darktable/src \
    -I/mnt/2t4/development/darktable/darktable/build \
    $GLIB_CFLAGS $GTK_CFLAGS $RSVG_CFLAGS $JSON_CFLAGS \
    -L/home/glen/Applications/Darktable/lib/darktable \
    -ldarktable $GLIB_LIBS \
    -Wl,-rpath,/home/glen/Applications/Darktable/lib/darktable

echo "✓ Created libdt_api_shim.so"

# Build cffi Python extension
echo "2. Building cffi Python extension..."
python build_dt_api.py

echo ""
echo "✓ Build complete!"
echo ""
echo "Generated files:"
ls -lh libdt_api_shim.so _dt_api*.so 2>/dev/null || true
