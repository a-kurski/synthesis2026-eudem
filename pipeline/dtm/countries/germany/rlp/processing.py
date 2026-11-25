"""Prepare official RLP tiles on either of the observed native 1 m lattices."""
from osgeo import gdal

from ....geo import grid, rlp_nominal_bounds, srs, validate_tile, verify_alignment
from ....process import OPTIONS, align, mosaic
from ....progress import track
from ....target_grid import write_reference
from ..processing import aggregate, prepare as prepare_native

VERTICAL_NOTE = ('RLP heights remain in DHHN2016/NHN (EPSG:7837), as declared by '
                 'the official DGM1 dataset metadata where the TIFF omits the vertical CRS. '
                 'No vertical transformation; averaging onto the common 5 m grid.')


def mosaic_on_target_lattice(product, tiles, work, config):
    """Own each nominal kilometre once; never mosaic different 1 m lattices.

    The 1001-sample tiles extend half a metre beyond their nominal footprint.
    Area averaging into 200 x 200 cells uses these edge samples without shifting
    their coordinates. Adjacent output tiles have no overlap. Integer-edge
    sources retain the exact 5 x 5 aggregation, even in a mixed-layout run.
    """
    directory = work / 'tiles_5m'
    directory.mkdir(parents=True, exist_ok=True)
    outputs = []
    for path in track(tiles, 'RLP aligning tile grids'):
        info = grid(path)
        box = rlp_nominal_bounds(info)
        target = {'cols': 200, 'rows': 200, 'extent': box,
                  'transform': [box[0], 5, 0, box[3], 0, -5],
                  'crs': srs(25832).ExportToWkt()}
        reference = write_reference(target, directory / (path.stem + '.reference.vrt'))
        destination = directory / path.name
        if info['cols'] == 1000:
            aggregate(path, reference, destination, config, product=product, vertical_note=VERTICAL_NOTE)
        else:
            # align() uses an explicit horizontal CRS and -novshift.
            # clean() has already converted the source sentinel to config NoData.
            align(path, reference, destination, config, source_epsg=25832, label='RLP')
            with gdal.Open(str(destination), gdal.GA_Update) as ds:
                ds.SetMetadataItem('VERTICAL_DATUM_NOTE', VERTICAL_NOTE)
                ds.SetMetadataItem('RESAMPLING', 'Area-weighted average from half-metre-edge 1 m pixels')
        outputs.append(destination)
    return mosaic(product, outputs, work, config)


def copy_target_window(native, reference, destination, config, *, product, vertical_note):
    """Crop/pad an already aligned 5 m mosaic without another interpolation."""
    target = grid(reference)
    source = grid(native)
    if source['transform'][1] != 5 or source['transform'][5] != -5:
        raise ValueError('RLP aligned mosaic must have 5 m pixels.')
    window = destination.with_suffix('.target_window.vrt')
    with gdal.BuildVRT(str(window), [str(native)], options=gdal.BuildVRTOptions(
            outputBounds=target['extent'], resolution='user', xRes=5, yRes=5,
            srcNodata=config['nodata'], VRTNodata=config['nodata'], strict=True)):
        pass
    verify_alignment(window, reference, config['alignment_tolerance_m'])
    temporary = destination.with_suffix('.part.tif')
    with gdal.Translate(str(temporary), str(window), format='GTiff',
                        outputType=gdal.GDT_Float32, creationOptions=OPTIONS) as ds:
        ds.SetMetadataItem('VERTICAL_DATUM_NOTE', vertical_note)
        ds.SetMetadataItem('RESAMPLING', 'Per-kilometre 5 m means; area-weighted for half-metre-edge sources')
    temporary.replace(destination)
    verify_alignment(destination, reference, config['alignment_tolerance_m'])


def prepare(tiles, geometry, reference, run_dir, config):
    def validate(path):
        info = grid(path)
        validate_tile(path, config['source'], {'bounds': rlp_nominal_bounds(info)})

    alternate = False
    footprints = set()
    for path in tiles:
        info = grid(path)
        footprint = tuple(rlp_nominal_bounds(info))
        if footprint in footprints:
            raise ValueError(f'Duplicate RLP kilometre footprint: {footprint}')
        footprints.add(footprint)
        alternate |= info['cols'] == 1001
    options = {'validate': validate}
    if alternate:
        options.update(mosaic_sources=mosaic_on_target_lattice, resample=copy_target_window)
    result = prepare_native(tiles, geometry, reference, run_dir, config,
                            product='rlp', vertical_note=VERTICAL_NOTE, **options)
    result.update(source_grid_layout='mixed_or_half_metre_edges' if alternate else 'integer_edges',
                  vertical_datum_basis='Embedded CRS or official RLP DGM1 dataset declaration',
                  vertical_datum_metadata_url='https://metaportal.rlp.de/gui/html/ab69aa3d-e786-41f8-95dc-7b34abb06c41',
                  separate_alignment=alternate)
    if alternate:
        result['aligned_5m_mosaic'] = result.pop('native_mosaic')
        result['resampling_detail'] = ('Exact 5x5 means for integer-edge tiles; area-weighted means '
                                       'for half-metre-edge tiles, clipped to nominal kilometre footprints.')
    return result
