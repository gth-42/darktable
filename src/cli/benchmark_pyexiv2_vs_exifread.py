#!/usr/bin/env python3
"""
Benchmark: pyexiv2 vs exifread with multiprocessing
Goal: Test if Exiv2 bindings can achieve 8x speedup vs darktable

Compares:
1. exifread serial and multiprocessing (from previous tests)
2. pyexiv2 serial
3. pyexiv2 with multiprocessing.Pool
4. vs darktable baseline (17ms per file)
"""

import os
import sys
import time
import glob
from multiprocessing import Pool

try:
    import pyexiv2
    HAS_PYEXIV2 = True
except ImportError:
    HAS_PYEXIV2 = False
    print("ERROR: pyexiv2 not installed (pip install pyexiv2)")
    sys.exit(1)

try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False
    print("WARNING: exifread not installed for comparison")

TEST_DATA_DIR = "/mnt/2t4/development/darktable/test_data"


def extract_metadata_pyexiv2(raw_path):
    """Extract minimal metadata using pyexiv2 (Exiv2 bindings)"""
    try:
        img = pyexiv2.Image(raw_path)
        data = img.read_exif()

        # Extract required fields
        maker = data.get('Exif.Image.Make', 'Unknown').strip()
        model = data.get('Exif.Image.Model', 'Unknown').strip()
        lens = data.get('Exif.Photo.LensModel', model).strip()

        # Dimensions
        width = int(data.get('Exif.Photo.PixelXDimension', 0))
        height = int(data.get('Exif.Photo.PixelYDimension', 0))

        # Exposure data
        focal_str = data.get('Exif.Photo.FocalLength', '0/1')
        if '/' in focal_str:
            num, denom = focal_str.split('/')
            focal_length = float(num) / float(denom) if float(denom) != 0 else 0.0
        else:
            focal_length = float(focal_str)

        aperture_str = data.get('Exif.Photo.FNumber', '0/1')
        if '/' in aperture_str:
            num, denom = aperture_str.split('/')
            aperture = float(num) / float(denom) if float(denom) != 0 else 0.0
        else:
            aperture = float(aperture_str)

        orientation = int(data.get('Exif.Image.Orientation', 1))

        img.close()

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


def extract_metadata_exifread(raw_path):
    """Extract minimal metadata using exifread (for comparison)"""
    try:
        with open(raw_path, 'rb') as f:
            tags = exifread.process_file(f, details=True)

        maker = str(tags.get('Image Make', 'Unknown')).strip()
        model = str(tags.get('Image Model', 'Unknown')).strip()
        lens = str(tags.get('EXIF LensModel', model)).strip()

        width = tags.get('EXIF ExifImageWidth')
        height = tags.get('EXIF ExifImageLength')
        width = int(str(width)) if width else 0
        height = int(str(height)) if height else 0

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


def benchmark_serial(raw_files, method='pyexiv2'):
    """Serial metadata extraction"""
    extract_func = extract_metadata_pyexiv2 if method == 'pyexiv2' else extract_metadata_exifread

    t0 = time.time()
    results = [extract_func(path) for path in raw_files]
    elapsed = time.time() - t0
    return results, elapsed


def benchmark_multiprocessing(raw_files, method='pyexiv2', processes=4):
    """Parallel metadata extraction with multiprocessing.Pool"""
    extract_func = extract_metadata_pyexiv2 if method == 'pyexiv2' else extract_metadata_exifread

    t0 = time.time()
    with Pool(processes=processes) as pool:
        results = pool.map(extract_func, raw_files)
    elapsed = time.time() - t0
    return results, elapsed


