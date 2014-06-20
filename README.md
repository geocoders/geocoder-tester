# OpenStreetMap Geocoding tester

Run search queries against an OSM based geocoder.

Supported adapters for now: Photon.

## Intalling

You should have created a python 3.4 virtualenv environment, then:

    pip install -r requirements.txt

## Running

Simply:

    py.test

For a global help, type:

    py.test -h

Tests are split by geographical area, so you can run only a subset of all the tests,
for example because your local database only contains a small area, or because you want
to focus on some data.

Available subsets: `germany`, `france`, `iledefrance`, `italy`.

If you want to run only a subset of the tests, run for example

    py.test -m iledefrance

What if I want to have details about the failures?

    py.test --tb short

How can I stop at first failing test?

    py.test -x

Can I change the photon URL I'm testing against?

    py.test --photon-url http://photon.komoot.de/api/

## Adding search cases

We support python, CSV and YAML format.

Before creating a new file, check that there isn't a one that can host the test
you want to add.

*How do I name my file?* Just make it start with `test_`, and chose the right
extension according to the format you want to use: `.py`, `.csv` or `.yml`.

*Where do I save my file?* Chose the right geographical area, and if you create
a new area remember to create all levels, like `france/iledefrance/paris`.

Remember to check the tests already done to get inspiration.

You generally want to use YAML format if you are managing tests by hand, CSV if
you are generating test cases from a script, and python test cases if you need
more control.

### Python

They are normal python tests. Just note that you have two utils in `base.py`:
`search` and `assert_search` that can do a lot for you.

### CSV

One column is mandatory: `query`, where you store the query you make.
Then you can add as many `expected_xxx` columns you want, according to what
you want to test. For example, to test the name in the result, you will store
the expected value in the column `expected_name`; for an `osm_id` it will be
`expected_osm_id`, and so on. Note on `expected_coordinate` format: it should be
of the form `lat,lon,tolerated deviation in meters`, e.g. `51.0,10.3,700`.

Optional columns:
* `limit`: decide how many results you want to look at for finding your result
(defaul: 1)
* `lat`, `lon`: if you want to add a center for the search
* `comment`: if you want to take control of the ouput of the test in the
command line
* `lang`: language
* `skip`: add a `skip` message if you want a test to be always skipped (feature
not supported yet for example)

### YAML

The spec name is the query, then one key is mandatory: `expected`, which then
has the subkeys you want to test against (`name`, `housenumber`…).
Optional keys: `limit`, `lang`, `lat` and `lon`, `skip`.
You can add categories to your test by using the key `mark` (which expects a
list), that you can then run with `-m yourmarker`.
