"""Small live RGE ALTI pilot in Belfort, using the shared department 90 cache."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def main():
    import argparse
    import logging
    from osgeo import gdal
    from osgeo_utils.samples.validate_cloud_optimized_geotiff import validate
    from dtm.acquire import write_json
    from dtm.coordinator import create_log_directory, load_config
    from dtm.countries import france
    from dtm.geo import rectangle, srs
    from dtm.paths import region_lock, scoped_root
    from dtm.target_grid import plan_grid, write_reference

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', nargs='?', default='config.france.json')
    parser.add_argument('--plan', action='store_true', help='Offline pilot plan only.')
    args = parser.parse_args()
    config = load_config(args.config)
    if config['country'] != 'france':
        raise ValueError('Use a France configuration.')
    config['source']['departments'] = ['90']
    root = scoped_root(config, 'logs_dir') / 'pilots'
    directory = create_log_directory({**config, 'country': '', 'logs_dir': str(root)})
    logging.basicConfig(filename=directory / 'processing.log', encoding='utf-8', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    geometry = rectangle([6.86, 47.637, 6.864, 47.640])
    geometry.AssignSpatialReference(srs(4326))
    config['target'] = {'epsg': 25832, 'resolution': 5}
    source = france.plan(geometry, config)
    target = plan_grid(geometry, config['target'])
    write_json(directory / 'plan.json', {'source': source, 'target_grid': target})
    print(f'Pilot plan: {directory / "plan.json"}')
    if args.plan:
        return
    with region_lock(config):
        tiles = france.download(config, source, directory)
        reference = write_reference(target, directory / 'target_grid.vrt')
        result = france.prepare(tiles, geometry, reference, directory / 'prepared', config)
        # A second acquisition must find the same tiles in the local cache.
        repeated = france.download(config, source, directory)
        if repeated != tiles:
            raise RuntimeError('Repeated acquisition changed the selected tiles.')
    with gdal.Open(result['prepared_raster']) as ds:
        warnings, errors, _ = validate(ds, full_check=True)
        if errors:
            raise RuntimeError(f'COG validation failed: {errors}')
    write_json(directory / 'pilot_report.json', {'status': 'passed', 'cog_errors': errors,
               'cog_warnings': warnings, 'repeat_acquisition_same_tiles': True, 'result': result})
    print(f'Pilot report: {directory / "pilot_report.json"}')


if __name__ == '__main__':
    bootstrap(__file__, 'config.france.json')
    main()
