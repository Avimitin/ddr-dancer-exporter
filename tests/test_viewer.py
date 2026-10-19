"""Exercise the offline HTML viewer with real MP4 decoding in isolated Chromium."""
import _bootstrap  # Local src/ discovery for direct invocation.
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def main():
    manifest=json.loads((ROOT/'preview/manifest.json').read_text(encoding='utf-8'))
    report={'animations':[],'checks':[]};errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1120})
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((ROOT/'preview/index.html').as_uri())
        page.wait_for_function("!document.getElementById('play').disabled")
        assert page.locator('#dancer option').count()==len(manifest['models'])
        for model in manifest['models']:
            previous=page.locator('#animation').input_value()
            page.select_option('#dancer',model['converted']['id'])
            page.wait_for_function("!document.getElementById('play').disabled")
            if previous in [a['id'] for a in model['animations']]:assert page.locator('#animation').input_value()==previous
            assert page.locator('#convertedCredit').inner_text()==model['converted']['credit']
            for clip in model['animations']:
                page.select_option('#animation',clip['id'])
                page.wait_for_function("!document.getElementById('play').disabled && document.getElementById('stock').readyState>=2 && document.getElementById('converted').readyState>=2")
                metadata=page.locator('video').evaluate_all('(vs)=>vs.map(v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,error:v.error?.message}))')
                assert all(m['width']==640 and m['height']==640 and not m['error'] for m in metadata)
                assert abs(metadata[0]['duration']-metadata[1]['duration'])<.04
                assert abs(metadata[0]['duration']-clip['duration'])<.04
                report['animations'].append({'dancer':model['converted']['id'],'id':clip['id'],'duration':metadata[0]['duration'],'resolution':'640x640','both_decoded':True})
            page.click('#play')
        page.select_option('#animation','mc_female_sf02_exec')
        page.wait_for_function("!document.getElementById('play').disabled")
        page.click('#play');page.wait_for_function("document.getElementById('stock').currentTime>1")
        drift=page.locator('video').evaluate_all('(vs)=>Math.abs(vs[0].currentTime-vs[1].currentTime)')
        assert drift<.08,drift
        page.click('#play');page.wait_for_function("Array.from(document.querySelectorAll('video')).every(v=>v.paused)")
        page.select_option('#speed','0.5')
        assert page.locator('video').evaluate_all('(vs)=>vs.every(v=>v.playbackRate===0.5)')
        page.click('#restart');page.wait_for_function("Array.from(document.querySelectorAll('video')).every(v=>!v.seeking && v.currentTime<0.01)")
        page.click('#next');page.wait_for_function("Array.from(document.querySelectorAll('video')).every(v=>!v.seeking)")
        t=page.locator('#stock').evaluate('(v)=>v.currentTime');assert abs(t-1/30)<.002,t
        page.click('#previous');page.wait_for_function("Array.from(document.querySelectorAll('video')).every(v=>!v.seeking && v.currentTime<0.01)")
        page.locator('#seek').evaluate("e=>{e.value=500;e.dispatchEvent(new Event('input',{bubbles:true}));}")
        page.wait_for_function("Array.from(document.querySelectorAll('video')).every(v=>!v.seeking)")
        times=page.locator('video').evaluate_all('(vs)=>vs.map(v=>v.currentTime)')
        assert abs(times[0]-times[1])<.002 and times[0]>5
        # Changing clips during playback must cancel the old playback cleanly.
        page.click('#play');page.select_option('#animation',manifest['animations'][0]['id'])
        page.wait_for_function("!document.getElementById('play').disabled")
        assert page.locator('video').evaluate_all('(vs)=>vs.every(v=>v.paused && v.currentTime<0.01)')
        page.select_option('#animation','mc_female_sf02_exec');page.wait_for_function("!document.getElementById('play').disabled")
        page.screenshot(path=str(ROOT/'preview/viewer-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        page.screenshot(path=str(ROOT/'preview/viewer-mobile.png'),full_page=True)
        page.evaluate("window.DDR_PREVIEW.models.forEach(m=>m.converted.credit='');document.getElementById('dancer').replaceChildren();")
        page.add_script_tag(path=str(ROOT/'preview/viewer.js'))
        assert 'mandatory credits missing' in page.locator('#status').inner_text()
        assert not errors,errors
        report.update(status='PASS',max_measured_sync_drift=drift,checks=['Every animation loads and decodes both MP4s','Matching resolution and duration','Synchronized play and pause','Shared playback speed','Frame stepping and seek','Clip change during playback','Dancer change during playback retains animation selection','Credits visible and required','Offline file URL works','Mobile layout has no horizontal overflow','No JavaScript runtime errors'])
        browser.close()
    (ROOT/'preview/browser-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
