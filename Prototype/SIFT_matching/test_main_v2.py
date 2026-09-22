from pathlib import Path

import pytest

from main_v2 import reuse_existing_output


def test_reuse_existing_output(tmp_path):
    source = tmp_path / 'input.tif'
    source.write_bytes(b'not-a-real-raster')

    existing = tmp_path / 'input_reprojected.tif'
    existing.write_bytes(b'already-processed')

    result = reuse_existing_output(source, '_reprojected', '.tif')

    assert result == existing
    assert existing.read_bytes() == b'already-processed'
