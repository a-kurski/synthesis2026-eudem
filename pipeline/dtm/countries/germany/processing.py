"""Shared cleaning, resampling, masking and publication for German DGM1."""
import math

import numpy as np
from osgeo import gdal

from ...paths import raw_directory
from ...progress import track, blocks

from ...geo import grid, srs, valid_values, verify_alignment
from ...process import aoi_mask, clean, create_raster, mosaic
from ...publication import mask_output, publish_tiles

VERTICAL_NOTE = 'NRW heights remain in DHHN2016/NHN. No horizontal or vertical transformation; 1 m to 5 m averaging only.'


def validate_native(path):
    info = grid(path)
    with gdal.Open(str(path)) as ds:
        crs = ds.GetSpatialRef()
        if crs:
            crs = crs.Clone()
            crs.StripVertical()
        if ds.RasterCount != 1 or not crs or not crs.IsSame(srs(25832)):
            raise ValueError('DGM1 requires a single-band EPSG:25832 source.')
    transform = info['transform']
    if not all(math.isclose(transform[i], v, abs_tol=1e-8, rel_tol=0) for i, v in ((1, 1), (5, -1))):
        raise ValueError('DGM1 source must have exact 1 m pixels.')
    if any(not math.isclose(transform[i], round(transform[i]), abs_tol=1e-8, rel_tol=0) for i in (0, 3)):
        raise ValueError('DGM1 source origin must have integer-metre edges; refusing a grid shift.')


def aggregate(native, reference, destination, config, *, product="nrw", vertical_note=VERTICAL_NOTE):
    """Mean valid 5x5 native pixels, using bounded-memory, exact integer windows.

    A native-resolution VRT pads the target extent with NoData. Its source and
    destination pixels are identical: no interpolation, reprojection or shifting.
    This also supports a shared reference larger than the NRW source coverage.
    """
    validate_native(native)
    target = grid(reference)
    gt = target['transform']
    with gdal.Open(str(reference)) as ref:
        if not ref.GetSpatialRef().IsSame(srs(25832)) or gt[1] != 5 or gt[5] != -5:
            raise ValueError('DGM1 target must use 5 m EPSG:25832 pixels.')
    if any(not math.isclose(gt[i] / 5, round(gt[i] / 5), abs_tol=1e-8, rel_tol=0) for i in (0, 3)):
        raise ValueError('DGM1 target origin must have 5 m edges.')
    window = destination.with_suffix('.native_window.vrt')
    with gdal.BuildVRT(str(window), [str(native)], options=gdal.BuildVRTOptions(
            outputBounds=target['extent'], resolution='user', xRes=1, yRes=1,
            srcNodata=config['nodata'], VRTNodata=config['nodata'], strict=True)) as ds:
        if ds is None or ds.RasterXSize != target['cols'] * 5 or ds.RasterYSize != target['rows'] * 5:
            raise RuntimeError('Failed to build exact native window for DGM1 aggregation.')
    temporary = destination.with_suffix('.part.tif')
    with gdal.Open(str(window)) as src, gdal.Open(str(reference)) as ref:
        with create_raster(temporary, ref, config['nodata'], vertical_note) as dst:
            dst.SetMetadataItem('RESAMPLING', 'Mean of valid pixels in exact native 5x5 blocks')
            for x, y, width, height in blocks(ref, config['block_size'], f'{product.upper()} resampling to 5 m'):
                values, valid = valid_values(src.GetRasterBand(1), (x * 5, y * 5, width * 5, height * 5))
                counts = valid.reshape(height, 5, width, 5).sum(axis=(1, 3))
                totals = np.where(valid, values, 0).reshape(height, 5, width, 5).sum(axis=(1, 3), dtype='float64')
                means = np.full((height, width), float(config['nodata']), dtype='float64')
                np.divide(totals, counts, out=means, where=counts > 0)
                dst.GetRasterBand(1).WriteArray(means.astype('float32'), x, y)
    temporary.replace(destination)
    verify_alignment(destination, reference, config['alignment_tolerance_m'])


def prepare(tiles, geometry, reference, run_dir, config, *, product="nrw", vertical_note=VERTICAL_NOTE,
            validate=validate_native, resample=aggregate, mosaic_sources=mosaic):
    processed = run_dir / 'processed'
    work = processed / '_work'
    cleaned_dir = work / 'clean_tiles'
    stitched = run_dir / 'stitched'
    for directory in (cleaned_dir, stitched):
        directory.mkdir(parents=True, exist_ok=True)
    cleaned = []
    for source in track(tiles, f'{product.upper()} cleaning'):
        validate(source)
        destination = cleaned_dir / source.name
        clean(source, destination, config, vertical_note=vertical_note)
        cleaned.append(destination)
    merged = mosaic_sources(product, cleaned, work, config)
    averaged = work / f'{product}_5m.tif'
    resample(merged, reference, averaged, config, product=product, vertical_note=vertical_note)
    mask_path = work / 'aoi_mask.tif'
    with gdal.Open(str(reference)) as ref:
        with aoi_mask(geometry, ref, mask_path):
            pass
    prepared = work / f'{product}_prepared.tif'
    count = mask_output(averaged, mask_path, prepared, config, vertical_note)['valid_cell_count']
    verify_alignment(prepared, reference, config['alignment_tolerance_m'])
    if not count:
        raise RuntimeError(f'No valid {product.upper()} coverage inside the AOI. All-NoData output saved: {prepared}')
    published = publish_tiles(prepared, processed, stitched / f'{product}.tif', config, product=product)
    return {'prepared_raster': published['stitched'], 'comparison_ready_raster': published['stitched'],
            'processed_tiles': published, f'raw_{product}_tiles': str(raw_directory(config)),
            f'{product}_stitched': str(stitched), 'native_mosaic': str(merged),
            'resampled_raster': str(averaged), 'aoi_mask': str(mask_path),
            'grid': grid(published['stitched']), 'valid_cell_count': count,
            'hole_filling_enabled': False, 'raster_reprojection': False, 'separate_alignment': False,
            'resampling': 'average', 'source_resolution_m': 1, 'target_resolution_m': 5,
            'vertical_datum': 'DHHN2016/NHN', 'vertical_datum_note': vertical_note}
