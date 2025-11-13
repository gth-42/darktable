#!/usr/bin/env python3
from _dt_api import ffi, lib

print("[TEST] Testing dt_init...")

argv = [
    ffi.new("char[]", b"/home/glen/Applications/Darktable/bin/darktable-cli"),
    ffi.new("char[]", b"--library"),
    ffi.new("char[]", b":memory:"),
    ffi.new("char[]", b"--conf"),
    ffi.new("char[]", b"write_sidecar_files=never"),
    ffi.new("char[]", b"--conf"),
    ffi.new("char[]", b"opencl=false"),
]

print("[TEST] Calling dt_init...")
ret = lib.dt_init(7, argv, False, True, ffi.NULL, ffi.NULL)
print(f"[TEST] dt_init returned: {ret}")

if ret == 0:
    print("[TEST] SUCCESS - darktable initialized!")
    lib.dt_cleanup()
    print("[TEST] Cleanup complete")
else:
    print(f"[TEST] FAILED - dt_init returned {ret}")
