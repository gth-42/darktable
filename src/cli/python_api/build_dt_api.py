#!/usr/bin/env python3
"""
cffi builder for darktable Python API

This exposes darktable's C functions to Python via cffi.
"""

from cffi import FFI
import subprocess

# Get pkg-config flags
def get_pkg_config(package, flag):
    result = subprocess.run(['pkg-config', flag, package],
                          capture_output=True, text=True, check=True)
    return result.stdout.strip().split()

glib_cflags = get_pkg_config('glib-2.0', '--cflags')
gtk_cflags = get_pkg_config('gtk+-3.0', '--cflags')
rsvg_cflags = get_pkg_config('librsvg-2.0', '--cflags')
json_cflags = get_pkg_config('json-glib-1.0', '--cflags')

# Combine and extract just -I flags
extra_cflags = glib_cflags + gtk_cflags + rsvg_cflags + json_cflags

ffibuilder = FFI()

# Define the C API that Python will see
ffibuilder.cdef("""
    // ========================================================================
    // Opaque types (we don't need to see inside these)
    // ========================================================================
    typedef struct dt_film_t dt_film_t;
    typedef struct dt_image_t dt_image_t;
    typedef struct dt_imageio_module_format_t dt_imageio_module_format_t;
    typedef struct dt_imageio_module_storage_t dt_imageio_module_storage_t;
    typedef struct dt_imageio_module_data_t dt_imageio_module_data_t;

    // ========================================================================
    // Simple typedefs
    // ========================================================================
    typedef int dt_filmid_t;
    typedef int dt_imgid_t;
    typedef int gboolean;

    // Color profile types (enum values)
    typedef enum {
        DT_COLORSPACE_NONE = -1,
        DT_COLORSPACE_FILE = 0,
        DT_COLORSPACE_SRGB = 1,
        DT_COLORSPACE_ADOBERGB = 2,
        DT_COLORSPACE_LIN_REC709 = 3,
        DT_COLORSPACE_LIN_REC2020 = 4,
        DT_COLORSPACE_XYZ = 5,
        DT_COLORSPACE_LAB = 6,
        DT_COLORSPACE_REC709 = 7,
        DT_COLORSPACE_PROPHOTO_RGB = 8,
        DT_COLORSPACE_PQ_REC2020 = 9,
        DT_COLORSPACE_HLG_REC2020 = 10,
        DT_COLORSPACE_PQ_P3 = 11,
        DT_COLORSPACE_HLG_P3 = 12,
        DT_COLORSPACE_DISPLAY_P3 = 13,
        ...
    } dt_colorspaces_color_profile_type_t;

    // ICC rendering intent
    typedef enum {
        DT_INTENT_PERCEPTUAL = 0,
        DT_INTENT_RELATIVE_COLORIMETRIC = 1,
        DT_INTENT_SATURATION = 2,
        DT_INTENT_ABSOLUTE_COLORIMETRIC = 3,
        ...
    } dt_iop_color_intent_t;

    // ========================================================================
    // Core darktable functions
    // ========================================================================

    // Initialization
    int dt_init(int argc, char *argv[],
                gboolean init_gui, gboolean load_data,
                void *L, const char *applicationdir);
    void dt_cleanup(void);

    // Film (directory) management
    dt_filmid_t dt_film_new(dt_film_t *film, const char *directory);
    gboolean dt_is_valid_filmid(dt_filmid_t id);

    // Image import
    dt_imgid_t dt_image_import(dt_filmid_t filmid, const char *path,
                               gboolean override_ignore_jpegs,
                               gboolean check_duplicates);
    gboolean dt_is_valid_imgid(dt_imgid_t id);
    gboolean dt_supported_image(const char *filename);

    // Get export modules
    dt_imageio_module_format_t* dt_imageio_get_format_by_name(const char *name);
    dt_imageio_module_storage_t* dt_imageio_get_storage_by_name(const char *name);

    // ========================================================================
    // Shim functions (wrappers for function pointers)
    // ========================================================================

    // Format module
    dt_imageio_module_data_t* dt_shim_format_get_params(dt_imageio_module_format_t *format);
    void dt_shim_format_free_params(dt_imageio_module_format_t *format,
                                     dt_imageio_module_data_t *data);

    // Storage module
    dt_imageio_module_data_t* dt_shim_storage_get_params(dt_imageio_module_storage_t *storage);
    void dt_shim_storage_free_params(dt_imageio_module_storage_t *storage,
                                      dt_imageio_module_data_t *data);
    void dt_shim_storage_finalize(dt_imageio_module_storage_t *storage,
                                   dt_imageio_module_data_t *data);

    // Export function
    int dt_shim_storage_store(dt_imageio_module_storage_t *storage,
                               dt_imageio_module_data_t *sdata,
                               dt_imgid_t imgid,
                               dt_imageio_module_format_t *format,
                               dt_imageio_module_data_t *fdata,
                               int num, int total,
                               gboolean high_quality,
                               gboolean allow_upscale,
                               gboolean export_masks,
                               dt_colorspaces_color_profile_type_t icc_type,
                               const char *icc_file,
                               dt_iop_color_intent_t icc_intent);

    // Helper functions
    dt_filmid_t dt_shim_film_new(const char *directory);

    void dt_shim_configure_export(dt_imageio_module_data_t *sdata,
                                   dt_imageio_module_data_t *fdata,
                                   const char *output_path,
                                   int width, int height);

    int dt_shim_get_default_metadata_flags(void);

    // Buffer-based export (NEW - Demo)
    int dt_shim_export_from_buffer(const uint8_t *raw_buffer,
                                    size_t buffer_size,
                                    const char *output_path,
                                    int quality,
                                    int max_width,
                                    int max_height);

    // Attach buffer to existing image
    void dt_shim_attach_buffer_to_image(dt_imgid_t imgid,
                                         const uint8_t *raw_buffer,
                                         size_t buffer_size);
""")

# Specify the source for compilation
ffibuilder.set_source(
    "_dt_api",
    """
    #include "dt_api_shim.h"
    #include "common/darktable.h"
    #include "common/film.h"
    #include "common/image.h"
    #include "imageio/imageio_common.h"
    #include "imageio/imageio_module.h"
    """,
    libraries=['dt_api_shim', 'darktable'],
    library_dirs=[
        '/mnt/2t4/development/darktable/darktable/src/cli/python_api',
        '/home/glen/Applications/Darktable/lib/darktable'
    ],
    runtime_library_dirs=[
        '/mnt/2t4/development/darktable/darktable/src/cli/python_api',
        '/home/glen/Applications/Darktable/lib/darktable'
    ],
    include_dirs=[
        '/mnt/2t4/development/darktable/darktable/src',
        '/mnt/2t4/development/darktable/darktable/src/cli/python_api',
        '/mnt/2t4/development/darktable/darktable/build'
    ],
    extra_compile_args=extra_cflags
)

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
