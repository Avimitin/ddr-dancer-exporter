"""Local integration: static PMX, missing backend, live Blender connection and ZIPs.

Requires the private local regression assets and Playwright; not release dependencies.
"""
from pathlib import Path
import json
import secrets
import subprocess
import time
from urllib.request import Request, urlopen
import zipfile
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'analysis/js-validation'


def source_zip(dancer):
    output = OUT / (dancer + '-source.zip')
    root = ROOT / 'dancers' / dancer
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in (root / 'source').rglob('*'):
            if path.is_file():
                archive.write(path, path.relative_to(root / 'source'))
        if dancer == 'adelie-tomorin':
            archive.write(root / 'bone-map.json', 'bone-map.json')
    return output


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pmx_zip, blend_zip = source_zip('adelie-tomorin'), source_zip('nailong')
    token = secrets.token_hex(32)
    reuse_bridge = False
    existing_token = ROOT / '.bridge-token'
    if existing_token.exists():
        try:
            candidate = existing_token.read_text(encoding='utf8').strip()
            with urlopen(Request('http://127.0.0.1:8765/api/capabilities', headers={'Authorization': 'Bearer ' + candidate}), timeout=1):
                token, reuse_bridge = candidate, True
        except Exception:
            pass
    token_file = OUT / '.test-token'
    token_file.write_text(token, encoding='utf8')
    blender = next((ROOT / 'tools').glob('blender-*/blender.exe'))
    process = None
    errors = []
    report = {}
    with (OUT / 'bridge-test.log').open('wb') as log, sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1100})
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.route('http://127.0.0.1:8765/**', lambda route: route.abort())
            page.goto((ROOT / 'web/index.html').as_uri() + '#session=' + token)
            page.locator('#models').set_input_files(str(blend_zip))
            page.wait_for_function("document.querySelector('#blender-help').hidden === false")
            assert 'install Blender' in page.locator('#blender-help').inner_text()
            assert page.locator('#convert').is_disabled()
            report['missing_blender_guidance'] = True
            reference = list((ROOT / 'dancers/template-miku/model').glob('*'))
            missing_texture = next(x for x in reference if x.suffix == '.dds')
            page.locator('#assets').set_input_files([
                {'name': x.name.replace('pl_miku00', 'pl_reference'), 'mimeType': 'application/octet-stream', 'buffer': x.read_bytes()}
                for x in reference if x.is_file() and x != missing_texture
            ])
            page.wait_for_function("document.querySelector('#reference-checks').textContent.includes('Missing textures:')")
            assert page.locator('#asset-status').get_attribute('data-ready') == 'false'
            page.locator('#assets').set_input_files(str(missing_texture))
            page.wait_for_function("document.querySelector('#asset-status').dataset.ready === 'true'")
            assert page.locator('#template-choice').input_value() == 'pl_reference.model'
            page.locator('#animations-upload').set_input_files(str(ROOT / 'animations/archives/mc_female.arc'))
            page.wait_for_function("document.querySelector('#animation').options.length > 1")
            stock = list((ROOT / 'dancers/stock-emi/model').glob('*')) + list((ROOT / 'dancers/stock-emi/face').glob('*'))
            page.locator('#comparison-upload').set_input_files([
                {'name': x.name.replace('pl_emi00', 'pl_stock_example'), 'mimeType': 'application/octet-stream', 'buffer': x.read_bytes()}
                for x in stock if x.is_file()
            ])
            page.wait_for_function("document.querySelector('#reference').options.length > 1")
            report['generic_references_and_missing_texture_guidance'] = True
            source_box = page.locator('#drop').bounding_box()
            reference_box = page.locator('#asset-drop').bounding_box()
            assert abs(source_box['y'] - reference_box['y']) < 1
            assert abs(source_box['height'] - reference_box['height']) < 1
            assert abs(page.locator('.card.input').bounding_box()['height'] - page.locator('.card.setup').bounding_box()['height']) < 1
            report['upload_panels_aligned'] = True
            page.locator('#models').set_input_files(str(pmx_zip))
            page.wait_for_function("document.querySelector('#model-choice').value.toLowerCase().endsWith('.pmx')")
            page.fill('#label', 'Tomorin JS test')
            page.fill('#credits', 'Bushiroad Games/オキアミ')
            page.click('#convert')
            page.wait_for_function("!document.querySelector('#download').disabled", timeout=120000)
            assert 'Converted and validated' in page.locator('#status').inner_text(), page.locator('#status').inner_text()
            page.select_option('#animation', 'mc_female_ht01_exec.anm')
            page.wait_for_timeout(800)
            page.select_option('#reference', 'pl_stock_example.model')
            assert 'Preview:' not in page.locator('#status').inner_text(), page.locator('#status').inner_text()
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / 'stock-emi.png'), full_page=True)
            page.select_option('#reference', '')
            page.screenshot(path=str(OUT / 'static-pmx.png'), full_page=True)
            with page.expect_download() as download:
                page.click('#download')
            download.value.save_as(str(OUT / 'tomorin-browser.zip'))
            with zipfile.ZipFile(OUT / 'tomorin-browser.zip') as archive:
                credit = next(n for n in archive.namelist() if n.endswith('/借物表.txt'))
                assert archive.read(credit).decode('utf8').strip() == 'Bushiroad Games/オキアミ'
                assert any(n.endswith('.model') for n in archive.namelist())
            report['static_pmx_export_and_ht01_preview'] = True
            page.unroute('http://127.0.0.1:8765/**')
            if not reuse_bridge:
                process = subprocess.Popen([str(blender), '--background', '--disable-autoexec', '--factory-startup',
                                            '--python-exit-code', '1', '--python', str(ROOT / 'service/blender_bridge.py'),
                                            '--', '--token-file', str(token_file)], stdout=log, stderr=subprocess.STDOUT,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
            page.wait_for_function("document.querySelector('#connection').textContent.includes('Blender · connected')", timeout=60000)
            assert page.url.startswith('file:///'), 'Frontend must remain static while backend connects'
            page.locator('#models').set_input_files(str(blend_zip))
            page.wait_for_function("document.querySelector('#model-choice').value.endsWith('.blend')")
            assert page.locator('#convert').is_enabled()
            page.fill('#label', 'Nailong JS test')
            page.fill('#credits', 'bingloe（AIGC / AI-generated）')
            page.click('#convert')
            page.wait_for_function("!document.querySelector('#convert').disabled", timeout=180000)
            assert page.locator('#dancer option').count() == 2, page.locator('#status').inner_text() + '\n' + page.locator('#log').inner_text()
            page.select_option('#animation', 'mc_female_ht01_exec.anm')
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUT / 'blender-connected.png'), full_page=True)
            with page.expect_download() as download:
                page.click('#download')
            download.value.save_as(str(OUT / 'nailong-browser.zip'))
            report['live_blender_connection_and_conversion'] = True
            page.select_option('#dancer', '0')
            assert 'Bushiroad' in page.locator('#preview-credit').inner_text()
            report['dancer_switching_and_credits'] = True
            assert not errors, errors
            if process:
                page.click('#stop')
                process.wait(timeout=15)
            report['page_errors'] = errors
            (OUT / 'frontend-test.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            print(json.dumps(report, indent=2))
        finally:
            browser.close()
            if process and process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)


if __name__ == '__main__':
    main()
