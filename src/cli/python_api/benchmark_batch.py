#!/usr/bin/env python3
"""
Phase 2: Batch Processing Benchmark

Tests the Python API with multiple unique files to identify bottlenecks.
Processes each file N times to get statistical significance.
"""

import os
import time
import glob
import statistics
import csv
import sys
from _dt_api import ffi, lib

# Configuration
TEST_DATA_DIR = b"/mnt/2t4/development/darktable/test_data"
OUTPUT_DIR = b"/tmp/dt_benchmark_output"
RESULTS_CSV = "/tmp/dt_benchmark_results.csv"
RESULTS_REPORT = "/tmp/dt_benchmark_report.txt"
NUM_RUNS = 3  # Process each file this many times
OUTPUT_WIDTH = 1920
OUTPUT_HEIGHT = 1080

class TeeOutput:
    """Write to both stdout and file simultaneously"""
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, 'w')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()

def get_test_files():
    """Get all ARW files and check for XMP sidecars"""
    arw_files = glob.glob("/mnt/2t4/development/darktable/test_data/*.ARW")
    arw_files += glob.glob("/mnt/2t4/development/darktable/test_data/*.arw")

    files = []
    for arw in sorted(arw_files):
        has_xmp = os.path.exists(arw + ".xmp")
        files.append({
            'path': arw.encode(),
            'name': os.path.basename(arw),
            'has_xmp': has_xmp
        })
    return files

def init_darktable():
    """Initialize darktable once"""
    argv = [
        ffi.new("char[]", b"darktable-benchmark"),
        ffi.new("char[]", b"--library"),
        ffi.new("char[]", b":memory:"),
        ffi.new("char[]", b"--conf"),
        ffi.new("char[]", b"write_sidecar_files=never"),
    ]
    argv_array = ffi.new("char*[]", argv)

    result = lib.dt_init(5, argv_array, False, True, ffi.NULL,
                         b"/home/glen/Applications/Darktable/bin")
    return result == 0

def process_image(input_path, output_path):
    """Process a single image and return timing breakdown"""
    times = {}

    # Get directory for film
    directory = os.path.dirname(input_path.decode()).encode()

    # Time: Film creation
    t0 = time.perf_counter()
    filmid = lib.dt_shim_film_new(directory)
    times['film_new'] = time.perf_counter() - t0

    if not lib.dt_is_valid_filmid(filmid):
        return None

    # Time: Image import
    t0 = time.perf_counter()
    imgid = lib.dt_image_import(filmid, input_path, True, True)
    times['import'] = time.perf_counter() - t0

    if not lib.dt_is_valid_imgid(imgid):
        return None

    # Time: Export setup (modules + config)
    t0 = time.perf_counter()
    format_mod = lib.dt_imageio_get_format_by_name(b"jpeg")
    storage_mod = lib.dt_imageio_get_storage_by_name(b"disk")

    if not format_mod or not storage_mod:
        return None

    fdata = lib.dt_shim_format_get_params(format_mod)
    sdata = lib.dt_shim_storage_get_params(storage_mod)

    if not fdata or not sdata:
        return None

    lib.dt_shim_configure_export(sdata, fdata, output_path,
                                  OUTPUT_WIDTH, OUTPUT_HEIGHT)
    times['export_setup'] = time.perf_counter() - t0

    # Time: Actual export (processing)
    t0 = time.perf_counter()
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
    times['export'] = time.perf_counter() - t0

    # Cleanup
    lib.dt_shim_storage_finalize(storage_mod, sdata)
    lib.dt_shim_storage_free_params(storage_mod, sdata)
    lib.dt_shim_format_free_params(format_mod, fdata)

    times['success'] = (export_result == 0)
    times['total'] = sum(v for k, v in times.items() if k != 'success')

    return times

