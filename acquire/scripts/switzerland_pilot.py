"""Small live swissALTI3D pilot near Vaduz; never uses the production AOI."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def main():
    import argparse
    import json
    import logging
    from osgeo import gdal, ogr
    from osgeo_utils.samples.validate_cloud_optimized_geotiff import validate
    from dtm.acquire import write_json
    from dtm.coordinator import create_log_directory, load_config
    from dtm.countries import switzerland
    from dtm.geo import rectangle, srs
    from dtm.paths import receipt_path, region_lock, scoped_root
    from dtm.target_grid import plan_grid, write_reference

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', nargs='?', default='config.switzerland.json')
    parser.add_argument('--plan', action='store_true', help='Offline pilot plan only.')
    parser.add_argument('--source-manifest', type=Path, help='Resume this pilot with frozen editions.')
    args = parser.parse_args()
    config = load_config(args.config)
    if config['country'] not in ('switzerland', 'liechtenstein'):
        raise ValueError('Use a Switzerland or Liechtenstein configuration.')
    root = scoped_root(config, 'logs_dir') / 'pilots'
    directory = create_log_directory({**config, 'country': '', 'region': None, 'logs_dir': str(root)})
    logging.basicConfig(filename=directory / 'processing.log', encoding='utf-8', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    aoi = directory / 'vaduz.gpkg'
    geometry = rectangle([9.510, 47.140, 9.512, 47.142])
    geometry.AssignSpatialReference(srs(4326))
    with ogr.GetDriverByName('GPKG').CreateDataSource(str(aoi)) as ds:
        layer = ds.CreateLayer('vaduz', srs(4326), ogr.wkbPolygon)
        feature = ogr.Feature(layer.GetLayerDefn())
        feature.SetGeometry(geometry)
        layer.CreateFeature(feature)
    config.update(aoi=str(aoi), layer=None, target={'epsg': 25832, 'resolution': 5},
                  source_manifest=str(args.source_manifest.resolve()) if args.source_manifest else None)
    source_plan = switzerland.plan(geometry, config)
    target = plan_grid(geometry, config['target'])
    write_json(directory / 'config.json', config)
    write_json(directory / 'plan.json', {'source': source_plan, 'target_grid': target})
    print(f'Pilot plan: {directory / "plan.json"}')
    if args.plan:
        return
    # Use the production cache/receipts/lock, but keep all pilot products here.
    # Pilot runs do not update production latest_run.json or latest_plan.json.
    with region_lock(config):
        tiles = switzerland.download(config, source_plan, directory)
        write_json(directory / 'source_manifest.json', {'query': source_plan, 'tiles': [
            {'path': str(path), 'receipt': json.loads(receipt_path(path, config).read_text(encoding='utf-8'))}
            for path in tiles]})
        reference = write_reference(target, directory / 'target_grid.vrt')
        result = switzerland.prepare(tiles, geometry, reference, directory / 'prepared', config)
    with gdal.Open(result['prepared_raster']) as ds:
        warnings, errors, details = validate(ds, full_check=True)
        if errors:
            raise RuntimeError(f'COG validation failed: {errors}')
    write_json(directory / 'pilot_report.json', {'status': 'passed', 'cog_errors': errors,
               'cog_warnings': warnings, 'result': result})
    print(f'Pilot report: {directory / "pilot_report.json"}')


if __name__ == '__main__':
    bootstrap(__file__, 'config.switzerland.json')
    main()
