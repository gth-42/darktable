#!/usr/bin/env python3
"""
Benchmark: Parallel Metadata Extraction
Goal: Validate 10x speedup hypothesis from batch_import_strategy.md

Compares:
1. Serial metadata extraction (current darktable approach)
2. Parallel metadata extraction with ThreadPoolExecutor
3. Different Python libraries: exifread, rawpy

Expected result: 10x speedup with 10 threads
"""

import os
import sys
import time
import glob
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import statistics

# Try to import both libraries
try:
    import exifread
    HAS_EXIFREAD = True
except ImportError:
    HAS_EXIFREAD = False
    print("⚠ exifread not installed (pip install exifread)")

try:
    import rawpy
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False
    print("⚠ rawpy not installed (pip install rawpy)")

if not HAS_EXIFREAD and not HAS_RAWPY:
    print("ERROR: Need at least one of: exifread, rawpy")
    sys.exit(1)

TEST_DATA_DIR = "/mnt/2t4/development/darktable/test_data"


def extract_metadata_exifread(raw_path):
    """Extract minimal metadata using exifread (pure Python)"""
    try:
        with open(raw_path, 'rb') as f:
            tags = exifread.process_file(f, details=True)

        # Extract required fields for darktable import
        maker = str(tags.get('Image Make', 'Unknown')).strip()
        model = str(tags.get('Image Model', 'Unknown')).strip()

        # For Sony ZV-1 with fixed lens, use model as lens name
        lens = str(tags.get('EXIF LensModel', model)).strip()

        # Dimensions - use EXIF tags (processed image dimensions)
        width = tags.get('EXIF ExifImageWidth')
        height = tags.get('EXIF ExifImageLength')

        # Parse dimensions
        if width:
            width = int(str(width))
        else:
            # Fallback to SubIFD dimensions
            width = tags.get('EXIF SubIFD0 ImageWidth')
            width = int(str(width)) if width else 0

        if height:
            height = int(str(height))
        else:
            # Fallback to SubIFD dimensions
            height = tags.get('EXIF SubIFD0 ImageLength')
            height = int(str(height)) if height else 0

        # Exposure data
        focal_length = tags.get('EXIF FocalLength')
        if focal_length:
            focal_length = float(focal_length.values[0]) if hasattr(focal_length, 'values') else 0.0
        else:
            focal_length = 0.0

        aperture = tags.get('EXIF FNumber')
        if aperture:
            aperture = float(aperture.values[0]) if hasattr(aperture, 'values') else 0.0
        else:
            aperture = 0.0

        orientation = tags.get('Image Orientation')
        if orientation:
            # exifread returns IFD tag objects with .values attribute for numeric value
            if hasattr(orientation, 'values'):
                orientation = int(orientation.values[0])
            else:
                try:
                    orientation = int(str(orientation))
                except (ValueError, TypeError):
                    orientation = 1  # Default to normal orientation
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
            'method': 'exifread'
        }
    except Exception as e:
        return {'filename': os.path.basename(raw_path), 'error': str(e), 'method': 'exifread'}


def extract_metadata_rawpy(raw_path):
    """Extract minimal metadata using rawpy (libraw wrapper)"""
    try:
        with rawpy.imread(raw_path) as raw:
            # Get camera info
            maker = raw.color_desc.decode('utf-8', errors='ignore').strip() if hasattr(raw, 'color_desc') else 'Unknown'

            # Get dimensions
            width = raw.sizes.width
            height = raw.sizes.height

            # Get RAW parameters
            black = raw.black_level_per_channel[0] if len(raw.black_level_per_channel) > 0 else 0
            white = raw.white_level

            # rawpy doesn't easily expose EXIF, so we combine with exifread for complete metadata
            with open(raw_path, 'rb') as f:
                tags = exifread.process_file(f, details=False, stop_tag='EXIF LensModel')

            model = str(tags.get('Image Model', 'Unknown')).strip()
            lens = str(tags.get('EXIF LensModel', model)).strip()
            focal_length = tags.get('EXIF FocalLength')
            if focal_length:
                focal_length = float(focal_length.values[0]) if hasattr(focal_length, 'values') else 0.0
            else:
                focal_length = 0.0

            aperture = tags.get('EXIF FNumber')
            if aperture:
                aperture = float(aperture.values[0]) if hasattr(aperture, 'values') else 0.0
            else:
                aperture = 0.0

            orientation = tags.get('Image Orientation', 1)
            orientation = int(str(orientation)) if orientation else 1

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
                'raw_black': black,
                'raw_maximum': white,
                'method': 'rawpy'
            }
    except Exception as e:
        return {'filename': os.path.basename(raw_path), 'error': str(e), 'method': 'rawpy'}


def benchmark_serial(raw_files, method='exifread'):
    """Benchmark serial metadata extraction"""
    extract_func = extract_metadata_exifread if method == 'exifread' else extract_metadata_rawpy

    t0 = time.time()
    results = []
    for raw_path in raw_files:
        results.append(extract_func(raw_path))
    elapsed = time.time() - t0

    return results, elapsed


