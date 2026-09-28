"""Optional native-grid AHN interpolation, with fixed donors and provenance.

FillNodata works on a disk-backed copy of the cleaned mosaic. Only estimates
inside the original AOI are accepted; original valid elevations never change.
All gaps are eligible, including water. Estimates are not measured bathymetry.
"""
import math
from pathlib import Path
import time

import numpy as np
from osgeo import gdal

from ...acquire import write_json
from ...geo import grid, valid_values, verify_alignment, windows
from ...process import aoi_mask, create_raster, OPTIONS

DEFAULTS = {'enabled': True, 'method': 'gdal_idw', 'selection': 'all_aoi_nodata',
            'max_distance_m': 20.0, 'smoothing_iterations': 0}
NOTE = 'AHN heights remain NAP. Filled cells are terrain estimates, including over water; no vertical datum transformation.'


def settings(config):
    supplied = config.get('hole_filling', {})
    if not isinstance(supplied, dict):
        raise ValueError('hole_filling must be an object.')
    unknown = set(supplied) - set(DEFAULTS)
    if unknown:
        raise ValueError(f'Unknown hole_filling settings: {sorted(unknown)}')
    result = {**DEFAULTS, **supplied}
    if type(result['enabled']) is not bool:
        raise ValueError('hole_filling.enabled must be true or false.')
    if result['method'] != 'gdal_idw' or result['selection'] != 'all_aoi_nodata':
        raise ValueError('Supported filling: method=gdal_idw, selection=all_aoi_nodata.')
    distance = result['max_distance_m']
    if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance <= 0:
        raise ValueError('hole_filling.max_distance_m must be a finite positive number.')
    if type(result['smoothing_iterations']) is not int or result['smoothing_iterations'] != 0:
        raise ValueError('Initial hole filling supports smoothing_iterations=0 only.')
    return result


def byte_raster(path, reference):
    ds = gdal.GetDriverByName('GTiff').Create(str(path), reference.RasterXSize, reference.RasterYSize,
                                            1, gdal.GDT_Byte, ['TILED=YES', 'COMPRESS=DEFLATE', 'BIGTIFF=IF_SAFER'])
    ds.SetProjection(reference.GetProjection())
    ds.SetGeoTransform(reference.GetGeoTransform())
    return ds


