/*
    Python API Shim Layer for darktable

    This file provides C wrapper functions that cffi can easily call.
    Main purpose: wrap function pointers in structs (which cffi can't call directly)
*/

#pragma once

#include "common/darktable.h"
#include "imageio/imageio_module.h"
#include "imageio/imageio_common.h"

#ifdef __cplusplus
extern "C" {
#endif

// ============================================================================
// Format Module Wrappers
// ============================================================================

// Get format module parameters
dt_imageio_module_data_t* dt_shim_format_get_params(dt_imageio_module_format_t *format);

// Free format module parameters
void dt_shim_format_free_params(dt_imageio_module_format_t *format,
                                 dt_imageio_module_data_t *data);

// ============================================================================
// Storage Module Wrappers
// ============================================================================

// Get storage module parameters
dt_imageio_module_data_t* dt_shim_storage_get_params(dt_imageio_module_storage_t *storage);

// Free storage module parameters
void dt_shim_storage_free_params(dt_imageio_module_storage_t *storage,
                                  dt_imageio_module_data_t *data);

// Finalize storage (optional cleanup)
void dt_shim_storage_finalize(dt_imageio_module_storage_t *storage,
                               dt_imageio_module_data_t *data);

// The big export function - wraps storage->store()
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

// ============================================================================
// Helper Functions
// ============================================================================

// Simplified film creation - allocates film internally, just returns filmid
dt_filmid_t dt_shim_film_new(const char *directory);

// Configure export paths and dimensions (handles the char* cast weirdness)
void dt_shim_configure_export(dt_imageio_module_data_t *sdata,
                               dt_imageio_module_data_t *fdata,
                               const char *output_path,
                               int width, int height);

// Get default metadata flags
int dt_shim_get_default_metadata_flags(void);

// ============================================================================
// Buffer-based export (NEW - Demo)
// ============================================================================

// Export directly from memory buffer (no filename needed!)
int dt_shim_export_from_buffer(const uint8_t *raw_buffer,
                                size_t buffer_size,
                                const char *output_path,
                                int quality,
                                int max_width,
                                int max_height);

// Attach buffer to existing image (for production use)
// TODO: Temporary API - should be integrated into import workflow
void dt_shim_attach_buffer_to_image(dt_imgid_t imgid,
                                     const uint8_t *raw_buffer,
                                     size_t buffer_size);

#ifdef __cplusplus
}
#endif
