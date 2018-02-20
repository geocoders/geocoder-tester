import csv
import os
import sys
import yaml

import pytest

from geocoder_tester.base import assert_search, CONFIG


def pytest_collect_file(parent, path):
    if not path.basename.startswith("test"):
        return None
    f = None
    ext = path.ext
    if ext == ".csv":
        f = CSVFile(path, parent)
    if ext == ".yml":
        f = YamlFile(path, parent)
    return f


def pytest_itemcollected(item):
    dirs = item.session.fspath.bestrelpath(item.fspath.dirpath()).split(os.sep)
    for d in dirs:
        if d != ".":
            item.add_marker(d)
            if item.nodeid in CONFIG.get('COMPARE_WITH', []):
                item.add_marker('xfail')


def pytest_addoption(parser):
    parser.addoption(
        '--api-url',
        dest="api_url",
        default=CONFIG['API_URL'],
        help="The URL to use for running tests against."
    )
    parser.addoption(
        '--max-run',
        dest="max_run",
        type=int,
        default=CONFIG['MAX_RUN'],
        help="Limit the number of tests to be run."
    )
    parser.addoption(
        '--loose-compare',
        dest="loose_compare",
        action="store_true",
        help="Loose compare the results strings."
    )
    parser.addoption(
        '--geojson', action="store_true", dest="geojson",
        help=("Display geojson in traceback of failing tests.")
    )
    parser.addoption(
        '--save-report',
        dest="save_report",
        help="Path where to save the report."
    )
    parser.addoption(
        '--compare-report',
        dest="compare_report",
        help="Path where to load the report to compare with."
    )


def pytest_configure(config):
    CONFIG['API_URL'] = config.getoption('--api-url')
    CONFIG['MAX_RUN'] = config.getoption('--max-run')
    CONFIG['LOOSE_COMPARE'] = config.getoption('--loose-compare')
    CONFIG['GEOJSON'] = config.getoption('--geojson')
    if config.getoption('--compare-report'):
        with open(config.getoption('--compare-report')) as f:
            CONFIG['COMPARE_WITH'] = []
            for line in f:
                CONFIG['COMPARE_WITH'].append(line.strip())


def pytest_unconfigure(config):
    if config.getoption('--save-report'):
        with open(config.getoption('--save-report'), mode='w',
                  encoding='utf-8') as f:
            f.write('\n'.join(CONFIG['FAILED']))
    if config.getoption('--compare-report'):
        import _pytest.config
        writer = _pytest.config.create_terminal_writer(config, sys.stdout)
        total = 0
        writer.sep('!', 'NEW FAILURES', red=True)
        for failed in CONFIG['FAILED']:
            if failed not in CONFIG['COMPARE_WITH']:
                total += 1
                print(failed)
        writer.sep('!', 'TOTAL NEW FAILURES: {}'.format(total), red=True)
        total = 0
        writer.sep('=', 'NEW PASSING', green=True)
        for failed in CONFIG['COMPARE_WITH']:
            if failed not in CONFIG['FAILED']:
                print(failed)
                total += 1
        writer.sep('=', 'TOTAL NEW PASSING: {}'.format(total), green=True)


REPORTS = 0


def pytest_runtest_logreport(report):
    if report.failed or (not report.passed and 'xfail' in report.keywords):
        CONFIG['FAILED'].append(report.nodeid)
    if report.when == 'teardown' and not report.skipped:
        global REPORTS
        REPORTS += 1
        if CONFIG['MAX_RUN'] and REPORTS >= CONFIG['MAX_RUN']:
            raise KeyboardInterrupt(
                'Limit of {} reached'.format(CONFIG['MAX_RUN']))


class CSVFile(pytest.File):

    def collect(self):
        with self.fspath.open(encoding="utf-8") as f:
            dialect = csv.Sniffer().sniff(f.read(1024))
            f.seek(0)
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                yield CSVItem(row, self)


class YamlFile(pytest.File):

    def collect(self):
        raw = yaml.safe_load(self.fspath.open(encoding="utf-8"))
        for name, spec in raw.items():
            yield YamlItem(name, self, spec)


class BaseFlatItem(pytest.Item):

    def __init__(self, name, parent, **kwargs):
        super().__init__(name, parent)
        self.lat = kwargs.get('lat')
        self.lon = kwargs.get('lon')
        self.lang = kwargs.get('lang')
        self.limit = kwargs.get('limit')
        self.comment = kwargs.get('comment')
        self.skip = kwargs.get('skip')
        self.mark = kwargs.get('mark', [])
        for mark in self.mark:
            self.add_marker(mark)

    def runtest(self):
        if self.skip is not None:
            pytest.skip(msg=self.skip)
        kwargs = {
            'query': self.query,
            'expected': self.expected,
            'lang': self.lang,
            'comment': self.comment
        }
        if self.lat and self.lon:
            kwargs['center'] = [self.lat, self.lon]
        if self.limit:
            kwargs['limit'] = self.limit
        assert_search(**kwargs)

    def repr_failure(self, excinfo):
        """ called when self.runtest() raises an exception. """
        return str(excinfo.value)

    def reportstring(self):
        s = "Search: {}".format(self.query)
        if self.comment:
            s = "{} ({})".format(s, self.comment)
        return s

    def reportinfo(self):
        return self.fspath, 0, self.reportstring()


class CSVItem(BaseFlatItem):

    def __init__(self, row, parent):
        if "mark" in row:
            row['mark'] = row['mark'].split(',')
        super().__init__(row.get('query', ''), parent, **row)
        self.query = row.get('query', '')
        self.expected = {}
        for key, value in row.items():
            if key.startswith('expected_') and value:
                self.expected[key[9:]] = value


class YamlItem(BaseFlatItem):
    def __init__(self, name, parent, spec):
        super(YamlItem, self).__init__(name, parent, **spec)
        self.query = spec.pop('query', name)
        self.expected = spec['expected']
