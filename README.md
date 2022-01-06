# Geocoder tester

Run search queries against a geocoder that supports [geocodejson spec](https://github.com/geocoders/geocodejson-spec).

## Intalling

- create a python >= 3.4 [virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/) environment
- `git clone https://github.com/geocoders/geocoder-tester && cd geocoder-tester`
- `pip install -r requirements.txt`

## Running

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

Can I change the api URL I'm testing against?

    py.test --api-url http://photon.komoot.de/api/

If you want to test not only against another photon instance, but against a nominatim or pelias service, supply the optional --api-type parameter and specify either `photon`, `nominatim` or `pelias`. 

    py.test --api-url https://nominatim.openstreetmap.org/ --api-type nominatim


Note that support for pelias is still rudimentary.
   
Can I limit the number of tests to be run (even if my filter select thousands
of tests) ?

    py.test --max-run 100

You can compare two runs (for example to compare two branches). First, save the
report from the first run:

    py.test --save-report path/to/report.log

Then compare when running a new version

    py.test --compare-report path/to/report.log

Note: in compare mode, only new failures will appear as "FAILED" and their
traceback will be rendered; already known failures will appear as "xfail" and
in yellow instead of red. If you want those known to fail tests not to be run at
all (thus you'll don't know how many of them now pass), you can use the `--skip-xfail`
command line argument.


## Adding search cases

We support python, CSV and YAML format.

Before creating a new file, check that there isn't a one that can host the test
you want to add.

*How do I name my file?* Just make it start with `test_`, and chose the right
extension according to the format you want to use: `.py`, `.csv` or `.yml`.

*Where do I save my file?* Chose the right geographical area, and if you create
a new area remember to create all levels, like `france/iledefrance/paris`.

Remember to check the tests already done to get inspiration.

You generally want to use YAML format if you are managing tests by hand in your
text editor, CSV if you are generating test cases from a script, and python test
cases if you need more control.

### Python

They are normal python tests. Just note that you have two utils in `base.py`:
`search` and `assert_search` that can do a lot for you.

### CSV

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

## License

Geocoder-tester is available under a MIT license. See LICENSE.txt for more
information.

As a special exception, the test cases under `geocoder_tester/world/` are
considered to be in the public domain. You may use them without any
restrictions.
