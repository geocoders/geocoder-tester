import json
import re

import requests
from geopy import Point
from geopy.distance import distance
from unidecode import unidecode
from collections import defaultdict


POTSDAM = [52.3879, 13.0582]
BERLIN = [52.519854, 13.438596]
MUNICH = [43.731245, 7.419744]
AUCKLAND = [-36.853467, 174.765551]
CONFIG = {
    'API_URL': "http://localhost:5001/api/",
    'LOOSE_COMPARE': False,
    'MAX_RUN': 0,  # means no limit
    'GEOJSON': False,
    'FAILED': [],
    'CHECK_DUPLICATES': None,
}

http = requests.Session()


def get_properties(f):
    if 'geocoding' in f['properties']:
        return f['properties']['geocoding']
    else:
        return f['properties']


def get_duplicates_key(feature):
    """
    returns a key used to check if a feature has a duplicate.
    This is a bit tuned on how the results are displayed to the end user.

    For the majority of objects we use the label (or name if there is no label) + the type of the object
    The type is used because for example there can be a POI with the same name as a Stop

    For the POI it's a bit trickier, we also use the address of the POI
    because there can be for example 2 bars with the same name in the same city
    """
    obj = get_properties(feature)
    label = obj.get('label') or feature['name']
    if obj.get('type') == 'poi':
        addr = obj.get('address', {}).get('label', '')
        return (label, obj['type'], addr)
    return (label, obj.get('type'))


class HttpSearchException(Exception):

    def __init__(self, **kwargs):
        super().__init__()
        self.error = kwargs.get("error", {})

    def __str__(self):
        return self.error


class DuplicatesException(Exception):
    """ custom exception for duplicates reporting. """

    def __init__(self, duplicates, params):
        super().__init__()
        self.duplicates = duplicates
        self.query = params.get('q')

    def __str__(self):
        lines = [
            '',
            'Duplicates found in the response',
            "# Search was: {}".format(self.query),
        ]
        for key, features in self.duplicates.items():
            lines.append('## Entry {} has been found for:'.format(key))
            keys = [
                'label', 'id', 'type', 'osm_id', 'housenumber', 'street',
                'postcode', 'city', 'country', 'lat', 'lon', 'addr', 'poi_types'
            ]
            def flatten_res(f):
                r = get_properties(f)
                coords = f.get('geometry', {}).get('coordinates', [None, None])
                r['lat'] = coords[1]
                r['lon'] = coords[0]
                r['addr'] = r.get('address', {}).get('label')
                r['poi_types'] = "-".join(t['name'] for t in r.get('poi_types', []))
                return r
            results = [flatten_res(f) for f in features]
            lines.extend(dicts_to_table(results, keys=keys))
            lines.append('')

        return "\n".join(lines)


class SearchException(Exception):
    """ custom exception for error reporting. """

    def __init__(self, params, expected, results, message=None):
        super().__init__()
        self.results = results
        self.query = params.pop('q')
        self.params = params
        self.expected = expected
        self.message = message

    def __str__(self):
        lines = [
            '',
            'Search failed',
            "# Search was: {}".format(self.query),
        ]
        params = '# Params was: '
        params += " - ".join("{}: {}".format(k, v)
                             for k, v in self.params.items())
        lines.append(params)
        expected = '# Expected was: '
        expected += " | ".join("{}: {}".format(k, v)
                               for k, v in self.expected.items())
        lines.append(expected)
        if self.message:
            lines.append('# Message: {}'.format(self.message))
        lines.append('# Results were:')
        keys = [
            'name', 'osm_key', 'osm_value', 'osm_id', 'housenumber', 'street',
            'postcode', 'city', 'country', 'lat', 'lon', 'distance'
        ]
        results = [self.flat_result(f) for f in self.results]
        lines.extend(dicts_to_table(results, keys=keys))
        lines.append('')
        if CONFIG['GEOJSON']:
            coordinates = None
            if 'coordinate' in self.expected:
                coordinates = self.expected['coordinate'].split(',')[:2]
                coordinates.reverse()
                properties = self.expected.copy()
                properties.update({'expected': True})
            elif 'lat' in self.params and 'lon' in self.params:
                coordinates = [self.params['lon'], self.params['lat']]
                properties = {'center': True}
            if coordinates:
                coordinates = list(map(float, coordinates))
                geojson = self.to_geojson(coordinates, **properties)
                lines.append('# Geojson:')
                lines.append(geojson)
                lines.append('')
        return "\n".join(lines)

    def to_geojson(self, coordinates, **properties):
        self.results.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coordinates},
            "properties": properties,
        })
        return json.dumps({'features': self.results})

    def flat_result(self, result):
        out = get_properties(result)
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
    r = http.get(CONFIG['API_URL'], params=params)
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


def assert_search(query, expected, limit=1,
                  comment=None, lang=None, center=None,
                  max_matches=None):
    query_limit = max(CONFIG['CHECK_DUPLICATES'] or 0, int(limit))
    params = {"q": query, "limit": query_limit}
    if lang:
        params['lang'] = lang
    if center:
        params['lat'] = center[0]
        params['lon'] = center[1]
    raw_results = search(**params)
    results = raw_results['features'][:int(limit)]

    def assert_expected(expected):
        nb_found = 0
        for r in results:
            found = True
            properties = get_properties(r)
            failed = properties['failed'] = []
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
                        failed.append('distance')
                    found = False
                    failed.append(key)
            if found:
                nb_found += 1
                if max_matches is None:
                    break

        if nb_found == 0:

            raise SearchException(
                params=params,
                expected=expected,
                results=results
            )
        elif max_matches is not None and nb_found > max_matches:
            message = 'Got {} matching results. Expected at most {}.'.format(
                nb_found, max_matches
            )
            raise SearchException(
                params=params,
                expected=expected,
                results=results,
                message=message
            )

    if not isinstance(expected, list):
        expected = [expected]
    for s in expected:
        assert_expected(s)

    if CONFIG['CHECK_DUPLICATES']:
        check_duplicates(raw_results['features'][:CONFIG['CHECK_DUPLICATES']], params)


def check_duplicates(features, params):
    results = defaultdict(list)
    for f in features:
        key = get_duplicates_key(f)
        results[key].append(f)

    duplicates = {k: dup for k, dup in results.items() if len(dup) != 1}
    if duplicates:
        raise DuplicatesException(duplicates, params)


def dicts_to_table(dicts, keys):
    if not dicts:
        return []
    # Compute max length for each column.
    lengths = {}
    for key in keys:
        lengths[key] = len(key) + 2  # Surrounding spaces.
    for d in dicts:
        for key in keys:
            i = len(str(d.get(key, '')))
            if i > lengths[key]:
                lengths[key] = i + 2  # Surrounding spaces.
    out = []
    cell = '{{{key}:^{length}}}'
    tpl = '|'.join(cell.format(key=key, length=lengths[key]) for key in keys)
    # Headers.
    out.append(tpl.format(**dict(zip(keys, keys))))
    # Separators line.
    out.append(tpl.format(**dict(zip(keys, ['—'*lengths[k] for k in keys]))))
    for d in dicts:
        row = {}
        l = lengths.copy()
        for key in keys:
            value = d.get(key) or '_'
            if key in d.get('failed', {}):
                l[key] += 10  # Add ANSI chars so python len will turn out.
                value = "\033[1;4m{}\033[0m".format(value)
            row[key] = value
        # Recompute tpl with lengths adapted to failed rows (and thus ansi
        # extra chars).
        tpl = '|'.join(cell.format(key=key, length=l[key]) for key in keys)
        out.append(tpl.format(**row))
    return out
