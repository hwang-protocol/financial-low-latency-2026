import copy
import json
import os
from pathlib import Path
import sys
from urllib.request import urlopen

sys.path.insert(0, '/tmp/flle-playwright')
from playwright.sync_api import sync_playwright

root = Path('/financial-low-latency')
out = root / 'Documents/reports/course-runs/20260910T080208Z-02-fanout-fix/raw/browser'
out.mkdir(parents=True, exist_ok=True)
with urlopen('http://10.1.1.101:8088/api/state', timeout=10) as reply:
    live = json.load(reply)
(out / 'live-state.json').write_text(json.dumps(live, indent=2))
env = dict(os.environ, LD_LIBRARY_PATH='/tmp/flle-review-browser/libs/usr/lib/x86_64-linux-gnu',
           FONTCONFIG_FILE='/tmp/flle-review-browser/fonts.conf')
results = []
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(
        executable_path='/root/.cache/puppeteer/chrome/linux-131.0.6778.204/chrome-linux64/chrome',
        headless=True, env=env, args=['--no-sandbox', '--disable-dev-shm-usage', '--no-proxy-server'])
    try:
        for width, height in [(1440, 1000), (390, 844)]:
            context = browser.new_context(viewport=dict(width=width, height=height), device_scale_factor=1)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('**/api/stream*', lambda route: route.abort())
            for mode in ['healthy', 'resync']:
                state = copy.deepcopy(live)
                if mode == 'resync':
                    state['feed'].update(integrity='GAP', trading_gate='INHIBITED_FEED_GAP',
                        resync_required=True, resync_reason='GAP_LIMIT', pending=32768,
                        next_expected=7641279, gap_size=1, gap_age_ms=4288910)
                page.route('**/api/state', lambda route, request, value=state: route.fulfill(json=value))
                page.goto('http://10.1.1.101:8088/', wait_until='domcontentloaded')
                page.wait_for_function('app.state !== null')
                page.wait_for_timeout(500)
                visible = page.locator('#feed-gap-banner').is_visible()
                assert visible == (mode == 'resync')
                data = page.evaluate('''() => {
                    const banner=document.getElementById('feed-gap-banner');
                    const detail=document.getElementById('feed-gap-detail');
                    const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom}};
                    return {viewport:innerWidth,body:document.body.scrollWidth,banner:rect(banner),
                      detail:rect(detail),detailText:detail.textContent,
                      submitDisabled:document.getElementById('submit-order').disabled,
                      firstCard:rect(document.querySelector('main section'))};
                }''')
                if mode == 'resync':
                    assert data['submitDisabled'], data
                    assert '需要重新同步' in data['detailText'] or '需重新同步' in data['detailText']
                    assert data['detail']['right'] <= width + 1, data
                    assert data['detail']['bottom'] <= data['banner']['bottom'], data
                    assert data['firstCard']['y'] >= data['banner']['bottom'], data
                assert not errors, errors
                page.screenshot(path=str(out / f'{mode}-{width}.png'), full_page=False)
                results.append(dict(mode=mode, width=width, errors=list(errors), **data))
                page.unroute('**/api/state')
            context.close()
        for width, height in [(1440, 1000), (390, 844)]:
            context = browser.new_context(viewport=dict(width=width, height=height))
            page = context.new_page()
            page.goto('http://10.1.1.101:8088/', wait_until='domcontentloaded')
            page.wait_for_function('app.state !== null && app.state.feed.integrity === "HEALTHY"')
            first = page.locator('#wall-clock').inner_text()
            page.wait_for_timeout(1800)
            last = page.locator('#wall-clock').inner_text()
            assert first != last, (first, last)
            assert page.locator('#stream-label').inner_text() == '实时连接'
            assert not page.locator('#feed-gap-banner').is_visible()
            page.screenshot(path=str(out / f'live-{width}.png'), full_page=False)
            results.append(dict(mode='live', width=width, first_clock=first, last_clock=last,
                                stream='实时连接', integrity='HEALTHY'))
            context.close()
    finally:
        browser.close()
(out / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(results, ensure_ascii=False, indent=2))
