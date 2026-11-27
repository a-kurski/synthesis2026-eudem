"""Region outlines from OpenStreetMap (via osmnx / Nominatim), saved under the country_masks file names.

Run from pipeline-merge:  python get_osm_masks.py [out_dir]     (default: osm_masks)
Then point the regions' "vector" in the JSON at out_dir, or copy the files over country_masks.
Needs osmnx:  micromamba install -c conda-forge osmnx
"""
import sys
from pathlib import Path

import osmnx as ox

RELATIONS = {  # file name -> OSM boundary relation id (check on openstreetmap.org/relation/<id>)
    'Netherlands': 47796,               # European Netherlands
    'Germany_NRW': 62761,
    'Germany_RheinlandPfalz': 62341,
    'Germany_Saarland': 62372,
    'Germany_Hessen': 62650,
    'Germany_BadenWurttemberg': 62611,
    'Germany_Bayern': 2145268,
    'Germany_Thuringen': 62366,
    'France': 1403916,                  # metropolitan France
    'Luxembourg': 2171347,
    'Swiss': 51701,
    'Liechtenstein': 1155955,
    'Austria': 16239,
    'Belgium': 52411,
}

out = Path(sys.argv[1] if len(sys.argv) > 1 else 'osm_masks')
out.mkdir(exist_ok=True)
for name, rid in RELATIONS.items():
    gdf = ox.geocode_to_gdf(f'R{rid}', by_osmid=True)
    gdf[['display_name', 'geometry']].to_file(out / f'{name}.gpkg', layer=name, driver='GPKG')
    x0, y0, x1, y1 = gdf.total_bounds
    print(f'{name}: {gdf.display_name[0]} (lon {x0:.2f}..{x1:.2f}, lat {y0:.2f}..{y1:.2f})', flush=True)
