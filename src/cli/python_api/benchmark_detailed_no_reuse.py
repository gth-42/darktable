#!/usr/bin/env python3
"""
Phase 2: Detailed Benchmark WITHOUT State Reuse

Measures every operation with high granularity to understand time proportions.
Init+process+cleanup FOR EACH IMAGE (darktable-cli pattern).
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
OUTPUT_DIR = b"/tmp/dt_benchmark_output_detailed_no_reuse"
RESULTS_CSV = "/tmp/dt_benchmark_detailed_no_state_reuse.csv"
RESULTS_REPORT = "/tmp/dt_benchmark_detailed_no_state_reuse.txt"
NUM_RUNS = 3
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

def process_image_full_cycle(input_path, output_path):
    """Process image with full init/cleanup cycle - detailed timing"""
    times = {}
    directory = os.path.dirname(input_path.decode()).encode()

    # 1. Initialize darktable
    t0 = time.perf_counter()
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
    times['dt_init'] = time.perf_counter() - t0

    if result != 0:
        times['success'] = False
        return times

    # 2. Film creation
    t0 = time.perf_counter()
    filmid = lib.dt_shim_film_new(directory)
    times['film_new'] = time.perf_counter() - t0

    if not lib.dt_is_valid_filmid(filmid):
        lib.dt_cleanup()
        times['success'] = False
        return times

    # 3. Image import
    t0 = time.perf_counter()
    imgid = lib.dt_image_import(filmid, input_path, True, True)
    times['import'] = time.perf_counter() - t0

    if not lib.dt_is_valid_imgid(imgid):
        lib.dt_cleanup()
        times['success'] = False
        return times

    # 4. Get export modules
    t0 = time.perf_counter()
    format_mod = lib.dt_imageio_get_format_by_name(b"jpeg")
    storage_mod = lib.dt_imageio_get_storage_by_name(b"disk")
    times['module_lookup'] = time.perf_counter() - t0

    if not format_mod or not storage_mod:
        lib.dt_cleanup()
        times['success'] = False
        return times

    # 5. Get module parameters
    t0 = time.perf_counter()
    fdata = lib.dt_shim_format_get_params(format_mod)
    sdata = lib.dt_shim_storage_get_params(storage_mod)
    times['module_params'] = time.perf_counter() - t0

    if not fdata or not sdata:
        lib.dt_cleanup()
        times['success'] = False
        return times

    # 6. Configure export
    t0 = time.perf_counter()
    lib.dt_shim_configure_export(sdata, fdata, output_path,
                                  OUTPUT_WIDTH, OUTPUT_HEIGHT)
    times['configure_export'] = time.perf_counter() - t0

    # 7. Actual export (processing)
    t0 = time.perf_counter()
    export_result = lib.dt_shim_storage_store(
        storage_mod, sdata, imgid, format_mod, fdata,
        1, 1, True, False, False, 1, ffi.NULL, 0
    )
    times['export_processing'] = time.perf_counter() - t0

    # 8. Export cleanup
    t0 = time.perf_counter()
    lib.dt_shim_storage_finalize(storage_mod, sdata)
    lib.dt_shim_storage_free_params(storage_mod, sdata)
    lib.dt_shim_format_free_params(format_mod, fdata)
    times['export_cleanup'] = time.perf_counter() - t0

    # 9. Cleanup darktable
    t0 = time.perf_counter()
    lib.dt_cleanup()
    times['dt_cleanup'] = time.perf_counter() - t0

    times['success'] = (export_result == 0)
    times['total'] = sum(v for k, v in times.items() if k != 'success')

    return times

def main():
    # Set up output tee
    tee = TeeOutput(RESULTS_REPORT)
    original_stdout = sys.stdout
    sys.stdout = tee

    print("=" * 70)
    print("Phase 2: Detailed Benchmark WITHOUT State Reuse")
    print("(darktable-cli pattern: init+process+cleanup per image)")
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

    os.makedirs(OUTPUT_DIR.decode(), exist_ok=True)

    # Prepare CSV
    csv_file = open(RESULTS_CSV, 'w', newline='')
    csv_writer = csv.DictWriter(csv_file, fieldnames=[
        'run', 'filename', 'has_xmp',
        'dt_init', 'film_new', 'import', 'module_lookup', 'module_params',
        'configure_export', 'export_processing', 'export_cleanup', 'dt_cleanup',
        'total', 'success'
    ])
    csv_writer.writeheader()

    print(f"\n{'='*70}")
    print(f"PROCESSING IMAGES (NO State Reuse - Full Cycle Each Time)")
    print(f"{'='*70}")
    print(f"Processing each file {NUM_RUNS} times...")
    print(f"Total operations: {len(test_files)} files × {NUM_RUNS} runs = {len(test_files) * NUM_RUNS}\n")

    all_results = []

    for run in range(NUM_RUNS):
        print(f"Run {run + 1}/{NUM_RUNS}:")
        for file_info in test_files:
            input_path = file_info['path']
            output_name = f"run{run+1}_{file_info['name']}.jpg".encode()
            output_path = os.path.join(OUTPUT_DIR.decode(),
                                      output_name.decode()).encode()

            times = process_image_full_cycle(input_path, output_path)

            if times and times['success']:
                result_row = {
                    'run': run + 1,
                    'filename': file_info['name'],
                    'has_xmp': file_info['has_xmp'],
                    'dt_init': times['dt_init'],
                    'film_new': times['film_new'],
                    'import': times['import'],
                    'module_lookup': times['module_lookup'],
                    'module_params': times['module_params'],
                    'configure_export': times['configure_export'],
                    'export_processing': times['export_processing'],
                    'export_cleanup': times['export_cleanup'],
                    'dt_cleanup': times['dt_cleanup'],
                    'total': times['total'],
                    'success': True
                }
                all_results.append({**file_info, **times, 'run': run + 1})
                csv_writer.writerow(result_row)
                csv_file.flush()

                print(f"  ✓ {file_info['name']:20s} total={times['total']:.3f}s")
                print(f"      init={times['dt_init']:.3f}s, film={times['film_new']:.6f}s, "
                      f"import={times['import']:.6f}s, lookup={times['module_lookup']:.6f}s")
                print(f"      params={times['module_params']:.6f}s, config={times['configure_export']:.6f}s, "
                      f"export={times['export_processing']:.3f}s")
                print(f"      exp_cleanup={times['export_cleanup']:.6f}s, cleanup={times['dt_cleanup']:.3f}s")
            else:
                csv_writer.writerow({
                    'run': run + 1,
                    'filename': file_info['name'],
                    'has_xmp': file_info['has_xmp'],
                    'success': False
                })
                csv_file.flush()
                print(f"  ✗ {file_info['name']:20s} FAILED")

    # ====================================================================
    # ANALYSIS
    # ====================================================================
    print("\n" + "=" * 70)
    print("DETAILED TIMING ANALYSIS")
    print("=" * 70)

    if not all_results:
        print("No successful runs to analyze")
        csv_file.close()
        sys.stdout = original_stdout
        tee.close()
        return 1

    total_images = len(all_results)

    # Calculate averages and std devs for each operation
    operations = ['dt_init', 'film_new', 'import', 'module_lookup', 'module_params',
                  'configure_export', 'export_processing', 'export_cleanup', 'dt_cleanup', 'total']

    stats = {}
    for op in operations:
        values = [r[op] for r in all_results]
        stats[op] = {
            'mean': statistics.mean(values),
            'stdev': statistics.stdev(values) if len(values) > 1 else 0,
            'min': min(values),
            'max': max(values)
        }

    print(f"\nProcessed: {total_images} images")

    print(f"\nPer-image timing (mean ± stdev) [min - max]:")
    for op in operations:
        s = stats[op]
        pct = (s['mean'] / stats['total']['mean'] * 100) if op != 'total' else 100
        print(f"  {op:20s}: {s['mean']:.6f}s ±{s['stdev']:.6f}s  "
              f"[{s['min']:.6f}s - {s['max']:.6f}s]  ({pct:.1f}%)")

    # Overhead analysis
    avg_init = stats['dt_init']['mean']
    avg_cleanup = stats['dt_cleanup']['mean']
    avg_processing = stats['total']['mean'] - avg_init - avg_cleanup
    avg_export = stats['export_processing']['mean']

    print(f"\n{'='*70}")
    print("OVERHEAD BREAKDOWN (per image)")
    print(f"{'='*70}")
    print(f"  Init overhead:       {avg_init:.6f}s  ({avg_init/stats['total']['mean']*100:.1f}%)")
    print(f"  Processing work:     {avg_processing:.6f}s  ({avg_processing/stats['total']['mean']*100:.1f}%)")
    print(f"    (of which export:  {avg_export:.6f}s)  ({avg_export/stats['total']['mean']*100:.1f}%)")
    print(f"  Cleanup overhead:    {avg_cleanup:.6f}s  ({avg_cleanup/stats['total']['mean']*100:.1f}%)")
    print(f"  {'─'*68}")
    print(f"  TOTAL:               {stats['total']['mean']:.6f}s  (100.0%)")
    print(f"\n  Total overhead per image: {avg_init + avg_cleanup:.6f}s  "
          f"({(avg_init + avg_cleanup)/stats['total']['mean']*100:.1f}%)")

    # XMP comparison
    with_xmp = [r for r in all_results if r['has_xmp']]
    without_xmp = [r for r in all_results if not r['has_xmp']]

    if with_xmp and without_xmp:
        print(f"\n{'='*70}")
        print("XMP SIDECAR EFFECT")
        print(f"{'='*70}")
        avg_with = statistics.mean([r['total'] for r in with_xmp])
        avg_without = statistics.mean([r['total'] for r in without_xmp])
        print(f"  With XMP:    {avg_with:.3f}s (n={len(with_xmp)})")
        print(f"  Without XMP: {avg_without:.3f}s (n={len(without_xmp)})")
        print(f"  Difference:  {avg_with - avg_without:+.3f}s ({(avg_with/avg_without - 1)*100:+.1f}%)")

    print("\n" + "=" * 70)
    print(f"✓ Benchmark complete")
    print(f"\nResults saved to:")
    print(f"  Report: {RESULTS_REPORT}")
    print(f"  CSV:    {RESULTS_CSV}")
    print(f"  Images: {OUTPUT_DIR.decode()}")
    print("=" * 70)

    csv_file.close()
    sys.stdout = original_stdout
    tee.close()

    return 0

if __name__ == "__main__":
    exit(main())
