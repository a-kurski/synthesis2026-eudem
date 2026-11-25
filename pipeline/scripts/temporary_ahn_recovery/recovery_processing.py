"""AHN processing: clean, mosaic, warp once, fill target gaps, mask, verify."""
import math
import logging
from osgeo import gdal

from ...paths import raw_directory
from ...progress import track

from ...geo import grid, verify_alignment
from ...process import align, aoi_mask, clean, mosaic
from ...acquire import write_json
from ._temporary_bounded_holes import fill_holes, settings
from ...publication import mask_output, publish_tiles
from ...target_grid import write_reference
from ...process import OPTIONS


def crop_target(source, destination, reference, padding):
    """Copy target pixels without resampling, removing the donor margin."""
    info = grid(reference)
    with gdal.Translate(str(destination), str(source), format='GTiff',
                        srcWin=[padding, padding, info['cols'], info['rows']],
                        creationOptions=OPTIONS):
        pass

VERTICAL_NOTE = 'AHN heights remain in NAP. Horizontal transformation only; no vertical datum harmonisation.'


def recover(context_warp, merged, geometry, reference, run_dir, config):
    processed = run_dir / 'processed'
    work = processed / '_work'
    stitched = run_dir / 'stitched'
    stitched.mkdir(parents=True, exist_ok=True)
    aligned, output = [work / name for name in ('aligned', 'output')]
    for directory in (aligned, output):
        directory.mkdir(parents=True, exist_ok=True)
    fill = settings(config)
    # The driver validates the saved context against the original target/halo.
    info = grid(reference)
    padding = math.ceil(fill['max_distance_m'] / info['transform'][1]) + 1
    warped = aligned / 'ahn_aligned_to_target.tif'
    logging.getLogger('dtm').info('Recovery: copying the target window from completed alignment')
    crop_target(context_warp, warped, reference, padding)
    logging.getLogger('dtm').info('Recovery: restarting filling with bounded nearest search')
    report = fill_holes(context_warp, geometry, work / 'hole_filling', config) if fill['enabled'] else None

    # Keep the unfilled baseline as one full-grid raster, without separate tiles.
    prepared = stitched / 'ahn_unfilled.tif' if settings(config)['enabled'] else output / 'ahn_prepared.tif'
    logging.getLogger('dtm').info('Recovery: masking baseline and filled outputs')
    mask_path = output / 'aoi_mask.tif'
    with gdal.Open(str(warped)) as src:
        with aoi_mask(geometry, src, mask_path) as mask:
            pass
    count = mask_output(warped, mask_path, prepared, config, VERTICAL_NOTE)['valid_cell_count']
    verify_alignment(prepared, reference, config['alignment_tolerance_m'])
    result = {'prepared_raster': str(prepared), 'comparison_ready_raster': str(prepared), 'aoi_mask': str(mask_path),
            'native_mosaic': str(merged), 'aligned_raster': str(warped),
            'grid': grid(prepared), 'valid_cell_count': count,
            'hole_filling_enabled': settings(config)['enabled'],
            'vertical_datum': 'NAP', 'vertical_datum_note': VERTICAL_NOTE}
    if settings(config)['enabled']:
        filled_warp = aligned / 'ahn_filled_aligned_to_target.tif'
        crop_target(report['filled_raster'], filled_warp, reference, padding)
        filled_prepared = output / 'ahn_prepared_filled.tif'
        filled_count = mask_output(filled_warp, mask_path, filled_prepared, config, report['note'])['valid_cell_count']
        fraction_warp = aligned / 'ahn_fill_fraction_aligned.tif'
        crop_target(report['fill_fraction_raster'], fraction_warp, reference, padding)
        # The fraction raster already spans the entire target grid; save it
        # directly instead of splitting it into tiles and stitching it again.
        fraction = stitched / 'ahn_fill_fraction.tif'
        fraction_stats = mask_output(fraction_warp, mask_path, fraction, config, report['note'], units='1')
        for path in (filled_prepared, fraction):
            verify_alignment(path, reference, config['alignment_tolerance_m'])
        if fraction_stats['valid_cell_count'] != filled_count:
            raise RuntimeError('Fill fraction and filled elevation validity counts differ.')
        report.update(stage='after_resampling', target_valid_unfilled=count, target_valid_filled=filled_count,
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
    logging.getLogger('dtm').info('Recovery: publishing final tiles and stitched COG')
    published = publish_tiles(selected, processed, stitched / 'ahn.tif', config)
    result.update(comparison_ready_raster=published['stitched'], processed_tiles=published,
                  raw_ahn_tiles=str(raw_directory(config)), ahn_stitched=str(stitched))
    if result['hole_filling_enabled']:
        result.update(prepared_raster=str(prepared), prepared_filled_raster=published['stitched'],
                      fill_fraction=str(fraction))
        report.update(prepared_filled=published['stitched'], fill_fraction=str(fraction),
                      processed_tiles=published)
        write_json(report['report_path'], report)
    else:
        result['prepared_raster'] = published['stitched']
    return result
