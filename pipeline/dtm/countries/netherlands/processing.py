"""AHN-specific processing: clean, mosaic, warp once, clean/mask, verify."""
import numpy as np
from osgeo import gdal

from ...geo import grid, valid_values, verify_alignment, windows
from ...process import align, aoi_mask, clean, create_raster, mosaic
from ...acquire import write_json
from .hole_filling import fill_holes, settings
from .stitching import publish_tiles

VERTICAL_NOTE = 'AHN heights remain in NAP. Horizontal transformation only; no vertical datum harmonisation.'


def mask_output(warped, mask_path, prepared, config, note=VERTICAL_NOTE, units='m'):
    """Final clean/mask pass shared by heights and dimensionless fill fractions."""
    temp = prepared.with_suffix('.part.tif')
    count = influenced = 0
    total = maximum = 0.0
    with gdal.Open(str(warped)) as src, gdal.Open(str(mask_path)) as mask:
        with create_raster(temp, src, config['nodata'], note) as dst:
            dst.GetRasterBand(1).SetUnitType(units)
            dst.SetMetadataItem('PREPARATION', 'Average-resampled to target grid; valid cells inside pixel-centre AOI mask')
            for window in windows(src, config['block_size']):
                values, valid = valid_values(src.GetRasterBand(1), window)
                valid &= mask.GetRasterBand(1).ReadAsArray(*window) != 0
                count += int(valid.sum())
                dst.GetRasterBand(1).WriteArray(np.where(valid, values, config['nodata']).astype('float32'), window[0], window[1])
                if units == '1' and valid.any():
                    selected = values[valid]
                    if np.any((selected < 0) | (selected > 1)):
                        raise RuntimeError('Fill fraction outside [0, 1].')
                    influenced += int((selected > 0).sum())
                    total += float(selected.astype('float64').sum())
                    maximum = max(maximum, float(selected.max()))
    temp.replace(prepared)
    return {'valid_cell_count': count, 'cells_with_fill_contribution': influenced,
            'mean_fill_fraction_over_valid_cells': total / count if count else None,
            'max_fill_fraction': maximum if count else None}


def prepare(tiles, geometry, reference, run_dir, config):
    (run_dir / 'raw_ahn_tiles').mkdir(parents=True, exist_ok=True)
    processed = run_dir / 'processed_tiles'
    work = processed / '_work'
    stitched = run_dir / 'ahn_stitched'
    stitched.mkdir(parents=True, exist_ok=True)
    mosaics, aligned, output = [work / name for name in ('mosaics', 'aligned', 'output')]
    for directory in (mosaics, aligned, output):
        directory.mkdir(parents=True, exist_ok=True)
    cleaned_dir = mosaics / 'ahn_clean_tiles'
    cleaned_dir.mkdir()
    cleaned = []
    for source in tiles:
        destination = cleaned_dir / source.name
        clean(source, destination, config, vertical_note=VERTICAL_NOTE)
        cleaned.append(destination)
    merged = mosaic('ahn', cleaned, mosaics, config)
    warped = aligned / 'ahn_aligned_to_target.tif'
    align(merged, reference, warped, config)

    # Keep the unfilled baseline as one full-grid raster, without separate tiles.
    prepared = stitched / 'ahn_unfilled.tif' if settings(config)['enabled'] else output / 'ahn_prepared.tif'
    mask_path = output / 'aoi_mask.tif'
    with gdal.Open(str(warped)) as src:
        with aoi_mask(geometry, src, mask_path) as mask:
            pass
    count = mask_output(warped, mask_path, prepared, config)['valid_cell_count']
    verify_alignment(prepared, reference, config['alignment_tolerance_m'])
    result = {'prepared_raster': str(prepared), 'comparison_ready_raster': str(prepared), 'aoi_mask': str(mask_path),
            'native_mosaic': str(merged), 'aligned_raster': str(warped),
            'grid': grid(prepared), 'valid_cell_count': count,
            'hole_filling_enabled': settings(config)['enabled'],
            'vertical_datum': 'NAP', 'vertical_datum_note': VERTICAL_NOTE}
    if settings(config)['enabled']:
        report = fill_holes(merged, geometry, work / 'hole_filling', config)
        filled_warp = aligned / 'ahn_filled_aligned_to_target.tif'
        align(report['filled_native'], reference, filled_warp, config)
        filled_prepared = output / 'ahn_prepared_filled.tif'
        filled_count = mask_output(filled_warp, mask_path, filled_prepared, config, report['note'])['valid_cell_count']
        fraction_warp = aligned / 'ahn_fill_fraction_aligned.tif'
        align(report['native_fill_fraction'], reference, fraction_warp, config)
        # The fraction raster already spans the entire target grid; save it
        # directly instead of splitting it into tiles and stitching it again.
        fraction = stitched / 'ahn_fill_fraction.tif'
        fraction_stats = mask_output(fraction_warp, mask_path, fraction, config, report['note'], units='1')
        for path in (filled_prepared, fraction):
            verify_alignment(path, reference, config['alignment_tolerance_m'])
        if fraction_stats['valid_cell_count'] != filled_count:
            raise RuntimeError('Fill fraction and filled elevation validity counts differ.')
        report.update(target_valid_unfilled=count, target_valid_filled=filled_count,
                      target_new_valid_cells=filled_count - count, target_fill_fraction=fraction_stats,
                      prepared_filled=str(filled_prepared), fill_fraction=str(fraction))
        write_json(report['report_path'], report)
        result.update(comparison_ready_raster=str(filled_prepared), prepared_filled_raster=str(filled_prepared),
                      filled_valid_cell_count=filled_count, fill_fraction=str(fraction),
                      hole_filling_report=report['report_path'], hole_filling=report)
        count = filled_count
    if not count:
        raise RuntimeError(f'No valid AHN coverage inside the AOI on the target grid. All-NoData output saved: {prepared}')
    # Publish finished German-grid tiles, then assemble the user-facing TIFF.
    selected = result['comparison_ready_raster']
    published = publish_tiles(selected, processed, stitched / 'ahn.tif', config)
    result.update(comparison_ready_raster=published['stitched'], processed_tiles=published,
                  raw_ahn_tiles=str(run_dir / 'raw_ahn_tiles'), ahn_stitched=str(stitched))
    if result['hole_filling_enabled']:
        result.update(prepared_raster=str(prepared), prepared_filled_raster=published['stitched'],
                      fill_fraction=str(fraction))
        report.update(prepared_filled=published['stitched'], fill_fraction=str(fraction),
                      processed_tiles=published)
        write_json(report['report_path'], report)
    else:
        result['prepared_raster'] = published['stitched']
    return result
