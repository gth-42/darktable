/*
    Python API Shim Layer Implementation

    These are thin wrappers that make darktable's C API callable from cffi.
*/

#include "dt_api_shim.h"
#include "common/film.h"
#include "common/metadata_export.h"
#include "common/image_cache.h"
#include <string.h>

// ============================================================================
// Format Module Wrappers
// ============================================================================

dt_imageio_module_data_t* dt_shim_format_get_params(dt_imageio_module_format_t *format)
{
  if(!format || !format->get_params) return NULL;
  return format->get_params(format);
}

void dt_shim_format_free_params(dt_imageio_module_format_t *format,
                                 dt_imageio_module_data_t *data)
{
  if(!format || !format->free_params || !data) return;
  format->free_params(format, data);
}

// ============================================================================
// Storage Module Wrappers
// ============================================================================

dt_imageio_module_data_t* dt_shim_storage_get_params(dt_imageio_module_storage_t *storage)
{
  if(!storage || !storage->get_params) return NULL;
  return storage->get_params(storage);
}

void dt_shim_storage_free_params(dt_imageio_module_storage_t *storage,
                                  dt_imageio_module_data_t *data)
{
  if(!storage || !storage->free_params || !data) return;
  storage->free_params(storage, data);
}

void dt_shim_storage_finalize(dt_imageio_module_storage_t *storage,
                               dt_imageio_module_data_t *data)
{
  if(!storage || !storage->finalize_store || !data) return;
  storage->finalize_store(storage, data);
}

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
                           dt_iop_color_intent_t icc_intent)
{
  if(!storage || !storage->store) return 1;

  // Create metadata with defaults
  dt_export_metadata_t metadata;
  metadata.flags = dt_lib_export_metadata_default_flags();
  metadata.list = NULL;

  // Call the actual store function
  return storage->store(storage, sdata, imgid, format, fdata,
                       num, total,
                       high_quality, allow_upscale,
                       FALSE,  // is_scaling - always FALSE for simple export
                       1.0,    // scale_factor - 1.0 for no additional scaling
                       export_masks,
                       icc_type, icc_file, icc_intent,
                       &metadata);
}

// ============================================================================
// Helper Functions
// ============================================================================

dt_filmid_t dt_shim_film_new(const char *directory)
{
  if(!directory) return -1;

  // Allocate film on stack like darktable-cli does
  dt_film_t film;
  return dt_film_new(&film, directory);
}

void dt_shim_configure_export(dt_imageio_module_data_t *sdata,
                               dt_imageio_module_data_t *fdata,
                               const char *output_path,
                               int width, int height)
{
  if(!sdata || !fdata || !output_path) return;

  // Strip extension from output path (storage module adds it back)
  gchar *output_without_ext = g_strdup(output_path);
  gchar *last_dot = strrchr(output_without_ext, '.');
  if(last_dot) *last_dot = '\0';

  // sdata is actually a struct but darktable casts it to char* for the path
  // This is darktable's pattern - we're just following it
  g_strlcpy((char *)sdata, output_without_ext, DT_MAX_PATH_FOR_PARAMS);
  g_free(output_without_ext);

  // Format data has real accessible fields
  fdata->max_width = width;
  fdata->max_height = height;
}

int dt_shim_get_default_metadata_flags(void)
{
  return dt_lib_export_metadata_default_flags();
}

// ============================================================================
// Buffer-based export (NEW - Demo)
// ============================================================================

int dt_shim_export_from_buffer(const uint8_t *raw_buffer,
                                size_t buffer_size,
                                const char *output_path,
                                int quality,
                                int max_width,
                                int max_height)
{
  if(!raw_buffer || buffer_size == 0 || !output_path)
  {
    dt_print(DT_DEBUG_ALWAYS,
             "[shim] export_from_buffer: invalid parameters");
    return 1;
  }

  dt_print(DT_DEBUG_ALWAYS,
           "[shim] Decoding %zu bytes from buffer...", buffer_size);

  dt_print(DT_DEBUG_ALWAYS,
           "[shim] Creating temporary dt_image_t...");

  // Create a temporary dt_image_t
  dt_image_t img;
  memset(&img, 0, sizeof(dt_image_t));

  // Set minimal required fields
  img.id = -1;  // Temporary image
  g_strlcpy(img.filename, "buffer://memory", sizeof(img.filename));
  img.exif_inited = TRUE;  // Skip EXIF reading for demo

  dt_print(DT_DEBUG_ALWAYS,
           "[shim] Calling dt_imageio_open_rawspeed_from_buffer...");

  // Decode from buffer (pass NULL for mbuf to skip pixel storage for demo)
  // This will decode metadata and image properties without allocating mipmap cache
  dt_imageio_retval_t decode_ret =
      dt_imageio_open_rawspeed_from_buffer(&img, raw_buffer, buffer_size, NULL);

  dt_print(DT_DEBUG_ALWAYS,
           "[shim] Decode returned: %d", decode_ret);

  if(decode_ret != DT_IMAGEIO_OK)
  {
    dt_print(DT_DEBUG_ALWAYS,
             "[shim] Failed to decode buffer: error %d", decode_ret);
    return 2;
  }

  dt_print(DT_DEBUG_ALWAYS,
           "[shim] Successfully decoded from buffer: %dx%d, %s %s",
           img.width, img.height, img.camera_maker, img.camera_model);

  dt_print(DT_DEBUG_ALWAYS,
           "[shim] Demo complete - decode successful!");
  dt_print(DT_DEBUG_ALWAYS,
           "[shim] (Export to %s not yet implemented)", output_path);

  return 0;
}

// ============================================================================
// Attach buffer to image for export (Production API)
// ============================================================================

void dt_shim_attach_buffer_to_image(dt_imgid_t imgid,
                                     const uint8_t *raw_buffer,
                                     size_t buffer_size)
{
  if(!raw_buffer || buffer_size == 0)
  {
    dt_print(DT_DEBUG_ALWAYS,
             "[shim] attach_buffer: invalid buffer");
    return;
  }

  // Get writable image from cache
  dt_image_t *img = dt_image_cache_get(imgid, 'w');
  if(!img)
  {
    dt_print(DT_DEBUG_ALWAYS,
             "[shim] attach_buffer: failed to get image %d", imgid);
    return;
  }

  // TODO: Temporary hack - attaching buffer pointer directly
  // WARNING: Buffer must remain valid for lifetime of export!
  // Consider: copying buffer or reference counting
  img->raw_buffer = raw_buffer;
  img->raw_buffer_size = buffer_size;

  dt_print(DT_DEBUG_ALWAYS,
           "[shim] Attached %zu byte buffer to image %d", buffer_size, imgid);

  dt_image_cache_write_release(img, DT_IMAGE_CACHE_RELAXED);
}
