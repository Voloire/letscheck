"""Live browser acceptance: real HTTP backend and real SkyChart.

The one intercepted status response explicitly tests a connection failure UI.
All subsequent connection and astronomy requests are real.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


base = sys.argv[1]
artifacts = Path(__file__).resolve().parents[1] / 'artifacts'
artifacts.mkdir(exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(base)
    expect(page.get_by_label('Sky object', exact=True)).to_be_disabled()
    page.route('**/api/status', lambda route: route.fulfill(
        status=200, content_type='application/json',
        body=json.dumps({'connected': False, 'message': 'SkyChart non raggiungibile', 'port': 3292})))
    page.get_by_role('button', name='Verifica connessione', exact=True).click()
    expect(page.get_by_label('Sky object', exact=True)).to_be_disabled()
    page.unroute('**/api/status')
    page.get_by_role('button', name='Verifica connessione', exact=True).click()
    expect(page.get_by_label('Sky object', exact=True)).to_be_enabled(timeout=15000)

    for label, value in [('Sky object', 'M13'), ('Latitude', '43.9729'),
                         ('Longitude', '7.9944'), ('Site date and time', '2026-09-05T23:00'),
                         ('Durata continua', '30'), ('Altezza minima', '0'),
                         ('Maximum altitude', '90'), ('Azimut iniziale', '0'), ('Azimut finale', '360')]:
        page.get_by_label(label, exact=True).fill(value)
    with page.expect_response('**/api/check', timeout=180000) as response:
        page.get_by_role('button', name='Check visibility', exact=True).click()
    result = response.value.json()
    assert result.get('status') == 'full', result
    expect(page.get_by_text('Visible for the full duration', exact=True)).to_be_visible(timeout=10000)
    expect(page.get_by_text('First complete window', exact=True)).to_be_visible()
    page.screenshot(path=str(artifacts / 'astrochecker-desktop.png'), full_page=True)
    (artifacts / 'live-full.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')

    page.get_by_label('Maximum altitude', exact=True).fill('1')
    with page.expect_response('**/api/check', timeout=180000) as response:
        page.get_by_role('button', name='Check visibility', exact=True).click()
    unavailable = response.value.json()
    assert unavailable.get('status') == 'none', unavailable
    assert unavailable.get('first_window') is None, unavailable
    expect(page.get_by_text('No solution in the analyzed 24 hours', exact=True)).to_be_visible()

    page.get_by_label('Sky object', exact=True).fill('ASTROCHECKER_UNKNOWN_987654321')
    with page.expect_response('**/api/check', timeout=180000) as response:
        page.get_by_role('button', name='Check visibility', exact=True).click()
    unknown = response.value.json()
    assert unknown.get('code') == 'object', unknown
    assert unknown.get('error'), unknown

    page.set_viewport_size({'width': 390, 'height': 844})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Horizontal overflow'
    page.screenshot(path=str(artifacts / 'astrochecker-mobile.png'), full_page=True)
    assert not errors, errors
    browser.close()
    print('PASS: prerequisite failure/retry, real connection, full result, no solution, unknown target, mobile overflow, JS errors')
