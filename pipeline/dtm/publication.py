"""Shared final masking and lossless publication of target-grid terrain tiles."""
from pathlib import Path
import math

import numpy as np
from osgeo import gdal

from .acquire import write_json
from .geo import grid, valid_values, verify_alignment, windows
from .process import create_raster
from .progress import blocks, gdal_progress, track


COG_OPTIONS = ['COMPRESS=DEFLATE', 'PREDICTOR=FLOATING_POINT', 'BIGTIFF=YES',
               'BLOCKSIZE=512', 'OVERVIEWS=IGNORE_EXISTING',
               'OVERVIEW_RESAMPLING=AVERAGE']


def write_cog(source, destination):
    """Publish lossless Float32 terrain with internal display overviews.

    Set metadata on the source before calling: updating a finished COG can
    invalidate its optimized layout. Keep the old destination until success.
    """
    destination = Path(destination)
    temporary = destination.with_suffix('.cog.part.tif')
    if gdal.GetDriverByName('COG') is None:
        raise RuntimeError('This GDAL installation does not provide the COG driver.')
    with gdal_progress('Writing COG ' + destination.name) as callback:
        with gdal.Translate(str(temporary), source, format='COG',
                            creationOptions=COG_OPTIONS, callback=callback):
            pass
    with gdal.Open(str(temporary)) as check:
        if check.GetMetadataItem('LAYOUT', 'IMAGE_STRUCTURE') != 'COG':
            raise RuntimeError(f'Output is not a Cloud Optimized GeoTIFF: {temporary}')
        if max(check.RasterXSize, check.RasterYSize) > 512 and check.GetRasterBand(1).GetOverviewCount() == 0:
            raise RuntimeError(f'COG output is missing internal overviews: {temporary}')
    temporary.replace(destination)


def mask_output(warped, mask_path, prepared, config, note='Heights retain their source vertical datum.', units='m'):
    """Final clean/mask pass shared by heights and dimensionless fill fractions."""
    temp = prepared.with_suffix('.part.tif')
    count = influenced = 0
    total = maximum = 0.0
    with gdal.Open(str(warped)) as src, gdal.Open(str(mask_path)) as mask:
        with create_raster(temp, src, config['nodata'], note) as dst:
            dst.GetRasterBand(1).SetUnitType(units)
            dst.SetMetadataItem('PREPARATION', 'Average-resampled to target grid; valid cells inside pixel-centre AOI mask')
            for window in blocks(src, config['block_size'], 'Masking ' + prepared.name):
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
    write_cog(str(temp), prepared)
    temp.unlink()
    return {'valid_cell_count': count, 'cells_with_fill_contribution': influenced,
            'mean_fill_fraction_over_valid_cells': total / count if count else None,
            'max_fill_fraction': maximum if count else None}


def publish_tiles(source, directory, destination, config, product='ahn'):
    directory, destination = Path(directory), Path(destination)
    directory.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tile_size = config.get('processed_tile_size_pixels', 1000)
    if type(tile_size) is not int or tile_size < 1:
        raise ValueError('processed_tile_size_pixels must be a positive integer.')
    records = []
    paths = []
    with gdal.Open(str(source)) as src:
        unit = src.GetRasterBand(1).GetUnitType()
        metadata = src.GetMetadata()
        total = math.ceil(src.RasterXSize / tile_size) * math.ceil(src.RasterYSize / tile_size)
        for x, y, width, height in track(windows(src, tile_size), product.upper() + ' publishing', total):
            path = directory / f'{product}_r{y:07d}_c{x:07d}.tif'
            # Windowed Translate may omit the band's unit. Restore it on a
            # virtual source before COG creation, never on the finished TIFF.
            with gdal.Translate('', src, format='VRT', srcWin=[x, y, width, height]) as view:
                view.GetRasterBand(1).SetUnitType(unit)
                write_cog(view, path)
            paths.append(str(path.resolve()))
            records.append({'path': str(path), 'column': x, 'row': y, 'cols': width, 'rows': height})
    # Tile list is explicit: no tiles from previous runs can enter the mosaic.
    vrt = destination.with_suffix('.vrt')
    with gdal.BuildVRT(str(vrt), paths, options=gdal.BuildVRTOptions(resolution='highest', strict=True,
                       srcNodata=config['nodata'], VRTNodata=config['nodata'])) as ds:
        if ds is None:
            raise RuntimeError('Failed to build processed-tile mosaic.')
        ds.SetMetadata(metadata)
        ds.GetRasterBand(1).SetUnitType(unit)
    write_cog(str(vrt), destination)
    verify_alignment(source, destination, config['alignment_tolerance_m'])
    # Verify actual values, including NoData; a matching grid alone is not enough.
    with gdal.Open(str(source)) as src, gdal.Open(str(destination)) as dst:
        for window in blocks(src, config['block_size'], product.upper() + ' verification'):
            if not np.array_equal(src.GetRasterBand(1).ReadAsArray(*window), dst.GetRasterBand(1).ReadAsArray(*window)):
                raise RuntimeError('Stitched pixels differ from the processed surface.')
    manifest = directory / 'tiles.json'
    write_json(manifest, {'grid': grid(destination), 'tile_size_pixels': tile_size,
                         'format': 'COG', 'creation_options': COG_OPTIONS,
                         'tiles': records, 'stitched_raster': str(destination)})
    return {'directory': str(directory), 'count': len(records), 'manifest': str(manifest), 'stitched': str(destination)}