def main():
    # Set up output tee (stdout + file)
    tee = TeeOutput(RESULTS_REPORT)
    original_stdout = sys.stdout
    sys.stdout = tee

    print("=" * 70)
    print("Phase 2: Batch Processing Benchmark")
    print("=" * 70)
    print(f"\nResults will be saved to:")
    print(f"  Report: {RESULTS_REPORT}")
    print(f"  CSV:    {RESULTS_CSV}")

    # Get test files
    test_files = get_test_files()
    print(f"\nFound {len(test_files)} test files:")
    for f in test_files:
        xmp_status = "with XMP" if f['has_xmp'] else "no XMP"
        print(f"  - {f['name']} ({xmp_status})")

    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR.decode(), exist_ok=True)

    # Prepare CSV file
    csv_file = open(RESULTS_CSV, 'w', newline='')
    csv_writer = csv.DictWriter(csv_file, fieldnames=[
        'run', 'filename', 'has_xmp', 'film_new', 'import',
        'export_setup', 'export', 'total', 'success'
    ])
    csv_writer.writeheader()

    # Initialize darktable ONCE
    print(f"\nInitializing darktable...")
    t0 = time.perf_counter()
    if not init_darktable():
        print("✗ Failed to initialize darktable")
        return 1
    init_time = time.perf_counter() - t0
    print(f"✓ Initialized in {init_time:.3f}s (one-time cost)")

    # Process each file NUM_RUNS times
    print(f"\nProcessing each file {NUM_RUNS} times...")
    print(f"Total operations: {len(test_files)} files × {NUM_RUNS} runs = {len(test_files) * NUM_RUNS}")
    print()

    all_results = []

    for run in range(NUM_RUNS):
        print(f"Run {run + 1}/{NUM_RUNS}:")
        for file_info in test_files:
            input_path = file_info['path']
            output_name = f"run{run+1}_{file_info['name']}.jpg".encode()
            output_path = os.path.join(OUTPUT_DIR.decode(),
                                      output_name.decode()).encode()

            times = process_image(input_path, output_path)

            if times and times['success']:
                result_row = {
                    'run': run + 1,
                    'filename': file_info['name'],
                    'has_xmp': file_info['has_xmp'],
                    'film_new': times['film_new'],
                    'import': times['import'],
                    'export_setup': times['export_setup'],
                    'export': times['export'],
                    'total': times['total'],
                    'success': True
                }
                all_results.append({
                    **file_info,
                    **times,
                    'run': run + 1
                })
                csv_writer.writerow(result_row)
                csv_file.flush()  # Flush after each write so you can tail it
                print(f"  ✓ {file_info['name']:20s} "
                      f"total={times['total']:.3f}s "
                      f"(film={times['film_new']:.3f}s, "
                      f"import={times['import']:.3f}s, "
                      f"setup={times['export_setup']:.3f}s, "
                      f"export={times['export']:.3f}s)")
            else:
                csv_writer.writerow({
                    'run': run + 1,
                    'filename': file_info['name'],
                    'has_xmp': file_info['has_xmp'],
                    'success': False
                })
                csv_file.flush()
                print(f"  ✗ {file_info['name']:20s} FAILED")

    # Cleanup darktable
    print("\nCleaning up...")
    lib.dt_cleanup()

    # Analyze results
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    if not all_results:
        print("No successful runs to analyze")
        return 1

    # Overall statistics
    total_images = len(all_results)
    avg_total = sum(r['total'] for r in all_results) / total_images
    avg_film = sum(r['film_new'] for r in all_results) / total_images
    avg_import = sum(r['import'] for r in all_results) / total_images
    avg_setup = sum(r['export_setup'] for r in all_results) / total_images
    avg_export = sum(r['export'] for r in all_results) / total_images

    # Calculate standard deviations
    std_total = statistics.stdev([r['total'] for r in all_results]) if len(all_results) > 1 else 0
    std_film = statistics.stdev([r['film_new'] for r in all_results]) if len(all_results) > 1 else 0
    std_import = statistics.stdev([r['import'] for r in all_results]) if len(all_results) > 1 else 0
    std_export = statistics.stdev([r['export'] for r in all_results]) if len(all_results) > 1 else 0

    print(f"\nProcessed: {total_images} images")
    print(f"Init time: {init_time:.3f}s (one-time overhead)")
    print(f"\nPer-image averages (± std dev):")
    print(f"  Total:        {avg_total:.4f}s (±{std_total:.4f}s)")
    print(f"  Film new:     {avg_film:.6f}s (±{std_film:.6f}s) ({avg_film/avg_total*100:.1f}%)")
    print(f"  Import:       {avg_import:.6f}s (±{std_import:.6f}s) ({avg_import/avg_total*100:.1f}%)")
    print(f"  Export setup: {avg_setup:.6f}s ({avg_setup/avg_total*100:.1f}%)")
    print(f"  Export:       {avg_export:.4f}s (±{std_export:.4f}s) ({avg_export/avg_total*100:.1f}%)")

    # XMP comparison
    with_xmp = [r for r in all_results if r['has_xmp']]
    without_xmp = [r for r in all_results if not r['has_xmp']]

    if with_xmp and without_xmp:
        print(f"\nXMP sidecar effect:")
        avg_with = sum(r['total'] for r in with_xmp) / len(with_xmp)
        avg_without = sum(r['total'] for r in without_xmp) / len(without_xmp)
        print(f"  With XMP:    {avg_with:.3f}s (n={len(with_xmp)})")
        print(f"  Without XMP: {avg_without:.3f}s (n={len(without_xmp)})")
        diff = avg_with - avg_without
        print(f"  Difference:  {diff:+.3f}s ({diff/avg_without*100:+.1f}%)")

    # Identify bottleneck
    print(f"\nBottleneck identification:")
    operations = {
        'film_new': avg_film,
        'import': avg_import,
        'export_setup': avg_setup,
        'export': avg_export
    }
    bottleneck = max(operations, key=operations.get)
    print(f"  Slowest operation: {bottleneck} ({operations[bottleneck]:.3f}s)")

    if avg_import > avg_total * 0.3:
        print(f"  ⚠️  Import takes {avg_import/avg_total*100:.0f}% of time - likely database/duplicate checking")
    if avg_export > avg_total * 0.5:
        print(f"  ℹ️  Export takes {avg_export/avg_total*100:.0f}% of time - this is expected (actual processing)")
    if avg_film > 0.1:
        print(f"  ⚠️  Film creation is slow ({avg_film:.3f}s) - consider reusing films")

    # Per-file breakdown
    print(f"\nPer-file statistics (across {NUM_RUNS} runs):")
    for file_info in test_files:
        file_results = [r for r in all_results if r['name'] == file_info['name']]
        if file_results:
            file_times = [r['total'] for r in file_results]
            file_avg = statistics.mean(file_times)
            file_std = statistics.stdev(file_times) if len(file_times) > 1 else 0
            xmp_marker = " (XMP)" if file_info['has_xmp'] else ""
            print(f"  {file_info['name']:20s}{xmp_marker:6s}: "
                  f"{file_avg:.4f}s ±{file_std:.4f}s  "
                  f"[{min(file_times):.4f}s - {max(file_times):.4f}s]")

    print("\n" + "=" * 70)
    print(f"✓ Benchmark complete")
    print(f"\nResults saved to:")
    print(f"  Report: {RESULTS_REPORT}")
    print(f"  CSV:    {RESULTS_CSV}")
    print(f"  Images: {OUTPUT_DIR.decode()}")
    print("=" * 70)

    # Close files
    csv_file.close()
    sys.stdout = original_stdout
    tee.close()

    return 0

if __name__ == "__main__":
    exit(main())
