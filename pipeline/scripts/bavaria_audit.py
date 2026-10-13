"""Audit all locally cached Bavaria ZIPs without downloading or modifying terrain.

Usage: python scripts/bavaria_audit.py config.germany.bavaria.json
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dtm.runtime import bootstrap


def main():
    from collections import Counter
    import zipfile
    import numpy as np
    from dtm.acquire import write_json
    from dtm.coordinator import load_config
    from dtm.countries.germany.bavaria.acquisition import parse_catalogue, validate_zip
    from dtm.countries.germany.bavaria.processing import read_xyz
    from dtm.paths import scoped_root

    config = load_config(sys.argv[1])
    if config['country'] != 'germany' or config['region'] != 'bavaria':
        raise ValueError('This audit requires the Bavaria config.')
    logs = scoped_root(config, 'logs_dir')
    index = parse_catalogue(logs / '09.meta4')['tiles']
    shapes, lattices = Counter(), Counter()
    report = {'checked': 0, 'nonstandard_tiles': [], 'errors': []}
    for archive in sorted((scoped_root(config, 'cache_root') / 'source_archive').glob('*.zip')):
        try:
            tile = index[archive.name]
            member = validate_zip(archive, tile)['member']
            with zipfile.ZipFile(archive) as package, package.open(member) as stream:
                values, transform = read_xyz(stream, tile['bounds'])
            missing = values == config['source'].get('nodata')
            if np.any(~missing & (~np.isfinite(values) | (np.abs(values) >= 1e20))):
                raise ValueError('Undeclared nonfinite/extreme heights.')
            shape = f'{values.shape[1]}x{values.shape[0]}'
            lattice = f'{transform[0] % 5:g},{transform[3] % 5:g}'
            shapes[shape] += 1
            lattices[lattice] += 1
            if shape != '200x200' or lattice != '0,0':
                report['nonstandard_tiles'].append({'archive': archive.name, 'sha256': tile['sha256'],
                    'shape': shape, 'transform': transform, 'nodata_cells': int(missing.sum()),
                    'valid_cells': int((~missing).sum())})
        except Exception as exc:
            report['errors'].append({'archive': archive.name, 'error': str(exc)})
        report['checked'] += 1
    report.update(shapes=dict(shapes), lattices=dict(lattices))
    destination = logs / 'cache_audit.json'
    write_json(destination, report)
    print(f'Checked {report["checked"]} ZIPs; shapes={dict(shapes)}; lattices={dict(lattices)}; '
          f'errors={len(report["errors"])}. Report: {destination}')
    if report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    bootstrap(__file__, 'config.germany.bavaria.json')
    main()
