"""Run the Rhine-basin DTM pipeline: python main.py [pipeline.json] [--stages ...]"""
import sys

from dtm.runtime import bootstrap


if __name__ == '__main__':
    try:
        bootstrap(__file__, 'pipeline.json')
        from dtm.pipeline import main
        main()
    except KeyboardInterrupt:
        print('Interrupted. Finished outputs are recorded in the JSON; rerun to resume.', file=sys.stderr)
        sys.exit(130)