def main():
    print("="*70)
    print("pyexiv2 vs exifread Benchmark")
    print("="*70)

    # Find test files - repeat to get more samples
    raw_files_base = sorted(glob.glob(os.path.join(TEST_DATA_DIR, "*.ARW")))
    if not raw_files_base:
        print(f"ERROR: No ARW files found in {TEST_DATA_DIR}")
        sys.exit(1)

    # Repeat files to get 20 samples
    raw_files = raw_files_base * 4

    print(f"\nFound {len(raw_files_base)} unique ARW files, testing with {len(raw_files)} total operations")
    for f in raw_files_base:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"  - {os.path.basename(f)} ({size_mb:.1f} MB)")

    print("="*70)

    # Test each library
    results_all = []

    # pyexiv2 tests
    print(f"\n{'='*70}")
    print(f"Method: PYEXIV2 (Exiv2 C++ bindings)")
    print(f"{'='*70}")

    # Serial
    print(f"\n[1/5] Serial extraction...")
    metadata_serial, time_serial = benchmark_serial(raw_files, 'pyexiv2')
    errors_serial = sum(1 for m in metadata_serial if 'error' in m)
    print(f"  ✓ Completed in {time_serial:.3f}s")
    print(f"    Per-file: {time_serial / len(raw_files) * 1000:.2f}ms")
    if errors_serial > 0:
        print(f"    ⚠ Errors: {errors_serial}/{len(raw_files)}")

    # Multiprocessing
    process_counts = [2, 4, 8]
    pyexiv2_results = []

    for idx, processes in enumerate(process_counts, start=2):
        print(f"\n[{idx}/5] Parallel extraction ({processes} processes)...")
        metadata_parallel, time_parallel = benchmark_multiprocessing(raw_files, 'pyexiv2', processes)

        errors_parallel = sum(1 for m in metadata_parallel if 'error' in m)
        speedup = time_serial / time_parallel if time_parallel > 0 else 0
        efficiency = (speedup / processes) * 100

        print(f"  ✓ Completed in {time_parallel:.3f}s")
        print(f"    Per-file: {time_parallel / len(raw_files) * 1000:.2f}ms")
        print(f"    Speedup: {speedup:.2f}x ({efficiency:.0f}% efficiency)")
        if errors_parallel > 0:
            print(f"    ⚠ Errors: {errors_parallel}/{len(raw_files)}")

        pyexiv2_results.append({
            'processes': processes,
            'time': time_parallel,
            'speedup': speedup,
            'efficiency': efficiency
        })

    results_all.append({
        'method': 'pyexiv2',
        'serial_time': time_serial,
        'parallel_results': pyexiv2_results
    })

    # exifread comparison (if available)
    if HAS_EXIFREAD:
        print(f"\n{'='*70}")
        print(f"Method: EXIFREAD (Pure Python) - For Comparison")
        print(f"{'='*70}")

        print(f"\n[Comparison] exifread serial...")
        metadata_exif_serial, time_exif_serial = benchmark_serial(raw_files, 'exifread')
        print(f"  ✓ Completed in {time_exif_serial:.3f}s")
        print(f"    Per-file: {time_exif_serial / len(raw_files) * 1000:.2f}ms")

        results_all.append({
            'method': 'exifread',
            'serial_time': time_exif_serial,
            'parallel_results': []
        })

    # Summary
    print("\n" + "="*70)
    print("COMPREHENSIVE SUMMARY")
    print("="*70)

    print(f"\nFiles tested: {len(raw_files)} operations ({len(raw_files_base)} unique × {len(raw_files) // len(raw_files_base)})")

    for result in results_all:
        print(f"\n{result['method'].upper()}:")
        print(f"  Serial: {result['serial_time']:.3f}s ({result['serial_time']/len(raw_files)*1000:.2f}ms per file)")

        if result['parallel_results']:
            print(f"  Multiprocessing:")
            for pr in result['parallel_results']:
                print(f"    {pr['processes']:2d} processes: {pr['time']:.3f}s → {pr['speedup']:.2f}x speedup ({pr['efficiency']:.0f}% efficiency)")

    # Comparison to darktable
    print(f"\n{'-'*70}")
    print("Comparison to darktable dt_image_import():")
    print(f"{'-'*70}")
    print("From Phase 2 benchmarks:")
    print("  darktable serial (Exiv2): 17ms per file")
    print()

    # Find best result
    best_method = results_all[0]  # pyexiv2
    best_parallel = max(best_method['parallel_results'], key=lambda p: p['speedup'])
    best_time_per_file = best_parallel['time'] / len(raw_files) * 1000

    serial_time_per_file = best_method['serial_time'] / len(raw_files) * 1000
    dt_time_per_file = 17.0  # From Phase 2 benchmarks

    print(f"PYEXIV2 Results:")
    print(f"  Serial:                    {serial_time_per_file:.2f}ms per file")
    print(f"  Best parallel ({best_parallel['processes']}p):   {best_time_per_file:.2f}ms per file ({best_parallel['speedup']:.2f}x speedup)")
    print()
    print(f"vs darktable (17ms):")
    print(f"  pyexiv2 serial:            {dt_time_per_file / serial_time_per_file:.2f}x {'faster' if serial_time_per_file < dt_time_per_file else 'slower'}")
    print(f"  pyexiv2 parallel ({best_parallel['processes']}p):  {dt_time_per_file / best_time_per_file:.2f}x faster")
    print()

    # Projected for 1000 files
    print(f"{'='*70}")
    print("PROJECTED PERFORMANCE FOR 1000 FILES")
    print(f"{'='*70}")

    exifread_mp8_time = 10.45  # From previous benchmark

    print(f"\nCurrent (darktable serial):                    17.0s")
    print(f"exifread multiprocessing (8p) [Phase 3A]:     10.4s  (1.63x speedup)")
    print(f"pyexiv2 serial:                                {serial_time_per_file * 1000 / 1000:.1f}s")
    print(f"pyexiv2 multiprocessing ({best_parallel['processes']}p):             {best_time_per_file * 1000 / 1000:.1f}s  ({dt_time_per_file / best_time_per_file:.2f}x speedup)")

    print(f"\n{'='*70}")
    print("KEY INSIGHTS")
    print(f"{'='*70}")

    print(f"\n1. pyexiv2 is {(time_exif_serial / time_serial):.1f}x faster than exifread (serial)")
    print(f"   - pyexiv2 uses Exiv2 C++ library (same as darktable)")
    print(f"   - exifread is pure Python (slower)")

    print(f"\n2. pyexiv2 serial is {(dt_time_per_file / serial_time_per_file):.2f}x vs darktable")
    print(f"   - Close to darktable's 17ms per file")
    print(f"   - Both use Exiv2 (C++ library)")

    print(f"\n3. multiprocessing provides {best_parallel['speedup']:.2f}x speedup")
    print(f"   - {best_parallel['processes']} processes = best result")
    print(f"   - {best_parallel['efficiency']:.0f}% CPU efficiency")

    print(f"\n4. pyexiv2 multiprocessing ({best_parallel['processes']}p) achieves:")
    print(f"   - {best_time_per_file:.2f}ms per file")
    print(f"   - {dt_time_per_file / best_time_per_file:.2f}x faster than darktable serial")
    print(f"   - 1000 files in {best_time_per_file * 1000 / 1000:.1f}s (vs darktable's 17s)")

    print(f"\n{'='*70}")
    print("✓ Benchmark complete")
    print(f"{'='*70}")

    # Show sample metadata
    if metadata_serial and 'error' not in metadata_serial[0]:
        print(f"\nSample metadata (first file):")
        sample = metadata_serial[0]
        for key, value in sample.items():
            print(f"  {key:15s}: {value}")


if __name__ == '__main__':
    main()
