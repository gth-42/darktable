#!/usr/bin/env python3
"""
Demonstration: Export raw image from Python buffer

This demonstrates that darktable can decode and export a raw file
WITHOUT ever knowing the filename - just working with a memory buffer.

Steps:
1. Load raw file into Python bytes object
2. Pass buffer to darktable (NO filename!)
3. darktable decodes from buffer
4. darktable exports to JPEG
5. Success! File never touched by darktable.
"""

import sys
import os

# Add python_api to path
sys.path.insert(0, '/tmp/darktable/src/cli/python_api')

from _dt_api import ffi, lib

def demo_buffer_export():
    print("=" * 70)
    print("BUFFER-BASED EXPORT DEMONSTRATION")
    print("=" * 70)

    # Configuration
    input_raw = "/mnt/2t4/development/darktable/test_data/test - 3.ARW"
    output_jpg = "/tmp/buffer_demo_output.jpg"
    jpeg_quality = 95

    print(f"\nInput (raw):  {input_raw}")
    print(f"Output (jpg): {output_jpg}")
    print(f"Quality:      {jpeg_quality}")

    # ========================================================================
    # Step 1: Initialize darktable
    # ========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: Initialize darktable")
    print("=" * 70)

    argv = [
        ffi.new("char[]", b"buffer-demo"),
        ffi.new("char[]", b"--library"),
        ffi.new("char[]", b":memory:"),
        ffi.new("char[]", b"--conf"),
        ffi.new("char[]", b"write_sidecar_files=never"),
    ]
    argv_array = ffi.new("char*[]", argv)

    result = lib.dt_init(
        5, argv_array, False, True, ffi.NULL,
        b"/home/glen/Applications/Darktable/bin"
    )

    if result != 0:
        print(f"✗ dt_init failed with code {result}")
        return 1

    print("✓ darktable initialized (in-memory database)")

    # ========================================================================
    # Step 2: Load raw file into Python buffer
    # ========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: Load raw file into Python memory")
    print("=" * 70)

    print(f"Reading: {input_raw}")

    try:
        with open(input_raw, 'rb') as f:
            raw_buffer = f.read()
    except Exception as e:
        print(f"✗ Failed to read file: {e}")
        lib.dt_cleanup()
        return 2

    buffer_size = len(raw_buffer)
    print(f"✓ Loaded {buffer_size:,} bytes into Python memory")
    print(f"  Buffer type: {type(raw_buffer)}")
    print(f"  First 16 bytes (hex): {raw_buffer[:16].hex()}")

    # ========================================================================
    # Step 3: Export from buffer (NO FILENAME!)
    # ========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: Export from buffer")
    print("=" * 70)

    print("Calling darktable with buffer (no filename given)...")
    print("  → darktable will decode RawSpeed from this buffer")
    print("  → darktable will export to JPEG")
    print("  → darktable will NEVER touch the filesystem for raw data")

    result = lib.dt_shim_export_from_buffer(
        raw_buffer,              # Python bytes object → C uint8_t*
        buffer_size,             # size_t
        output_jpg.encode(),     # const char*
        jpeg_quality,            # int
        0,                       # max_width (0 = no limit)
        0                        # max_height (0 = no limit)
    )

    if result != 0:
        print(f"✗ Export failed with code {result}")
        lib.dt_cleanup()
        return 3

    print("✓ Export completed!")

    # ========================================================================
    # Step 4: Verify output
    # ========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: Verify output")
    print("=" * 70)

    if not os.path.exists(output_jpg):
        print(f"✗ Output file not created: {output_jpg}")
        lib.dt_cleanup()
        return 4

    output_size = os.path.getsize(output_jpg)
    print(f"✓ Output file created: {output_jpg}")
    print(f"  Size: {output_size:,} bytes ({output_size/1024/1024:.2f} MB)")

    # ========================================================================
    # Step 5: Cleanup
    # ========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: Cleanup")
    print("=" * 70)

    lib.dt_cleanup()
    print("✓ darktable cleaned up")

    # ========================================================================
    # Success!
    # ========================================================================
    print("\n" + "=" * 70)
    print("SUCCESS!")
    print("=" * 70)
    print()
    print("Proof that buffer-based export works:")
    print(f"  1. Python loaded raw file into memory buffer")
    print(f"  2. darktable decoded {buffer_size:,} bytes from buffer")
    print(f"  3. darktable exported {output_size:,} byte JPEG")
    print(f"  4. darktable NEVER accessed the original file")
    print()
    print(f"Open the output: {output_jpg}")
    print()

    return 0

if __name__ == "__main__":
    try:
        exit_code = demo_buffer_export()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n✗ Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(99)
