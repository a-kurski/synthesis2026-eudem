"""Small terminal progress helpers; redirected output has no animated bars."""
from contextlib import contextmanager
import math

from tqdm import tqdm

from .geo import windows


class Progress(tqdm):
    @property
    def format_dict(self):
        values = super().format_dict
        values['left'] = max(0, (self.total or 0) - self.n)
        return values


@contextmanager
def bar(description, total, unit='tiles'):
    with Progress(total=total, desc=description, unit=unit, disable=None,
                  dynamic_ncols=True, mininterval=0.25,
                  bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} {unit}, '
                             '{left:.0f} left [{elapsed}<{remaining}]{postfix}') as progress:
        yield progress


def track(items, description, total=None, unit='tiles'):
    with bar(description, len(items) if total is None else total, unit) as progress:
        for item in items:
            yield item
            progress.update(1)


def blocks(dataset, size, description):
    total = math.ceil(dataset.RasterXSize / size) * math.ceil(dataset.RasterYSize / size)
    return track(windows(dataset, size), description, total, 'blocks')


@contextmanager
def gdal_progress(description):
    with bar(description, 100, '%') as progress:
        def callback(fraction, message, data):
            progress.update(max(0, min(100, int(fraction * 100)) - progress.n))
            return 1
        yield callback