def fill_holes(source, geometry, directory, config):
    """Return paths/report for a NEW filled native raster; source stays read-only.

    All candidates are evaluated against the original donor mask in a single
    GDAL call. Output merging/statistics are blockwise. The temporary GDAL files
    live beside the derivatives, not in an uncontrolled system temp directory.
    """
    options = settings(config)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    info = grid(source)
    pixel_size = info['transform'][1]
    if not math.isclose(pixel_size, .5, abs_tol=1e-8, rel_tol=0) or not math.isclose(info['transform'][5], -.5, abs_tol=1e-8, rel_tol=0):
        raise ValueError('Hole filling requires the native 0.5 m AHN grid.')
    from ...geo import srs
    with gdal.Open(str(source)) as check:
        if not check.GetSpatialRef().IsSame(srs(28992)):
            raise ValueError('Hole filling requires EPSG:28992.')
    search_pixels = options['max_distance_m'] / pixel_size
    filled = directory / 'ahn_filled_native.tif'
    temporary = directory / 'ahn_filled_native.part.tif'
    donor_path = directory / 'original_valid_mask.tif'
    aoi_path = directory / 'aoi_mask_native.tif'
    fill_mask_path = directory / 'ahn_fill_mask_native.tif'
    fraction_path = directory / 'ahn_fill_fraction_native.tif'
    original_count = candidate_count = filled_count = aoi_count = 0
    with gdal.Open(str(source)) as src:
        with aoi_mask(geometry, src, aoi_path, epsg=28992) as aoi:
            with byte_raster(donor_path, src) as donors:
                with gdal.GetDriverByName('GTiff').CreateCopy(str(temporary), src, options=OPTIONS) as candidate:
                    candidate.GetRasterBand(1).SetNoDataValue(config['nodata'])
                    for window in windows(src, config['block_size']):
                        values, valid = valid_values(src.GetRasterBand(1), window)
                        donors.GetRasterBand(1).WriteArray(valid.astype('uint8'), window[0], window[1])
                        candidate.GetRasterBand(1).WriteArray(np.where(valid, values, config['nodata']).astype('float32'), window[0], window[1])
                    donors.FlushCache()
                    candidate.FlushCache()
                    previous_tmp = gdal.GetThreadLocalConfigOption('CPL_TMPDIR')
                    gdal.SetThreadLocalConfigOption('CPL_TMPDIR', str(directory.resolve()))
                    try:
                        error = gdal.FillNodata(candidate.GetRasterBand(1), donors.GetRasterBand(1),
                                                search_pixels, 0, options=['INTERPOLATION=INV_DIST', 'TEMP_FILE_DRIVER=GTiff'])
                        if error != gdal.CE_None:
                            raise RuntimeError('GDAL hole interpolation failed.')
                    finally:
                        gdal.SetThreadLocalConfigOption('CPL_TMPDIR', previous_tmp)
                    with byte_raster(fill_mask_path, src) as fill_mask:
                        with create_raster(fraction_path, src, config['nodata'], NOTE) as fractions:
                            fractions.GetRasterBand(1).SetUnitType('1')
                            fractions.SetMetadataItem('DESCRIPTION', '0=original valid, 1=accepted fill, NoData=remaining invalid; average warp gives filled share of valid contribution')
                            for window in windows(src, config['block_size']):
                                values, valid = valid_values(src.GetRasterBand(1), window)
                                inside = aoi.GetRasterBand(1).ReadAsArray(*window) != 0
                                estimates, estimate_valid = valid_values(candidate.GetRasterBand(1), window)
                                wanted = inside & ~valid
                                accepted = wanted & estimate_valid
                                merged = np.where(valid, values, config['nodata']).astype('float32')
                                merged[accepted] = estimates[accepted]
                                candidate.GetRasterBand(1).WriteArray(merged, window[0], window[1])
                                fill_mask.GetRasterBand(1).WriteArray(accepted.astype('uint8'), window[0], window[1])
                                contribution = np.full(values.shape, config['nodata'], dtype='float32')
                                contribution[valid] = 0
                                contribution[accepted] = 1
                                fractions.GetRasterBand(1).WriteArray(contribution, window[0], window[1])
                                original_count += int((inside & valid).sum())
                                candidate_count += int(wanted.sum())
                                filled_count += int(accepted.sum())
                                aoi_count += int(inside.sum())
                    candidate.SetMetadataItem('VERTICAL_DATUM_NOTE', NOTE)
                    candidate.SetMetadataItem('HOLE_FILLING', f'GDAL inverse distance; {options["max_distance_m"]} m; no smoothing; original AHN donors only')
    temporary.replace(filled)
    verify_alignment(source, filled, config['alignment_tolerance_m'])
    pixel_area = abs(info['transform'][1] * info['transform'][5])
    report = {'settings': options, 'gdal_version': gdal.VersionInfo('--version'),
              'source': str(source), 'source_grid': info, 'max_search_pixels': search_pixels,
              'aoi_cell_count': aoi_count, 'original_valid_cell_count': original_count,
              'candidate_cell_count': candidate_count, 'filled_cell_count': filled_count,
              'remaining_nodata_cell_count': candidate_count - filled_count,
              'valid_cell_count_after': original_count + filled_count,
              'candidate_area_m2': candidate_count * pixel_area,
              'filled_area_m2': filled_count * pixel_area,
              'remaining_nodata_area_m2': (candidate_count - filled_count) * pixel_area,
              'percent_candidates_filled': 100 * filled_count / candidate_count if candidate_count else 0.0,
              'elapsed_seconds': time.perf_counter() - started,
              'vertical_datum': 'NAP', 'note': NOTE,
              'filled_native': str(filled), 'native_fill_mask': str(fill_mask_path),
              'native_fill_fraction': str(fraction_path)}
    report_path = directory / 'hole_filling_report.json'
    report['report_path'] = str(report_path)
    write_json(report_path, report)
    return report
