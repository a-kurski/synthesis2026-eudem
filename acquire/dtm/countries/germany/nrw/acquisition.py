"""NRW WCS acquisition with validated current and version 1 cache reuse."""


import requests

from ....acquire import download_tile, metadata
from ....downloads import download_tiles
from ....geo import rectangle
from ....paths import raw_directory as regional_raw_directory


def raw_directory(config, log_dir=None):
    return regional_raw_directory(config)


def cache_directories(config):
    return [regional_raw_directory(config)]


def download(config, source_plan, log_dir):
    directory = raw_directory(config, log_dir)
    directory.mkdir(parents=True, exist_ok=True)

    candidates = (
        cache_directories(config)
        if config.get('reuse_cache', True)
        else []
    )

    with requests.Session() as session:
        session.headers['User-Agent'] = 'repeatable-dtm-comparison/1.0'
        metadata(session, config['source'], log_dir, 'nrw', config)
    return download_tiles(config, source_plan['tiles'], directory, candidates,
                          'NRW acquisition', download_tile)


def probe(config, source_plan, log_dir):
    directory = raw_directory(config)
    directory.mkdir(parents=True, exist_ok=True)

    # Clip the planned area to the service envelope before selecting the probe.
    # This avoids probing a Dutch-only centre of a cross-border AOI.
    import xml.etree.ElementTree as ET

    with requests.Session() as session:
        metadata(
            session,
            config['source'],
            log_dir,
            'nrw',
            config,
        )

        root = ET.parse(
            log_dir / 'nrw_DescribeCoverage.xml'
        ).getroot()

        ns = {
            'gml': 'http://www.opengis.net/gml/3.2'
        }

        envelope = root.find(
            './/gml:boundedBy/gml:Envelope',
            ns,
        )

        if (
            envelope is None
            or '25832' not in envelope.get('srsName', '')
        ):
            raise ValueError(
                'NRW metadata lacks an EPSG:25832 coverage envelope.'
            )

        lower = list(
            map(
                float,
                envelope.find(
                    'gml:lowerCorner',
                    ns,
                ).text.split(),
            )
        )

        upper = list(
            map(
                float,
                envelope.find(
                    'gml:upperCorner',
                    ns,
                ).text.split(),
            )
        )

        area = rectangle(
            source_plan['aoi_extent']
        ).Intersection(
            rectangle([
                *lower,
                *upper,
            ])
        )

        if area.IsEmpty() or area.GetArea() <= 0:
            raise ValueError(
                'AOI does not intersect the NRW coverage envelope.'
            )

        point = area.PointOnSurface()
        x = int(point.GetX())
        y = int(point.GetY())

        # A 20 m square also supports a tiny end-to-end 5 m aggregation check.
        tile = {
            'id': 'nrw_probe',
            'bounds': [
                x,
                y,
                x + 20,
                y + 20,
            ],
        }

        return download_tile(
            session,
            config['source'],
            tile,
            directory,
            config,
        )
