"""Prepare a country's terrain data for a later Rhine-catchment comparison."""
import sys

from dtm.runtime import bootstrap


if __name__ == '__main__':
    try:
        bootstrap(__file__, 'config.netherlands.json')
        from dtm.coordinator import main
        main()
    except KeyboardInterrupt:
        print('Interrupted. Completed source tiles are preserved; rerun to resume acquisition.', file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
