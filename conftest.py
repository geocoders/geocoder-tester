import csv
import yaml

import pytest

from osm_geocoding_tester.base import assert_search, CONFIG


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
    dirs = item.session.fspath.bestrelpath(item.fspath.dirpath()).split('/')
    for d in dirs:
        if d != ".":
            item.add_marker(d)


def pytest_addoption(parser):
    parser.addoption(
        '--api-url',
        dest="api_url",
        default=CONFIG['API_URL'],
        help="The URL to use for running tests against."
    )


def pytest_configure(config):
    CONFIG['API_URL'] = config.getoption('--api-url')


class CSVFile(pytest.File):

    def collect(self):
        with self.fspath.open() as f:
            dialect = csv.Sniffer().sniff(f.read(1024))
            f.seek(0)
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                yield CSVItem(row, self)


class YamlFile(pytest.File):

    def collect(self):
        raw = yaml.safe_load(self.fspath.open())
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
