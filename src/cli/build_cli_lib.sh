#!/bin/bash
# Build the dt_cli_wrapper shared library

set -e

echo "Building libdt_cli_wrapper.so..."

# Get pkg-config flags for all dependencies
GLIB_CFLAGS=$(pkg-config --cflags glib-2.0)
GLIB_LIBS=$(pkg-config --libs glib-2.0)
GTK_CFLAGS=$(pkg-config --cflags gtk+-3.0)
RSVG_CFLAGS=$(pkg-config --cflags librsvg-2.0)
JSON_CFLAGS=$(pkg-config --cflags json-glib-1.0)

# Compile the wrapper library
gcc -shared -fPIC \
    -o libdt_cli_wrapper.so \
    dt_cli_wrapper.c \
    -I/mnt/2t4/development/darktable/darktable/src \
    -I/home/glen/build \
    $GLIB_CFLAGS \
    $GTK_CFLAGS \
    $RSVG_CFLAGS \
    $JSON_CFLAGS \
    -L/home/glen/Applications/Darktable/lib/darktable \
    -ldarktable \
    $GLIB_LIBS \
    -Wl,-rpath,/home/glen/Applications/Darktable/lib/darktable

echo "Success! Created libdt_cli_wrapper.so"
ls -lh libdt_cli_wrapper.so
