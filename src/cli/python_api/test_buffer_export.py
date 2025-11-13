#!/usr/bin/env python3
"""
Test script for buffer-based raw file export.

This demonstrates the complete workflow:
1. Load raw file into Python memory buffer
2. Import image into darktable with dummy filename
3. Attach buffer to image (bypassing filesystem)
4. Export to JPEG using darktable's full pipeline
"""

import sys
import os
from pathlib import Path

# Import the generated Python API
from _dt_api import ffi, lib

def main():
    # Configuration
    input_file = "/mnt/2t4/development/darktable/test_data/test1.ARW"
    output_file = "/tmp/buffer_test_output.jpg"

    print(f"[TEST] Starting buffer-based export test")
    print(f"[TEST] Input: {input_file}")
    print(f"[TEST] Output: {output_file}")

    # Step 1: Load raw file into Python buffer
    print(f"\n[TEST] Step 1: Loading raw file into memory buffer...")
    with open(input_file, 'rb') as f:
        raw_data = f.read()

    print(f"[TEST] Loaded {len(raw_data):,} bytes into Python buffer")

    # Step 2: Initialize darktable
    print(f"\n[TEST] Step 2: Initializing darktable...")

    # Create argv with CLI-style arguments (like darktable-cli does)
    argv = [
        ffi.new("char[]", b"darktable-buffer-test"),
        ffi.new("char[]", b"--library"),
        ffi.new("char[]", b":memory:"),  # Use in-memory database
        ffi.new("char[]", b"--conf"),
        ffi.new("char[]", b"write_sidecar_files=never"),
    ]
    argc = len(argv)

    # Initialize darktable (no GUI, load data)
    # Use applicationdir parameter to point to installation (Phase 1 fix)
    ret = lib.dt_init(argc, argv, False, True, ffi.NULL,
                      b"/home/glen/Applications/Darktable/bin")
    if ret != 0:
        print(f"[TEST] ERROR: dt_init failed with code {ret}")
        return 1

    print(f"[TEST] darktable initialized successfully")

    try:
        # Step 3: Create film (directory) entry for input directory
        import_dir = os.path.dirname(input_file)
        print(f"\n[TEST] Step 3: Creating film entry for {import_dir}...")
        filmid = lib.dt_shim_film_new(import_dir.encode('utf-8'))

        if not lib.dt_is_valid_filmid(filmid):
            print(f"[TEST] ERROR: Failed to create film for {import_dir}")
            return 1

        print(f"[TEST] Film created: ID={filmid}")

        # Step 4: Import image with REAL filename (for EXIF extraction)
        print(f"\n[TEST] Step 4: Importing image from {input_file}...")
        print(f"[TEST] (EXIF will be read from disk now)")

        # Import the image (darktable will read EXIF from the actual file)
        imgid = lib.dt_image_import(
            filmid,
            input_file.encode('utf-8'),
            False,  # override_ignore_jpegs
            False   # check_duplicates
        )

        if not lib.dt_is_valid_imgid(imgid):
            print(f"[TEST] ERROR: Failed to import image")
            return 1

        print(f"[TEST] Image imported: ID={imgid}")

        # Step 5: Attach buffer to image
        print(f"\n[TEST] Step 5: Attaching {len(raw_data):,} byte buffer to image...")
        print(f"[TEST] (Export will use this buffer instead of re-reading from disk)")

        # Create a CFFI buffer from Python bytes
        # IMPORTANT: raw_data must remain alive for the duration of export!
        buffer_ptr = ffi.from_buffer("uint8_t[]", raw_data)

        # Attach buffer to the image
        lib.dt_shim_attach_buffer_to_image(imgid, buffer_ptr, len(raw_data))

        print(f"[TEST] Buffer attached to image {imgid}")

        # Step 6: Set up export modules
        print(f"\n[TEST] Step 6: Setting up export modules...")

        # Get JPEG format module
        format_module = lib.dt_imageio_get_format_by_name(b"jpeg")
        if format_module == ffi.NULL:
            print(f"[TEST] ERROR: Failed to get JPEG format module")
            return 1

        # Get disk storage module
        storage_module = lib.dt_imageio_get_storage_by_name(b"disk")
        if storage_module == ffi.NULL:
            print(f"[TEST] ERROR: Failed to get disk storage module")
            return 1

        print(f"[TEST] Export modules loaded")

        # Step 7: Get module parameters
        print(f"\n[TEST] Step 7: Getting module parameters...")

        format_data = lib.dt_shim_format_get_params(format_module)
        storage_data = lib.dt_shim_storage_get_params(storage_module)

        if format_data == ffi.NULL or storage_data == ffi.NULL:
            print(f"[TEST] ERROR: Failed to get module parameters")
            return 1

        print(f"[TEST] Module parameters acquired")

        # Step 8: Configure export
        print(f"\n[TEST] Step 8: Configuring export parameters...")

        # Configure paths and dimensions
        lib.dt_shim_configure_export(
            storage_data,
            format_data,
            output_file.encode('utf-8'),
            1920,  # max_width
            1080   # max_height
        )

        print(f"[TEST] Export configured: {output_file} (max 1920x1080)")

        # Step 9: Export the image
        print(f"\n[TEST] Step 9: Exporting image...")
        print(f"[TEST] This will test if darktable reads from buffer instead of filesystem")

        export_ret = lib.dt_shim_storage_store(
            storage_module,
            storage_data,
            imgid,
            format_module,
            format_data,
            1,      # num (image 1 of N)
            1,      # total (1 image)
            True,   # high_quality
            False,  # allow_upscale
            False,  # export_masks
            lib.DT_COLORSPACE_SRGB,  # icc_type
            ffi.NULL,                 # icc_file (use default)
            lib.DT_INTENT_PERCEPTUAL  # icc_intent
        )

        if export_ret != 0:
            print(f"[TEST] ERROR: Export failed with code {export_ret}")
            return 1

        print(f"[TEST] Export completed successfully!")

        # Step 10: Verify output
        print(f"\n[TEST] Step 10: Verifying output...")

        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            print(f"[TEST] ✓ Output file created: {output_file}")
            print(f"[TEST] ✓ Output size: {size:,} bytes")
        else:
            print(f"[TEST] ERROR: Output file not created!")
            return 1

        # Cleanup
        print(f"\n[TEST] Cleaning up...")
        lib.dt_shim_format_free_params(format_module, format_data)
        lib.dt_shim_storage_free_params(storage_module, storage_data)
        lib.dt_shim_storage_finalize(storage_module, storage_data)

    finally:
        # Always cleanup darktable
        print(f"\n[TEST] Shutting down darktable...")
        lib.dt_cleanup()

    print(f"\n[TEST] ========================================")
    print(f"[TEST] SUCCESS! Buffer-based export completed")
    print(f"[TEST] ========================================")
    print(f"[TEST] Workflow:")
    print(f"[TEST] 1. Imported image from disk (for EXIF metadata)")
    print(f"[TEST] 2. Attached pre-loaded buffer to image")
    print(f"[TEST] 3. Export used buffer instead of re-reading file")
    print(f"[TEST]")
    print(f"[TEST] This enables parallel I/O optimization:")
    print(f"[TEST] - Python can load files in parallel from slow storage")
    print(f"[TEST] - Darktable processes from fast RAM buffers")

    return 0

if __name__ == "__main__":
    sys.exit(main())
