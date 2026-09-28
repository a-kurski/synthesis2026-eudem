"""Publish complete target-grid tiles, then stitch them without resampling.

Tiles are non-overlapping integer windows on the German target grid, not the
skewed footprints of Dutch download tiles. Shared native processing prevents
interpolation seams; this publication stage preserves the resulting pixels.
"""
from pathlib import Path

import numpy as np
from osgeo import gdal

from ...acquire import write_json
from ...geo import grid, verify_alignment, windows
from ...process import OPTIONS


def publish_tiles(source, directory, destination, config):
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
        for x, y, width, height in windows(src, tile_size):
            path = directory / f'ahn_r{y:07d}_c{x:07d}.tif'
            with gdal.Translate(str(path), src, format='GTiff', srcWin=[x, y, width, height], creationOptions=OPTIONS) as tile:
                tile.GetRasterBand(1).SetUnitType(unit)
            paths.append(str(path.resolve()))
            records.append({'path': str(path), 'column': x, 'row': y, 'cols': width, 'rows': height})
    # Tile list is explicit: no tiles from previous runs can enter the mosaic.
    vrt = destination.with_suffix('.vrt')
    with gdal.BuildVRT(str(vrt), paths, options=gdal.BuildVRTOptions(resolution='highest', strict=True,
                       srcNodata=config['nodata'], VRTNodata=config['nodata'])) as ds:
        if ds is None:
            raise RuntimeError('Failed to build processed-tile mosaic.')
    temporary = destination.with_suffix('.part.tif')
    with gdal.Open(str(vrt)) as virtual:
        with gdal.Translate(str(temporary), virtual, format='GTiff', creationOptions=OPTIONS) as stitched:
            stitched.SetMetadata(metadata)
            stitched.GetRasterBand(1).SetUnitType(unit)
    temporary.replace(destination)
    verify_alignment(source, destination, config['alignment_tolerance_m'])
    # Verify actual values, including NoData; a matching grid alone is not enough.
    with gdal.Open(str(source)) as src, gdal.Open(str(destination)) as dst:
        for window in windows(src, config['block_size']):
            if not np.array_equal(src.GetRasterBand(1).ReadAsArray(*window), dst.GetRasterBand(1).ReadAsArray(*window)):
                raise RuntimeError('Stitched pixels differ from the processed surface.')
    manifest = directory / 'tiles.json'
    write_json(manifest, {'grid': grid(destination), 'tile_size_pixels': tile_size,
                         'tiles': records, 'stitched_raster': str(destination)})
    return {'directory': str(directory), 'count': len(records), 'manifest': str(manifest), 'stitched': str(destination)}
