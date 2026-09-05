"""Protected observable acceptance for the local-catalog release.

Real data and real astronomical calculations; network is forbidden in service tests.
SkyChart comparisons are stored observations from the first alpha, not live mocks.
"""
import importlib
import socket

import pytest


REQUEST = dict(object='M13', latitude=43.9729, longitude=7.9944,
               start='2026-09-05T23:00', timezone='Europe/Rome',
               duration_minutes=30, min_alt=0, max_alt=90, az_start=0, az_end=360)


def catalog_module():
    try:
        return importlib.import_module('astrochecker.catalog')
    except ModuleNotFoundError:
        pytest.fail('Local catalog feature is missing')


def forbid_network(*args, **kwargs):
    raise AssertionError('Local planning must not open a network connection')


@pytest.fixture
def local_service(monkeypatch):
    monkeypatch.setattr(socket, 'create_connection', forbid_network)
    monkeypatch.setattr(socket.socket, 'connect', forbid_network)
    from astrochecker.service import AstroCheckerService
    return AstroCheckerService()


def test_catalog_resolves_same_object_across_catalog_aliases():
    catalog = catalog_module().Catalog()
    messier = catalog.resolve('m 13')
    ngc = catalog.resolve('NGC6205')
    assert messier['name'] == ngc['name']
    assert messier['ra_deg'] == pytest.approx(250.42, abs=0.02)
    assert messier['dec_deg'] == pytest.approx(36.46, abs=0.02)


@pytest.mark.parametrize('identifier', ['IC 1396', 'sh 2-155', 'vdB 152', 'LDN 1251'])
def test_requested_catalogs_have_real_resolvable_targets(identifier):
    target = catalog_module().Catalog().resolve(identifier)
    assert 0 <= target['ra_deg'] < 360
    assert -90 <= target['dec_deg'] <= 90
    assert target['frame'] == 'icrs'
    assert target['source']


def test_missing_catalog_is_not_created_as_empty_success(tmp_path):
    path = tmp_path / 'missing.sqlite3'
    status = catalog_module().Catalog(path).status()
    assert status['ready'] is False
    assert not path.exists()


def test_runtime_is_ready_without_skychart_or_network(local_service):
    assert local_service.status().get('ready') is True


def test_real_m13_full_window_offline_matches_first_alpha(local_service):
    result = local_service.check(REQUEST)
    assert result['status'] == 'full'
    assert result['requested_visible_seconds'] == 1800
    assert result['first_window'] == {'start': 0, 'end': 1800}
    # First-alpha real SkyChart run: altitude at this instant ~46.46 deg,
    # and the initial continuous dark window lasted 18,683 seconds.
    assert result['intervals'][0]['end'] == pytest.approx(18683, abs=120)
    assert result['timezone'] == 'Europe/Rome'
    observed = {sample['offset']: sample for sample in result['samples']}
    # Four independent stored SkyChart observations, geometric altitudes.
    for offset, alt, az, sun in [(0, 46.4644, 280.4928, -29.6274),
            (21600, -4.3933, 334.3431, -20.3952),
            (43200, 5.9452, 43.2107, 40.6302),
            (64800, 64.6323, 96.2847, 30.1497)]:
        assert observed[offset]['alt'] == pytest.approx(alt, abs=0.05)
        assert observed[offset]['az'] == pytest.approx(az, abs=0.05)
        assert observed[offset]['sun_alt'] == pytest.approx(sun, abs=0.05)


def test_real_m13_partial_window_offline_matches_first_alpha(local_service):
    result = local_service.check(REQUEST | dict(start='2026-09-05T22:00', duration_minutes=240, min_alt=30))
    assert result['status'] == 'partial'
    assert result['requested_visible_seconds'] == pytest.approx(9335, abs=120)
    assert result['first_window'] is None


def test_unknown_target_is_an_error_not_astronomical_no(local_service):
    from astrochecker.server import ApiError
    with pytest.raises(ApiError) as error:
        local_service.check(REQUEST | {'object': 'NOT_A_REAL_TARGET_987654'})
    assert error.value.code == 'object'


def test_requested_timezone_controls_physical_instant():
    from astrochecker.server import validate_check_request
    parsed = validate_check_request(REQUEST | {'timezone': 'America/New_York', 'start': '2026-09-05T17:00'})
    assert parsed['start'].isoformat() == '2026-09-05T17:00:00-04:00'


def test_invalid_timezone_is_not_silently_replaced_by_rome():
    from astrochecker.server import validate_check_request
    with pytest.raises(ValueError):
        validate_check_request(REQUEST | {'timezone': 'Planet/Tatooine'})


def test_darkness_events_are_independent_of_balcony(local_service):
    result = local_service.check(REQUEST | {'max_alt': 1})
    assert result['status'] == 'none'
    darkness = result['darkness']
    assert darkness['at_start'] is True
    assert darkness['intervals'][0]['start'] == 0
    assert darkness['intervals'][0]['end'] > 18000
    assert any(e['kind'] == 'night_end' for e in darkness['events'])
    assert any(e['kind'] == 'night_start' for e in darkness['events'])


def test_polar_summer_has_no_invented_astronomical_twilight(local_service):
    result = local_service.check(REQUEST | dict(latitude=89, longitude=0,
                    timezone='UTC', start='2026-06-21T12:00'))
    assert result['status'] == 'none'
    assert result['darkness']['intervals'] == []
    assert result['darkness']['events'] == []
    assert result['darkness']['at_start'] is False
