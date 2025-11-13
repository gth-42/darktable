/*
    Buffer-based RawSpeed loader - new function

    Add this to imageio_rawspeed.cc after dt_imageio_open_rawspeed()
*/

dt_imageio_retval_t dt_imageio_open_rawspeed_from_buffer(
    dt_image_t *img,
    const uint8_t *buffer,
    size_t buffer_size,
    dt_mipmap_buffer_t *mbuf)
{
  if(!img)
  {
    dt_print(DT_DEBUG_ALWAYS,
             "[dt_imageio_open_rawspeed_from_buffer] failed to get dt_image_t at %p",
             mbuf);
    return DT_IMAGEIO_LOAD_FAILED;
  }

  if(!buffer || buffer_size == 0)
  {
    dt_print(DT_DEBUG_ALWAYS,
             "[dt_imageio_open_rawspeed_from_buffer] invalid buffer");
    return DT_IMAGEIO_LOAD_FAILED;
  }

  // SKIP EXIF for demo (user requested)
  // if(!img->exif_inited)
  //   (void)dt_exif_read(img, filename);

  try
  {
    dt_rawspeed_load_meta();

    // KEY CHANGE: Create Buffer directly from memory instead of FileReader
    // No file I/O happens here!
    Buffer storageBuf(buffer, static_cast<Buffer::size_type>(buffer_size));

    RawParser t(storageBuf);
    std::unique_ptr<RawDecoder> d = t.getDecoder(meta);

    if(!d.get()) return DT_IMAGEIO_UNSUPPORTED_FORMAT;

    d->failOnUnknown = true;
    d->checkSupport(meta);
    d->decodeRaw();
    d->decodeMetaData(meta);
    RawImage r = d->mRaw;

    const auto errors = r->getErrors();
    for(const auto &error : errors)
      dt_print(DT_DEBUG_ALWAYS, "[rawspeed] (from buffer) %s", error.c_str());

    g_strlcpy(img->camera_maker,
              r->metadata.canonical_make.c_str(),
              sizeof(img->camera_maker));
    g_strlcpy(img->camera_model,
              r->metadata.canonical_model.c_str(),
              sizeof(img->camera_model));
    g_strlcpy(img->camera_alias,
              r->metadata.canonical_alias.c_str(),
              sizeof(img->camera_alias));
    dt_image_refresh_makermodel(img);

    img->raw_black_level = r->blackLevel;
    img->raw_white_point = r->whitePoint.value_or((1U << 16)-1);

    if(!r->blackLevelSeparate)
    {
      r->calculateBlackAreas();
    }

    const auto bl = *(r->blackLevelSeparate->getAsArray1DRef());
    for(uint8_t i = 0; i < 4; i++)
      img->raw_black_level_separate[i] = bl(i);

    if(r->blackLevel == -1)
    {
      float black = 0.0f;
      for(uint8_t i = 0; i < 4; i++)
      {
        black += img->raw_black_level_separate[i];
      }
      black /= 4.0f;

      img->raw_black_level = CLAMP(roundf(black), 0, UINT16_MAX);
    }

    /* free auto pointers on spot */
    d.reset();

    // Grab the WB
    if(r->metadata.wbCoeffs) {
      for(int i = 0; i < 4; i++)
        img->wb_coeffs[i] = (*r->metadata.wbCoeffs)[i];
    } else {
      for(int i = 0; i < 4; i++)
        img->wb_coeffs[i] = 0.0;
    }

    // Grab the Adobe coeffs
    const int msize = r->metadata.colorMatrix.size();
    for(int k = 0; k < 4; k++)
      for(int i = 0; i < 3; i++)
      {
        const int idx = k*3 + i;
        if(idx < msize)
          img->adobe_XYZ_to_CAM[k][i] = float(r->metadata.colorMatrix[idx]);
        else
          img->adobe_XYZ_to_CAM[k][i] = 0.0f;
      }

    // SKIP additional exif tags for demo
    // dt_exif_img_check_additional_tags(img, filename);

    if(r->getDataType() == TYPE_FLOAT32)
    {
      img->flags |= DT_IMAGE_HDR;

      if(r->whitePoint == 0x3F800000) img->raw_white_point = 1;
      if(img->raw_white_point == 1)
        for(int k = 0; k < 4; k++) img->buf_dsc.processed_maximum[k] = 1.0f;
    }

    img->buf_dsc.filters = 0u;

    // dimensions of uncropped image
    const iPoint2D dimUncropped = r->getUncroppedDim();
    img->width = dimUncropped.x;
    img->height = dimUncropped.y;

    // dimensions of cropped image
    const iPoint2D dimCropped = r->dim;

    // crop - Top,Left corner
    const iPoint2D cropTL = r->getCropOffset();
    img->crop_x = cropTL.x;
    img->crop_y = cropTL.y;

    // crop - Bottom,Right corner
    const iPoint2D cropBR = dimUncropped - dimCropped - cropTL;
    img->crop_right = cropBR.x;
    img->crop_bottom = cropBR.y;
    img->p_width = img->width - img->crop_x - img->crop_right;
    img->p_height = img->height - img->crop_y - img->crop_bottom;

    img->fuji_rotation_pos = r->metadata.fujiRotationPos;
    img->pixel_aspect_ratio = (float)r->metadata.pixelAspectRatio;

    if(!r->isCFA)
    {
      const dt_imageio_retval_t ret = dt_imageio_open_rawspeed_sraw(img, r, mbuf);
      return ret;
    }

    if((r->getDataType() != TYPE_USHORT16) && (r->getDataType() != TYPE_FLOAT32))
      return DT_IMAGEIO_UNSUPPORTED_FEATURE;

    if((r->getBpp() != sizeof(uint16_t)) && (r->getBpp() != sizeof(float)))
      return DT_IMAGEIO_UNSUPPORTED_FEATURE;

    if((r->getDataType() == TYPE_USHORT16) && (r->getBpp() != sizeof(uint16_t)))
      return DT_IMAGEIO_UNSUPPORTED_FEATURE;

    if((r->getDataType() == TYPE_FLOAT32) && (r->getBpp() != sizeof(float)))
      return DT_IMAGEIO_UNSUPPORTED_FEATURE;

    const float cpp = r->getCpp();
    if(cpp != 1) return DT_IMAGEIO_LOAD_FAILED;

    img->buf_dsc.channels = 1;

    switch(r->getBpp())
    {
      case sizeof(uint16_t):
        img->buf_dsc.datatype = TYPE_UINT16;
        break;
      case sizeof(float):
        img->buf_dsc.datatype = TYPE_FLOAT;
        break;
      default:
        return DT_IMAGEIO_UNSUPPORTED_FEATURE;
    }

    img->buf_dsc.filters = dt_rawspeed_crop_dcraw_filters(r->cfa.getDcrawFilter(),
                                                          cropTL.x,
                                                          cropTL.y);

    if(FILTERS_ARE_4BAYER(img->buf_dsc.filters))
      img->flags |= DT_IMAGE_4BAYER;

    if(img->buf_dsc.filters)
    {
      img->flags &= ~DT_IMAGE_LDR;
      img->flags |= DT_IMAGE_RAW;

      // special handling for x-trans sensors
      if(img->buf_dsc.filters == 9u)
      {
        for(int i = 0; i < 6; ++i)
          for(int j = 0; j < 6; ++j)
          {
            img->buf_dsc.xtrans[j][i] = (uint8_t)r->cfa.getColorAt(i % 6, j % 6);
          }
      }
    }

    // if buf is NULL, we quit the fct here
    if(!mbuf)
    {
      img->buf_dsc.cst = IOP_CS_RAW;
      img->loader = LOADER_RAWSPEED;
      return DT_IMAGEIO_OK;
    }

    void *buf = dt_mipmap_cache_alloc(mbuf, img);
    if(!buf) return DT_IMAGEIO_CACHE_FULL;

    const size_t bufSize_mipmap = (size_t)img->width * img->height * r->getBpp();
    const size_t bufSize_rawspeed = (size_t)r->pitch * dimUncropped.y;
    if(bufSize_mipmap == bufSize_rawspeed)
    {
      memcpy(buf, (char *)(&(r->getByteDataAsUncroppedArray2DRef()(0, 0))), bufSize_mipmap);
    }
    else
    {
      dt_imageio_flip_buffers((char *)buf,
                              (char *)(&(r->getByteDataAsUncroppedArray2DRef()(0, 0))),
                              r->getBpp(),
                              dimUncropped.x, dimUncropped.y,
                              dimUncropped.x, dimUncropped.y,
                              r->pitch,
                              ORIENTATION_NONE);
    }

    const Camera *cam = meta->getCamera(r->metadata.make.c_str(),
                                        r->metadata.model.c_str(),
                                        r->metadata.mode.c_str());

    if(cam && cam->supportStatus == Camera::SupportStatus::SupportedNoSamples)
      img->camera_missing_sample = TRUE;
  }
  catch(const rawspeed::IOException &exc)
  {
    dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] I/O error: %s", exc.what());
    return DT_IMAGEIO_IOERROR;
  }
  catch(const rawspeed::FileIOException &exc)
  {
    dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] File I/O error: %s", exc.what());
    return DT_IMAGEIO_IOERROR;
  }
  catch(const rawspeed::RawDecoderException &exc)
  {
    const char *msg = exc.what();
    if(msg && (strstr(msg, "Camera not supported") || strstr(msg, "not supported, and not allowed to guess")))
    {
      dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] Unsupported camera model");
      return DT_IMAGEIO_UNSUPPORTED_CAMERA;
    }
    else if (msg && strstr(msg, "supported"))
    {
      dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] %s", msg);
      return DT_IMAGEIO_UNSUPPORTED_FEATURE;
    }
    else
    {
      dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] corrupt: %s", exc.what());
      return DT_IMAGEIO_UNSUPPORTED_FORMAT;
    }
  }
  catch(const rawspeed::RawParserException &exc)
  {
    dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] CIFF/FIFF error: %s", exc.what());
    return DT_IMAGEIO_UNSUPPORTED_FORMAT;
  }
  catch(const rawspeed::CameraMetadataException &exc)
  {
    dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] metadata error: %s", exc.what());
    return DT_IMAGEIO_UNSUPPORTED_FEATURE;
  }
  catch(const std::exception &exc)
  {
    dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] %s", exc.what());
    return DT_IMAGEIO_FILE_CORRUPTED;
  }
  catch(...)
  {
    dt_print(DT_DEBUG_ALWAYS, "[rawspeed buffer] unhandled exception");
    return DT_IMAGEIO_FILE_CORRUPTED;
  }

  img->buf_dsc.cst = IOP_CS_RAW;
  img->loader = LOADER_RAWSPEED;

  return DT_IMAGEIO_OK;
}
