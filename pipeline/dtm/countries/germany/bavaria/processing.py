"""Strict cell-centre XYZ conversion and lossless native-grid preparation."""
import json
import math

import numpy as np
from osgeo import gdal

from ....acquire import write_json
from ....geo import grid, srs, verify_alignment
from ....paths import receipt_path, scoped_root
from ....process import OPTIONS, align
from ..processing import prepare as prepare_native

VERTICAL_NOTE = 'Bavaria DGM5 heights retain DHHN2016/NHN; no vertical transformation.'
# Complete tiles convert identically; existing validated derivatives remain reusable.
CONVERSION_VERSION = 1


def validate_native(path, extent=None):
    info = grid(path)
    with gdal.Open(str(path)) as ds:
        if (ds.RasterCount != 1 or not ds.GetSpatialRef() or not ds.GetSpatialRef().IsSame(srs(25832))
                or info['dtype'] != 'Float32' or info['transform'][1:3] != [5, 0]
                or info['transform'][4:] != [0, -5]):
            raise ValueError(f'Expected one-band Float32 DGM5 in EPSG:25832: {path}')
    if extent is not None:
        x0, y0, x1, y1 = info['extent']
        if (not 1 <= info['cols'] <= 200 or not 1 <= info['rows'] <= 200
                or x0 + 2.5 < extent[0] or y0 + 2.5 < extent[1]
                or x1 - 2.5 >= extent[2] or y1 - 2.5 >= extent[3]):
            raise ValueError(f'DGM5 cell centres lie outside the filename extent: {path}')
    return info


def read_xyz(source, extent):
    """Accept complete native rectangles, including cropped/shifted boundary grids."""
    xyz = np.loadtxt(source, dtype='float64', ndmin=2, comments=None)
    if xyz.shape[1] != 3 or not 1 <= len(xyz) <= 40000 or not np.isfinite(xyz[:, :2]).all():
        raise ValueError('Malformed XYZ: expected 1 to 40,000 finite coordinate triples.')
    xs, ys = np.unique(xyz[:, 0]), np.unique(xyz[:, 1])[::-1]
    cols, rows = len(xs), len(ys)
    if (cols > 200 or rows > 200 or cols * rows != len(xyz)
            or np.any(np.diff(xs) != 5) or np.any(np.diff(ys) != -5)
            or not np.array_equal(xyz[:, 0], np.tile(xs, rows))
            or not np.array_equal(xyz[:, 1], np.repeat(ys, cols))):
        raise ValueError('Duplicate, missing, out-of-order or off-grid XYZ coordinates within native rectangle.')
    if xs[0] < extent[0] or xs[-1] >= extent[2] or ys[-1] < extent[1] or ys[0] >= extent[3]:
        raise ValueError('XYZ cell centres lie outside the filename extent.')
    transform = (float(xs[0] - 2.5), 5, 0, float(ys[0] + 2.5), 0, -5)
    return xyz[:, 2].reshape(rows, cols), transform


def convert_xyz(source, destination, extent, config):
    values, transform = read_xyz(source, extent)
    marker = config['source'].get('nodata')
    missing = values == marker if marker is not None else np.zeros(values.shape, dtype=bool)
    # Unknown conventions are errors, never invented holes or elevations.
    if np.any(~missing & (~np.isfinite(values) | (np.abs(values) >= 1e20))):
        raise ValueError('Nonfinite/unsupported XYZ elevation; source NoData convention needs review.')
    values = values.astype('float32')
    if np.any(~missing & (values == config['nodata'])):
        raise ValueError(f'{source.name}: {(~missing & (values == config["nodata"])).sum()} elevations '
                         'collide with output NoData. Set source.nodata and source.nodata_evidence '
                         'only after reviewing the source missing-value convention.')
    values[missing] = config['nodata']
    part = destination.with_suffix('.part.tif')
    try:
        with gdal.GetDriverByName('GTiff').Create(str(part), values.shape[1], values.shape[0], 1, gdal.GDT_Float32, OPTIONS) as ds:
            ds.SetProjection(srs(25832).ExportToWkt())
            ds.SetGeoTransform(transform)
            ds.SetMetadataItem('VERTICAL_DATUM_NOTE', VERTICAL_NOTE)
            ds.SetMetadataItem('SOURCE_PRODUCT', 'Bavaria DGM5')
            ds.GetRasterBand(1).SetNoDataValue(config['nodata'])
            ds.GetRasterBand(1).SetUnitType('m')
            ds.GetRasterBand(1).WriteArray(values)
        info = validate_native(part, extent)
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)
    return {'source_grid': info, 'nominal_tile_extent': extent,
            'valid_cells': int((~missing).sum()), 'absent_cells': 40000 - values.size,
            'coverage_note': 'Absent cells count is relative to a nominal 200x200 tile; no missing elevations are invented.',
            'explicit_nodata_cells': int(missing.sum()), 'source_nodata': marker}


