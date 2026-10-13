"""Validate pixel-centred XYZ, assign its declared CRS, then use shared processing."""
import json

import numpy as np
from osgeo import gdal

from ....acquire import write_json
from ....geo import grid, srs
from ....paths import receipt_path, scoped_root
from ..processing import prepare as prepare_native

VERTICAL_NOTE = ('Baden-Württemberg DGM1 heights retain DE_DHHN2016_NH (DHHN2016 normal heights). '
                 'EPSG:25832 is assigned from tile CSV metadata; no vertical transformation.')


def convert_xyz(source, destination, extent, metadata, config):
    if (metadata.get('Kachelname') != source.stem
            or metadata.get('Koordinatenreferenzsystem_Lage') != 'ETRS89_UTM32'
            or metadata.get('Koordinatenreferenzsystem_Hoehe') != 'DE_DHHN2016_NH'):
        raise ValueError(f'Unexpected or missing tile CRS/name metadata: {source.name}')
    # Border tiles may omit cells or use a different record order. Place points
    # explicitly: the XYZ driver can fill absent cells with zero.
    xyz = np.loadtxt(source, dtype='float64', ndmin=2)
    if xyz.shape[1] != 3 or not 0 < len(xyz) <= 1000000:
        raise ValueError(f'Expected 1 to 1,000,000 XYZ triples: {source.name}')
    x0, y0, x1, y1 = extent
    if x1 - x0 != 1000 or y1 - y0 != 1000:
        raise ValueError(f'Expected a 1 km filename extent: {source.name}')
    # Reuse the coordinate columns to keep memory bounded with multiple workers.
    coordinates = xyz[:, :2]
    coordinates[:, 0] -= x0 + .5
    np.subtract(y1 - .5, coordinates[:, 1], out=coordinates[:, 1])
    if (not np.isfinite(coordinates).all() or np.any(coordinates < 0) or np.any(coordinates >= 1000)):
        raise ValueError(f'XYZ coordinates differ from the regular 1 m filename extent: {source.name}')
    indices = np.rint(coordinates).astype('int32')
    if (np.any(indices >= 1000)
            or any(np.any(np.abs(coordinates[:, axis] - indices[:, axis]) > 1e-7) for axis in (0, 1))):
        raise ValueError(f'XYZ coordinates differ from the regular 1 m filename extent: {source.name}')
    cells = indices[:, 1] * 1000 + indices[:, 0]
    if np.bincount(cells).max() > 1:
        raise ValueError(f'Duplicate XYZ cell coordinates: {source.name}')
    elevations = xyz[:, 2]
    valid = np.isfinite(elevations) & (np.abs(elevations) < 1e20)
    if np.any(elevations[valid].astype('float32') == config['nodata']):
        raise ValueError(f'Undeclared elevation equals output NoData; source convention needs review: {source}')
    values = np.full(1000000, config['nodata'], dtype='float32')
    values[cells[valid]] = elevations[valid]
    part = destination.with_suffix('.part.tif')
    try:
        with gdal.GetDriverByName('GTiff').Create(str(part), 1000, 1000, 1, gdal.GDT_Float32,
                                               ['TILED=YES', 'COMPRESS=DEFLATE']) as out:
            out.SetGeoTransform((x0, 1, 0, y1, 0, -1))
            out.SetSpatialRef(srs(25832))
            out.SetMetadataItem('VERTICAL_DATUM_NOTE', VERTICAL_NOTE)
            out.GetRasterBand(1).SetNoDataValue(config['nodata'])
            out.GetRasterBand(1).WriteArray(values.reshape(1000, 1000))
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)
    return {'source_grid': {**grid(destination), 'nodata': None},
            'source_records': len(xyz), 'valid_cells': int(valid.sum()),
            'source_nodata': None, 'absent_cells': 1000000 - len(xyz),
            'invalid_elevation_cells': int((~valid).sum()),
            'nodata_policy': 'Absent cells, nonfinite and abs(value)>=1e20 excluded; no inferred source sentinel.'}



def prepare(tiles, geometry, reference, run_dir, config):
    from . import region_aoi
    result = prepare_native(tiles, region_aoi(geometry, config), reference, run_dir, config,
                            product='bw', vertical_note=VERTICAL_NOTE)
    provenance = run_dir / 'processed/source_provenance.json'
    write_json(provenance, {'producer': config['source']['producer'],
                           'vertical_datum_note': VERTICAL_NOTE,
                           'tiles': [json.loads(receipt_path(p, config).read_text(encoding='utf-8')) for p in tiles]})
    result.pop('raw_bw_tiles', None)
    result.update(source_archive=str(scoped_root(config, 'cache_root') / 'source_archive'),
                  source_provenance=str(provenance), producer=config['source']['producer'],
                  license=config['source']['license'], vertical_datum='DE_DHHN2016_NH')
    return result
