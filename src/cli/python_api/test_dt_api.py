#!/usr/bin/env python3
"""
Test the darktable Python API

This tests the full workflow: init -> import -> export -> cleanup
"""

import os
from _dt_api import ffi, lib

def test_basic_workflow():
    """Test basic init/import/export/cleanup"""
    print("=" * 70)
    print("darktable Python API Test")
    print("=" * 70)

    # 1. Initialize darktable
    print("\n1. Initializing darktable...")
    argv = [
        ffi.new("char[]", b"darktable-api"),
        ffi.new("char[]", b"--library"),
        ffi.new("char[]", b":memory:"),
        ffi.new("char[]", b"--conf"),
        ffi.new("char[]", b"write_sidecar_files=never"),
    ]
    argv_array = ffi.new("char*[]", argv)

    result = lib.dt_init(5, argv_array, False, True, ffi.NULL,
                         b"/home/glen/Applications/Darktable/bin")
    if result != 0:
        print(f"✗ dt_init failed with code {result}")
        return 1
    print("✓ darktable initialized")

    # 2. Import image
    print("\n2. Importing image...")
    input_path = b"/mnt/2t4/development/darktable/test_data/test - 3.ARW"

    if not lib.dt_supported_image(input_path):
        print(f"✗ Image format not supported: {input_path.decode()}")
        lib.dt_cleanup()
        return 2

    directory = os.path.dirname(input_path.decode()).encode()
    filmid = lib.dt_shim_film_new(directory)

    if not lib.dt_is_valid_filmid(filmid):
        print(f"✗ Failed to create film for {directory.decode()}")
        lib.dt_cleanup()
        return 3

    imgid = lib.dt_image_import(filmid, input_path, True, True)
    if not lib.dt_is_valid_imgid(imgid):
        print(f"✗ Failed to import image")
        lib.dt_cleanup()
        return 4
    print(f"✓ Image imported (imgid={imgid})")

    # 3. Setup export
    print("\n3. Setting up export modules...")
    format_mod = lib.dt_imageio_get_format_by_name(b"jpeg")
    storage_mod = lib.dt_imageio_get_storage_by_name(b"disk")

    if not format_mod or not storage_mod:
        print("✗ Failed to get format/storage modules")
        lib.dt_cleanup()
        return 5

    fdata = lib.dt_shim_format_get_params(format_mod)
    sdata = lib.dt_shim_storage_get_params(storage_mod)

    if not fdata or not sdata:
        print("✗ Failed to get module parameters")
        lib.dt_cleanup()
        return 6
    print("✓ Export modules configured")

    # 4. Configure output
    print("\n4. Configuring export...")
    output_path = b"/tmp/test_dt_api_output.jpg"
    lib.dt_shim_configure_export(sdata, fdata, output_path, 1920, 1080)
    print(f"✓ Output: {output_path.decode()} (1920x1080)")

    # 5. Export
    print("\n5. Exporting image...")
    export_result = lib.dt_shim_storage_store(
        storage_mod, sdata, imgid, format_mod, fdata,
        1, 1,          # num, total
        True,          # high_quality
        False,         # allow_upscale
        False,         # export_masks
        1,             # DT_COLORSPACE_SRGB
        ffi.NULL,      # icc_file
        0              # DT_INTENT_PERCEPTUAL
    )

    if export_result != 0:
        print(f"✗ Export failed with code {export_result}")
    else:
        print("✓ Export completed")
        if os.path.exists(output_path.decode()):
            size = os.path.getsize(output_path.decode())
            print(f"✓ Output file created: {size:,} bytes")
        else:
            print("✗ Output file not found!")
            export_result = 99

    # 6. Cleanup
    print("\n6. Cleaning up...")
    lib.dt_shim_storage_finalize(storage_mod, sdata)
    lib.dt_shim_storage_free_params(storage_mod, sdata)
    lib.dt_shim_format_free_params(format_mod, fdata)
    lib.dt_cleanup()
    print("✓ Cleanup complete")

    # Final result
    print("\n" + "=" * 70)
    if export_result == 0:
        print("✓ SUCCESS: Full workflow completed!")
    else:
        print(f"✗ FAILED: Export returned code {export_result}")
    print("=" * 70)

    return export_result

if __name__ == "__main__":
    exit(test_basic_workflow())
