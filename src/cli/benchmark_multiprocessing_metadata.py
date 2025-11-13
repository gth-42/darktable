#!/usr/bin/env python3
"""
Benchmark: multiprocessing.Pool for Metadata Extraction
Goal: Test if separate processes (no GIL sharing) provide speedup

Compares:
1. Serial metadata extraction
2. Parallel with multiprocessing.Pool (2, 4, 8 processes)
"""

import os
import sys
import time
import glob
from multiprocessing import Pool

try:
    import exifread
except ImportError:
    print("ERROR: exifread not installed (pip install exifread)")
    sys.exit(1)

TEST_DATA_DIR = "/mnt/2t4/development/darktable/test_data"


def extract_metadata_exifread(raw_path):
    """Extract minimal metadata using exifread (pure Python)"""
    try:
        with open(raw_path, 'rb') as f:
            tags = exifread.process_file(f, details=True)

        # Extract required fields
        maker = str(tags.get('Image Make', 'Unknown')).strip()
        model = str(tags.get('Image Model', 'Unknown')).strip()
        lens = str(tags.get('EXIF LensModel', model)).strip()

        # Dimensions
        width = tags.get('EXIF ExifImageWidth')
        height = tags.get('EXIF ExifImageLength')

        if width:
            width = int(str(width))
        else:
            width = tags.get('EXIF SubIFD0 ImageWidth')
            width = int(str(width)) if width else 0

        if height:
            height = int(str(height))
        else:
            height = tags.get('EXIF SubIFD0 ImageLength')
            height = int(str(height)) if height else 0

        # Exposure data
        focal_length = tags.get('EXIF FocalLength')
        if focal_length and hasattr(focal_length, 'values'):
            focal_length = float(focal_length.values[0])
        else:
            focal_length = 0.0

        aperture = tags.get('EXIF FNumber')
        if aperture and hasattr(aperture, 'values'):
            aperture = float(aperture.values[0])
        else:
            aperture = 0.0

        orientation = tags.get('Image Orientation')
        if orientation and hasattr(orientation, 'values'):
            orientation = int(orientation.values[0])
        else:
            orientation = 1

        return {
            'filename': os.path.basename(raw_path),
            'maker': maker,
            'model': model,
            'lens': lens,
            'width': width,
            'height': height,
            'focal_length': focal_length,
            'aperture': aperture,
            'orientation': orientation,
        }
    except Exception as e:
        return {'filename': os.path.basename(raw_path), 'error': str(e)}


def benchmark_serial(raw_files):
    """Serial metadata extraction"""
    t0 = time.time()
    results = [extract_metadata_exifread(path) for path in raw_files]
    elapsed = time.time() - t0
    return results, elapsed


def benchmark_multiprocessing(raw_files, processes=4):
    """Parallel metadata extraction with multiprocessing.Pool"""
    t0 = time.time()
    with Pool(processes=processes) as pool:
        results = pool.map(extract_metadata_exifread, raw_files)
    elapsed = time.time() - t0
    return results, elapsed


def main():
    print("="*70)
    print("multiprocessing.Pool Metadata Extraction Benchmark")
    print("="*70)

    # Find test files - repeat them to have more samples
    raw_files_base = sorted(glob.glob(os.path.join(TEST_DATA_DIR, "*.ARW")))
    if not raw_files_base:
        print(f"ERROR: No ARW files found in {TEST_DATA_DIR}")
        sys.exit(1)

    # Repeat files to get 20 samples (5 files × 4 = 20)
    raw_files = raw_files_base * 4

    print(f"\nFound {len(raw_files_base)} unique ARW files, testing with {len(raw_files)} total operations")
    print(f"(Each file processed {len(raw_files) // len(raw_files_base)} times)")

    for f in raw_files_base:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"  - {os.path.basename(f)} ({size_mb:.1f} MB)")

    print("="*70)

    # Benchmark serial
    print(f"\n[1/4] Serial extraction...")
    metadata_serial, time_serial = benchmark_serial(raw_files)
    errors_serial = sum(1 for m in metadata_serial if 'error' in m)
    print(f"  ✓ Completed in {time_serial:.3f}s")
    print(f"    Per-file: {time_serial / len(raw_files) * 1000:.2f}ms")
    if errors_serial > 0:
        print(f"    ⚠ Errors: {errors_serial}/{len(raw_files)}")

    # Benchmark multiprocessing with different process counts
    process_counts = [2, 4, 8]
    results_summary = []

    for idx, processes in enumerate(process_counts, start=2):
        print(f"\n[{idx}/4] Parallel extraction ({processes} processes)...")
        metadata_parallel, time_parallel = benchmark_multiprocessing(raw_files, processes)

        errors_parallel = sum(1 for m in metadata_parallel if 'error' in m)
        speedup = time_serial / time_parallel if time_parallel > 0 else 0

        print(f"  ✓ Completed in {time_parallel:.3f}s")
        print(f"    Per-file: {time_parallel / len(raw_files) * 1000:.2f}ms")
        print(f"    Speedup: {speedup:.2f}x")
        if errors_parallel > 0:
            print(f"    ⚠ Errors: {errors_parallel}/{len(raw_files)}")

        results_summary.append({
            'processes': processes,
            'time': time_parallel,
            'speedup': speedup
        })

    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    print(f"\nFiles: {len(raw_files)} operations ({len(raw_files_base)} unique files × {len(raw_files) // len(raw_files_base)})")
    print(f"Serial time: {time_serial:.3f}s ({time_serial/len(raw_files)*1000:.2f}ms per file)")

    print(f"\nmultiprocessing.Pool results:")
    for result in results_summary:
        efficiency = (result['speedup'] / result['processes']) * 100
        print(f"  {result['processes']:2d} processes: {result['time']:.3f}s → {result['speedup']:.2f}x speedup ({efficiency:.0f}% efficiency)")

    print(f"\n{'='*70}")
    print("Comparison to darktable dt_image_import():")
    print(f"{'='*70}")
    print("From Phase 2 benchmarks:")
    print("  Run 1 (first import): 10-23ms per file (avg 17ms)")
    print()

    if results_summary:
        best = max(results_summary, key=lambda r: r['speedup'])
        best_time_per_file = best['time'] / len(raw_files) * 1000
        dt_import_time = 17  # ms per file

        print(f"Best result: {best['processes']} processes")
        print(f"  Time per file: {best_time_per_file:.2f}ms")
        print(f"  Speedup vs serial exifread: {best['speedup']:.2f}x")
        print(f"  vs darktable import (17ms): {dt_import_time / best_time_per_file:.2f}x faster than darktable")
        print()
        print(f"For 1000 files:")
        print(f"  darktable serial import:       ~17.0s")
        print(f"  exifread serial:               ~{time_serial / len(raw_files) * 1000:.1f}s")
        print(f"  exifread multiprocessing ({best['processes']}p): ~{best_time_per_file * 1000 / 1000:.1f}s ({best['speedup']:.1f}x speedup)")

    print("="*70)
    print("✓ Benchmark complete")
    print("="*70)


if __name__ == '__main__':
    main()
