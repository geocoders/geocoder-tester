import json
import re

import requests
from geopy import Point
from geopy.distance import distance
from unidecode import unidecode

POTSDAM = [52.3879, 13.0582]
BERLIN = [52.519854, 13.438596]
MUNICH = [43.731245, 7.419744]
AUCKLAND = [-36.853467, 174.765551]
CONFIG = {
    'API_URL': "http://localhost:5001/api/",
    'LOOSE_COMPARE': False,
    'MAX_RUN': 0,  #0 default# 0 means no limit
    'GEOJSON': False,
    'FAILED': [],
}


class HttpSearchException(Exception):

    def __init__(self, **kwargs):
        super().__init__()
        self.error = kwargs.get("error", {})

    def __str__(self):
        return self.error


class SearchException(Exception):
    """ custom exception for error reporting. """

    def __init__(self, params, expected, results, message=None,comment=None):
        super().__init__()
        self.results = results
        self.query = params.pop('q')
        self.params = params
        self.expected = expected
        self.message = message
        self.comment = comment


    def __str__(self):
        lines = [
            '',
            'Search failed',
            "# Search was: {}".format(self.query),
        ]
        params = '# Params was: '
        params += " - ".join("{}: {}".format(k, v) for k, v in self.params.items())
        lines.append(params)
        expected = '# Expected was: '
        expected += " | ".join("{}: {}".format(k, v) for k, v in self.expected.items())
        lines.append(expected)
        if self.message:
            lines.append('# Message: {}'.format(self.message))
        if self.comment:
            lines.append("# Comment : {}".format(self.comment))
        lines.append('# Results were:')
        keys = [
            'name', 'osm_key', 'osm_value', 'osm_id', 'housenumber', 'street',
            'postcode', 'city', 'country', 'lat', 'lon', 'distance', "type"
        ]
        results = [self.flat_result(f) for f in self.results['features']]
        lines.extend(dicts_to_table(results, keys=keys))
        lines.append('')
        if CONFIG['GEOJSON'] and 'coordinate' in self.expected:
            lines.append('# Geojson:')
            lines.append(self.to_geojson())
            lines.append('')
        return "\n".join(lines)

    def to_geojson(self):
        if not 'coordinate' in self.expected:
            return ''
        coordinates = self.expected['coordinate'].split(',')[:2]
        coordinates.reverse()
        coordinates = list(map(float, coordinates))
        properties = self.expected.copy()
        properties.update({'expected': True})
        self.results['features'].append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coordinates},
            "properties": properties,
        })
        return json.dumps(self.results)

    def flat_result(self, result):
        out = None
        if 'geocoding' in result['properties']:
            out = result['properties']['geocoding']
        else:
            out = result['properties']
        if 'geometry' in result:
            out['lat'] = result['geometry']['coordinates'][1]
            out['lon'] = result['geometry']['coordinates'][0]
        else:
            out['lat'] = None
            out['lon'] = None

        out['distance'] = '—'
        if 'coordinate' in self.expected:
            lat, lon, max_deviation = map(float, self.expected['coordinate'].split(','))
            dist = distance(Point(lat, lon), Point(out['lat'], out['lon']))
            out['distance'] = int(dist.meters)
        return out


def search(**params):
    r = requests.get(CONFIG['API_URL'], params=params)
    if not r.status_code == 200:
        raise HttpSearchException(error="Non 200 response")
    return r.json()


def normalize(s):
    return normalize_pattern.sub(' ', unidecode(s.lower()))
normalize_pattern = re.compile('[^\w]')


def compare_values(get, expected):
    if CONFIG['LOOSE_COMPARE']:
        return normalize(get) == normalize(expected)
    return get == expected


def assert_search(query, expected, limit=1, skip=None,
                  comment=None, lang=None, center=None):
    params = {"q": query, "limit": limit}
    if lang:
        params['lang'] = lang
    if center:
        params['lat'] = center[0]
        params['lon'] = center[1]
    results = search(**params)

    def assert_expected(expected):
        found = False
        for r in results['features']:
            found = True
            properties = None
            if 'geocoding' in r['properties']:
                properties = r['properties']['geocoding']
            else:
                properties = r['properties']
            for key, value in expected.items():
                value = str(value)
                if not compare_values(str(properties.get(key)), value):
                    # Value is not like expected. But in the case of
                    # coordinate we need to handle the tolerance.
                    if key == 'coordinate':
                        coord = r['geometry']['coordinates']
                        lat, lon, max_deviation = map(float, value.split(","))
                        deviation = distance(
                            Point(lat, lon),
                            Point(coord[1], coord[0])
                        )
                        if int(deviation.meters) <= int(max_deviation):
                            continue  # Continue to other properties
                    found = False
            if found:
                break
        if not found:
            raise SearchException(
                params=params,
                expected=expected,
                results=results
            )

    if not isinstance(expected, list):
        expected = [expected]
    for s in expected:
        assert_expected(s)


def dicts_to_table(dicts, keys=None):
    if not dicts:
        return []
    if keys is None:
        keys = dicts[0].keys()
    cols = []
    for i, key in enumerate(keys):
        cols.append(len(key))
    for d in dicts:
        for i, key in enumerate(keys):
            l = len(str(d.get(key, '')))
            if l > cols[i]:
                cols[i] = l
    out = []

    def fill(l, to, char=" "):
        l = str(l)
        return "{}{}".format(
            l,
            char * (to - len(l) if len(l) < to else 0)
        )

    def create_row(values, char=" "):
        row = []
        for i, v in enumerate(values):
            row.append(fill(v, cols[i], char))
        return " | ".join(row)

    out.append(create_row(keys))
    out.append(create_row(['' for k in keys], char="-"))
    for d in dicts:
        out.append(create_row([d.get(k, '—') for k in keys]))
    return out