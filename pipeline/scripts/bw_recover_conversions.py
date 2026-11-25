"""Adopt verified per-run BW TIFFs into the persistent cache without XYZ parsing."""
from pathlib import Path, PurePosixPath
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def recover(config, directory):
    import json
    import os
    import shutil
    import numpy as np
    from osgeo import gdal
    from dtm.acquire import sha256, write_json
    from dtm.countries.germany.bw.acquisition import CHILD, CONVERSION_VERSION, filename_bounds
    from dtm.countries.germany.processing import validate_native
    from dtm.geo import grid
    from dtm.paths import raw_directory, receipt_path, region_lock, scoped_root
    from dtm.progress import track

    if config['country'] != 'germany' or config['region'] != 'bw':
        raise ValueError('Recovery requires a Germany/BW config.')
    sources = sorted(directory.glob('*.tif'))
    if not sources:
        raise ValueError(f'No TIFFs found in {directory}')
    hashes = {}
    count = 0
    with region_lock(config):
        target = raw_directory(config)
        target.mkdir(parents=True, exist_ok=True)
        for source in track(sources, 'BW recovering converted tiles'):
            record = json.loads(source.with_suffix('.json').read_text(encoding='utf-8'))
            member = PurePosixPath(record['member'])
            extent = filename_bounds(member.name, CHILD, 1000)
            if member.with_suffix('.tif').name != source.name or record['source'] != config['source']:
                raise ValueError(f'Source identity mismatch: {source}')
            if sha256(source) != record['sha256']:
                raise ValueError(f'TIFF differs from receipt: {source}')
            archive = scoped_root(config, 'cache_root') / 'source_archive' / PurePosixPath(record['archive'].replace('\\', '/')).name
            if archive not in hashes:
                hashes[archive] = sha256(archive)
            if hashes[archive] != record['archive_sha256']:
                raise ValueError(f'Archive differs from receipt: {archive}')
            validate_native(source)
            info = grid(source)
            if (info['extent'] != extent or info['cols'] != 1000 or info['rows'] != 1000
                    or info['dtype'] != 'Float32' or info['nodata'] != config['nodata']):
                raise ValueError(f'Unexpected converted grid: {source}')
            with gdal.Open(str(source)) as ds:
                values = ds.ReadAsArray()
                valid = values != config['nodata']
                if (not np.isfinite(values).all() or np.any(np.abs(values[valid]) >= 1e20)
                        or int(valid.sum()) != record['valid_cells']):
                    raise ValueError(f'Invalid converted elevations/count: {source}')
            destination = target / source.name
            if destination.exists():
                if sha256(destination) != record['sha256']:
                    raise ValueError(f'Conflicting cache tile; leaving it untouched: {destination}')
            else:
                try:
                    os.link(source, destination)
                except OSError:
                    part = destination.with_suffix('.recovery.part')
                    shutil.copyfile(source, part)
                    part.replace(destination)
            receipt = receipt_path(destination, config)
            receipt.parent.mkdir(parents=True, exist_ok=True)
            write_json(receipt, {**record, 'archive': str(archive), 'bounds': extent,
                                'conversion_version': CONVERSION_VERSION,
                                'output_nodata': config['nodata'], 'bytes': destination.stat().st_size})
            count += 1
    print(f'Recovered {count} converted tiles. Original run files retained.')


if __name__ == '__main__':
    bootstrap(__file__, 'config.germany.bw.json')
    import argparse
    from dtm.coordinator import load_config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('source_tiles', type=Path)
    args = parser.parse_args()
    recover(load_config(args.config), args.source_tiles)