def same_lattice(native, reference):
    a, b = grid(native)['transform'], grid(reference)['transform']
    return all(math.isclose((a[i] - b[i]) / 5, round((a[i] - b[i]) / 5),
                            rel_tol=0, abs_tol=1e-9) for i in (0, 3))


def native_mosaics(name, tiles, directory, config):
    """Mosaic matching lattices only; never let BuildVRT snap shifted sources."""
    groups = {}
    for path in tiles:
        transform = grid(path)['transform']
        key = tuple(round(transform[i] % 5, 8) for i in (0, 3))
        groups.setdefault(key, []).append(str(path.resolve()))
    paths = []
    for index, sources in enumerate(groups.values()):
        path = directory / f'{name}_native_{index}.vrt'
        with gdal.BuildVRT(str(path), sources, options=gdal.BuildVRTOptions(
                resolution='highest', strict=True, srcNodata=config['nodata'], VRTNodata=config['nodata'])):
            pass
        paths.append(path)
    return paths


def align_native(native, reference, destination, config, **kwargs):
    sources = native if isinstance(native, list) else [native]
    target = grid(reference)
    with gdal.Open(str(reference)) as ref:
        if not ref.GetSpatialRef().IsSame(srs(25832)) or target['transform'][1:3] != [5, 0] or target['transform'][4:] != [0, -5]:
            raise ValueError('DGM5 target must be a north-up 5 m EPSG:25832 grid.')
    if len(sources) == 1 and same_lattice(sources[0], reference):
        # Identical source/destination cells; VRT also pads uncovered areas.
        with gdal.BuildVRT('', [str(sources[0])], options=gdal.BuildVRTOptions(
                outputBounds=target['extent'], resolution='user', xRes=5, yRes=5,
                srcNodata=config['nodata'], VRTNodata=config['nodata'], strict=True)) as view:
            with gdal.Translate(str(destination), view, format='GTiff', creationOptions=OPTIONS):
                pass
    else:
        # One average warp of native-lattice mosaics, not a warp for each tile.
        # Where boundary footprints overlap, prefer valid cells on the target lattice.
        sources = sorted(sources, key=lambda p: same_lattice(p, reference))
        align(sources, reference, destination, config, source_epsg=25832, label='Bavaria')
    verify_alignment(destination, reference, config['alignment_tolerance_m'])


def prepare(tiles, geometry, reference, run_dir, config):
    from . import region_aoi
    aligned = all(same_lattice(tile, reference) for tile in tiles)
    method = 'copy/window without interpolation' if aligned else 'average (one mosaic alignment)'
    source = config['source']
    metadata = {'SOURCE_PRODUCT': 'Bavaria DGM5', 'ATTRIBUTION': source['attribution'],
                'LICENSE': source['license'], 'LICENSE_URL': source['license_url'],
                'SOURCE_URL': source['website'], 'PREPARATION': method + '; pixel-centre polygon AOI mask'}
    result = prepare_native(tiles, region_aoi(geometry, config), reference, run_dir, config,
                            product='bavaria', vertical_note=VERTICAL_NOTE, validate=validate_native,
                            resample=align_native, mosaic_sources=native_mosaics, metadata=metadata)
    provenance = run_dir / 'processed/source_provenance.json'
    write_json(provenance, {'source': source, 'vertical_datum_note': VERTICAL_NOTE,
                           'modifications': method + '; XYZ conversion, mosaic, AOI mask and COG publication',
                           'overlap_policy': 'Last valid mosaic wins; target-lattice mosaics are supplied last.',
                           'tiles': [json.loads(receipt_path(p, config).read_text(encoding='utf-8')) for p in tiles]})
    result.update(source_resolution_m=5, resampling=method, separate_alignment=not aligned,
                  source_archive=str(scoped_root(config, 'cache_root') / 'source_archive'),
                  source_provenance=str(provenance), producer=source['producer'], license=source['license'])
    result.pop('native_mosaic', None)
    result['native_mosaics'] = [str(p) for p in sorted((run_dir / 'processed/_work').glob('bavaria_native_*.vrt'))]
    return result
