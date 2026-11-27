"""Launch either entry point in the existing QGIS Python environment on Windows."""
import json
import os
from pathlib import Path
import subprocess
import sys


def bootstrap(entry_point, default_config='config.json'):
    # Project-local pure-Python dependencies also work with user site disabled.
    packages = Path(__file__).resolve().parents[1] / '.python-packages'
    if packages.is_dir():
        sys.path.insert(0, str(packages))
    config = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else Path(default_config)
    cfg = json.loads(config.read_text(encoding='utf-8-sig')) if config.exists() else {}
    root = cfg.get('qgis_root') or os.environ.get('OSGEO4W_ROOT')
    if not root and os.name == 'nt':
        candidates = sorted(Path('C:/Program Files').glob('QGIS *'), reverse=True)
        root = str(candidates[0]) if candidates else None
    if root and os.name == 'nt':
        root = Path(root)
        if not (root / 'bin/gdalwarp.exe').exists():
            raise RuntimeError(f'Invalid qgis_root: {root}')
        os.environ['PATH'] = str(root / 'bin') + os.pathsep + os.environ['PATH']
        os.environ['GDAL_DATA'] = str(root / 'apps/gdal/share/gdal')
        os.environ['PROJ_DATA'] = str(root / 'share/proj')
        os.environ['GDAL_DRIVER_PATH'] = str(root / 'apps/gdal/lib/gdalplugins')
        if not os.environ.get('DTM_QGIS_BOOTSTRAPPED'):
            homes = sorted((root / 'apps').glob('Python3*'))
            if not homes:
                raise RuntimeError(f'No bundled Python found in {root}')
            env = os.environ.copy()
            env.update(PYTHONHOME=str(homes[-1]), PYTHONPATH='', PYTHONUTF8='1', DTM_QGIS_BOOTSTRAPPED='1')
            result = subprocess.run([str(root / 'bin/python.exe'), str(Path(entry_point).resolve()), *sys.argv[1:]], env=env)
            raise SystemExit(result.returncode)