def benchmark_parallel(raw_files, method='exifread', max_workers=10):
    """Benchmark parallel metadata extraction"""
    extract_func = extract_metadata_exifread if method == 'exifread' else extract_metadata_rawpy

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(extract_func, raw_files))
    elapsed = time.time() - t0

    return results, elapsed


def print_separator(char='=', length=70):
    print(char * length)


def main():
    print_separator()
    print("Parallel Metadata Extraction Benchmark")
    print_separator()

    # Find test files
    raw_files = sorted(glob.glob(os.path.join(TEST_DATA_DIR, "*.ARW")))
    if not raw_files:
        print(f"ERROR: No ARW files found in {TEST_DATA_DIR}")
        sys.exit(1)

    print(f"\nFound {len(raw_files)} ARW files:")
    for f in raw_files:
        size_mb = os.path.getsize(f) / (1024 * 1024)
        print(f"  - {os.path.basename(f)} ({size_mb:.1f} MB)")

    print_separator()

    # Test each available method
    methods = []
    if HAS_EXIFREAD:
        methods.append('exifread')
    if HAS_RAWPY and HAS_EXIFREAD:  # rawpy needs exifread for complete metadata
        methods.append('rawpy')

    results_summary = []

    for method in methods:
        print(f"\n{'='*70}")
        print(f"Method: {method.upper()}")
        print(f"{'='*70}")

        # Benchmark serial
        print(f"\n[1/2] Serial extraction...")
        metadata_serial, time_serial = benchmark_serial(raw_files, method)

        errors_serial = sum(1 for m in metadata_serial if 'error' in m)
        print(f"  ✓ Completed in {time_serial:.3f}s")
        print(f"    Per-file: {time_serial / len(raw_files) * 1000:.2f}ms")
        if errors_serial > 0:
            print(f"    ⚠ Errors: {errors_serial}/{len(raw_files)}")

        # Benchmark parallel with different thread counts
        thread_counts = [2, 5, 10]
        parallel_results = []

        for threads in thread_counts:
            print(f"\n[2/2] Parallel extraction ({threads} threads)...")
            metadata_parallel, time_parallel = benchmark_parallel(raw_files, method, threads)

            errors_parallel = sum(1 for m in metadata_parallel if 'error' in m)
            speedup = time_serial / time_parallel if time_parallel > 0 else 0

            print(f"  ✓ Completed in {time_parallel:.3f}s")
            print(f"    Per-file: {time_parallel / len(raw_files) * 1000:.2f}ms")
            print(f"    Speedup: {speedup:.2f}x")
            if errors_parallel > 0:
                print(f"    ⚠ Errors: {errors_parallel}/{len(raw_files)}")

            parallel_results.append({
                'threads': threads,
                'time': time_parallel,
                'speedup': speedup
            })

        results_summary.append({
            'method': method,
            'serial_time': time_serial,
            'parallel_results': parallel_results,
            'file_count': len(raw_files)
        })

        # Show sample metadata from first file
        if metadata_serial and 'error' not in metadata_serial[0]:
            print(f"\nSample metadata (first file):")
            sample = metadata_serial[0]
            for key, value in sample.items():
                if key != 'method':
                    print(f"  {key:15s}: {value}")

    # Final summary
    print_separator('=')
    print("SUMMARY")
    print_separator('=')

    for result in results_summary:
        print(f"\nMethod: {result['method'].upper()}")
        print(f"Files: {result['file_count']}")
        print(f"Serial time: {result['serial_time']:.3f}s ({result['serial_time']/result['file_count']*1000:.2f}ms per file)")
        print(f"\nParallel results:")
        for pr in result['parallel_results']:
            print(f"  {pr['threads']:2d} threads: {pr['time']:.3f}s → {pr['speedup']:.2f}x speedup")

    # Comparison to darktable import
    print(f"\n{'-'*70}")
    print("Comparison to darktable dt_image_import():")
    print(f"{'-'*70}")
    print("From Phase 2 benchmarks:")
    print("  Run 1 (first import): 10-23ms per file (avg 17ms)")
    print("  Run 2 (cached):       0.7-5.5ms per file (avg 3ms)")
    print()

    if results_summary:
        best_method = min(results_summary, key=lambda r: r['serial_time'])
        best_parallel = min(best_method['parallel_results'], key=lambda p: p['time'])

        dt_import_time = 0.017 * len(raw_files)  # 17ms per file from benchmarks
        our_time = best_parallel['time']
        vs_dt_speedup = dt_import_time / our_time if our_time > 0 else 0

        print(f"Best result: {best_method['method']} with {best_parallel['threads']} threads")
        print(f"  Time: {our_time:.3f}s")
        print(f"  vs dt_import (17ms/file): {vs_dt_speedup:.2f}x faster")
        print()
        print(f"For 1000 files:")
        print(f"  darktable serial import: ~17.0s")
        print(f"  {best_method['method']} parallel:     ~{our_time / len(raw_files) * 1000:.1f}s ({best_parallel['speedup']:.1f}x speedup)")

    print_separator('=')
    print("✓ Benchmark complete")
    print_separator('=')


if __name__ == '__main__':
    main()
