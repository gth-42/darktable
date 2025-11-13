#!/usr/bin/env python3
"""
Test the dt_cli_process_simple cffi wrapper - Phase 1.
No launcher needed - applicationdir passed directly to dt_init!
"""

import os
from _dt_cli_wrapper import lib

def test_process_image():
    input_path = b"/mnt/2t4/development/darktable/test_data/test - 3.ARW"
    output_path = b"/tmp/test_output.jpg"
    width = 1920
    height = 1080

    print("=" * 60)
    print("Phase 1 cffi Wrapper Test")
    print("=" * 60)
    print(f"Input:  {input_path.decode()}")
    print(f"Output: {output_path.decode()}")
    print(f"Size:   {width}x{height}")
    print("-" * 60)

    # Call the C function through cffi
    result = lib.dt_cli_process_simple(input_path, output_path, width, height)

    print("-" * 60)
    if result == 0:
        print("✓ SUCCESS: Image processed without errors")
        # Check if output file exists
        if os.path.exists(output_path.decode()):
            size = os.path.getsize(output_path.decode())
            print(f"✓ Output file created: {size:,} bytes")
        else:
            print("✗ WARNING: No output file found")
            result = 99
    else:
        print(f"✗ ERROR: Processing failed with code {result}")

    print("=" * 60)
    return result

if __name__ == "__main__":
    exit_code = test_process_image()
    exit(exit_code)
