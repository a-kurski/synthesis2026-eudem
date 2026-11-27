"""Germany adapter: each federal state owns its source and processing rules."""
from . import bavaria, bw, hessen, nrw, rlp, saarland

REGIONS = {'nrw': nrw, 'rlp': rlp, 'saarland': saarland, 'hessen': hessen, 'bw': bw, 'bavaria': bavaria}
VERTICAL_NOTE = 'German regional products retain their source vertical datum.'


def adapter(config):
    region = config.get('region')
    if region not in REGIONS:
        raise ValueError(f'Unsupported Germany region: {region!r}. Available: {", ".join(REGIONS)}')
    return REGIONS[region]


def validate_config(config):
    adapter(config).validate_config(config)


def plan(geometry, config):
    return adapter(config).plan(geometry, config)


def download(config, source_plan, log_dir):
    return adapter(config).download(config, source_plan, log_dir)


def probe(config, source_plan, log_dir):
    return adapter(config).probe(config, source_plan, log_dir)


def prefetch(config, log_dir):
    region = adapter(config)
    if not hasattr(region, 'prefetch'):
        raise ValueError('Explicit statewide prefetch is currently supported only for Baden-Württemberg.')
    return region.prefetch(config, log_dir)


def prepare(tiles, geometry, reference, run_dir, config):
    return adapter(config).prepare(tiles, geometry, reference, run_dir, config)
