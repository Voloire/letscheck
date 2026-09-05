"""Run explicitly against the local alpha and real SkyChart; no test doubles."""
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from astrochecker.skychart import SkyChartClient

BASE = sys.argv[1]
ARTIFACTS = ROOT / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)


def state():
    with SkyChartClient() as client:
        return {'chart': client.initial_chart, **{command: client.command(command)
                for command in ('LISTCHART', 'GETDATE', 'GETOBS', 'GETTZ')}}


def check(payload):
    request = Request(BASE + '/api/check', data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'}, method='POST')
    start = time.monotonic()
    try:
        with urlopen(request, timeout=180) as response:
            status, result = response.status, json.load(response)
    except HTTPError as error:
        status, result = error.code, json.load(error)
    print(json.dumps({'seconds': round(time.monotonic()-start, 2), 'http': status,
                      'status': result.get('status'), 'error': result.get('error')}, ensure_ascii=False), flush=True)
    return status, result


before = state()
payload = dict(object='M13', latitude=43.9729, longitude=7.9944,
    start='2026-09-05T22:00', duration_minutes=240,
    min_alt=30, max_alt=90, az_start=0, az_end=360)
status, partial = check(payload)
assert status == 200 and partial['status'] == 'partial', partial
assert 0 < partial['requested_visible_seconds'] < 14400, partial
assert partial['first_window'] is None or partial['first_window']['end'] - partial['first_window']['start'] == 14400
(ARTIFACTS / 'live-partial.json').write_text(json.dumps(partial, indent=2, ensure_ascii=False), encoding='utf-8')

status, alternative = check(payload | dict(start='2026-09-05T15:00', duration_minutes=30, min_alt=0))
assert status == 200 and alternative['status'] == 'none', alternative
assert alternative['first_window'] and alternative['first_window']['start'] > 0, alternative
assert alternative['first_window']['end'] - alternative['first_window']['start'] == 1800
(ARTIFACTS / 'live-alternative.json').write_text(json.dumps(alternative, indent=2, ensure_ascii=False), encoding='utf-8')
status, invalid = check(payload | dict(latitude=91))
assert status == 400 and invalid['code'] == 'validation', invalid
after = state()
assert before == after, {'before': before, 'after': after}
(ARTIFACTS / 'live-state-preserved.json').write_text(json.dumps({'before': before, 'after': after}, indent=2), encoding='utf-8')
print('PASS: real partial visibility, first later complete window, invalid input, original SkyChart state preserved')
