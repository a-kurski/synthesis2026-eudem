"""Prepare a tiny AOI inside the configured Bavaria mask, then prove offline reuse.

Usage: python scripts/bavaria_pilot.py config.germany.bavaria.json
Downloads the catalogue and at most four 1 km ZIPs; uses the standard cache.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def main():
    from unittest.mock import patch
    from osgeo import ogr

    from dtm.acquire import sha256, write_json
    from dtm.coordinator import create_log_directory, execute, load_config
    from dtm.countries.germany import bavaria
    from dtm.geo import read_aoi, srs, verify_alignment
    from dtm.paths import scoped_root

    config = load_config(sys.argv[1])
    if config['country'] != 'germany' or config['region'] != 'bavaria':
        raise ValueError('This pilot requires the Bavaria config.')
    geometry, _, _ = read_aoi(config['aoi'], config['layer'])
    native = bavaria.region_aoi(geometry, config)
    # The 40 m diameter is much smaller than a source tile, even at a tile corner.
    small = native.PointOnSurface().Buffer(20).Intersection(native)
    directory = create_log_directory({**config, 'logs_dir': str(scoped_root(config, 'logs_dir') / 'pilots'),
                                      'country': '', 'region': None})
    aoi = directory / 'pilot_aoi.gpkg'
    with ogr.GetDriverByName('GPKG').CreateDataSource(str(aoi)) as ds:
        layer = ds.CreateLayer('aoi', srs(25832), ogr.wkbUnknown)
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(small)
        layer.CreateFeature(feature)
    config.update(aoi=str(aoi), layer='aoi', reuse_cache=True, catalogue_refresh=False,
                  catalogue_max_age_days=None, timeout_seconds=60, download_attempts=2)
    first = execute(config, 'yes')
    with patch('requests.Session.get', side_effect=AssertionError('Unexpected network request on repeat')):
        second = execute(config, 'yes')
    verify_alignment(first['prepared_raster'], second['prepared_raster'])
    if sha256(Path(first['prepared_raster'])) != sha256(Path(second['prepared_raster'])):
        raise RuntimeError('Repeated pilot COG differs from the original.')
    write_json(directory / 'verification.json', {'first': first, 'offline_repeat': second,
                                                'identical_cogs': True, 'offline_cache_reuse': True})
    print(f'Pilot verification: {directory / "verification.json"}')


if __name__ == '__main__':
    bootstrap(__file__, 'config.germany.bavaria.json')
    main()
