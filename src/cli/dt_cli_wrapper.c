/*
    Phase 1 cffi wrapper library for darktable-cli.
    Provides dt_cli_process_simple() without requiring main.c compilation.
*/

#include "common/darktable.h"
#include "common/file_location.h"
#include "common/film.h"
#include "common/image.h"
#include "common/image_cache.h"
#include "imageio/imageio_common.h"
#include "imageio/imageio_module.h"
#include <glib.h>

// Forward declaration from main.c
extern int cli_export_images(GList *id_list, dt_imageio_module_storage_t *storage,
                             dt_imageio_module_data_t *sdata, dt_imageio_module_format_t *format,
                             dt_imageio_module_data_t *fdata, gboolean high_quality,
                             gboolean allow_upscale, gboolean masks,
                             dt_colorspaces_color_profile_type_t icc_type, const char *icc_file,
                             dt_iop_color_intent_t icc_intent, int total_count);

// Phase 1 wrapper: Simple single-image processing function.
// Returns 0 on success, non-zero on error.
int dt_cli_process_simple(const char *input_path, const char *output_path, int width, int height)
{
  // Minimal init args for darktable
  char *init_argv[] = { "darktable-cli", "--library", ":memory:",
                        "--conf", "write_sidecar_files=never", NULL };
  int init_argc = 5;

  // Initialize darktable - pass applicationdir to bypass whereami auto-detection
  // This allows Python to load the wrapper without needing a launcher executable
  if(dt_init(init_argc, init_argv, FALSE, TRUE, NULL, "/home/glen/Applications/Darktable/bin"))
  {
    fprintf(stderr, "dt_cli_process_simple: failed to initialize darktable\n");
    return 1;
  }

  // Import the image
  gchar *directory = g_path_get_dirname(input_path);
  dt_film_t film;
  dt_filmid_t filmid = dt_film_new(&film, directory);
  g_free(directory);

  if(!dt_is_valid_filmid(filmid))
  {
    fprintf(stderr, "dt_cli_process_simple: failed to create film for input\n");
    dt_cleanup();
    return 2;
  }

  const dt_imgid_t imgid = dt_image_import(filmid, input_path, TRUE, TRUE);
  if(!dt_is_valid_imgid(imgid))
  {
    fprintf(stderr, "dt_cli_process_simple: failed to import image\n");
    dt_cleanup();
    return 3;
  }

  // Setup export modules (default to JPEG)
  dt_imageio_module_format_t *format = dt_imageio_get_format_by_name("jpeg");
  dt_imageio_module_storage_t *storage = dt_imageio_get_storage_by_name("disk");

  if(!format || !storage)
  {
    fprintf(stderr, "dt_cli_process_simple: failed to get format/storage modules\n");
    dt_cleanup();
    return 4;
  }

  dt_imageio_module_data_t *sdata = storage->get_params(storage);
  dt_imageio_module_data_t *fdata = format->get_params(format);

  if(!sdata || !fdata)
  {
    fprintf(stderr, "dt_cli_process_simple: failed to get module params\n");
    if(sdata) storage->free_params(storage, sdata);
    if(fdata) format->free_params(format, fdata);
    dt_cleanup();
    return 5;
  }

  // Configure output
  gchar *output_without_ext = g_strdup(output_path);
  gchar *last_dot = strrchr(output_without_ext, '.');
  if(last_dot) *last_dot = '\0';
  g_strlcpy((char *)sdata, output_without_ext, DT_MAX_PATH_FOR_PARAMS);
  g_free(output_without_ext);

  fdata->max_width = width;
  fdata->max_height = height;

  // Export the image
  GList *id_list = g_list_append(NULL, GINT_TO_POINTER(imgid));

  dt_export_metadata_t metadata;
  metadata.flags = dt_lib_export_metadata_default_flags();
  metadata.list = NULL;

  int export_result = storage->store(storage, sdata, imgid, format, fdata, 1, 1, TRUE, FALSE,
                                      FALSE, 1.0, FALSE, DT_COLORSPACE_SRGB, NULL,
                                      DT_INTENT_PERCEPTUAL, &metadata);

  g_list_free(id_list);

  // Cleanup
  if(storage->finalize_store) storage->finalize_store(storage, sdata);
  storage->free_params(storage, sdata);
  format->free_params(format, fdata);
  dt_cleanup();

  return (export_result == 0) ? 0 : 6;
}
