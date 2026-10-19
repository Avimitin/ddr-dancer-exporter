'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const library = window.DDR_PREVIEW;
  const videos = [$('stock'), $('converted')];
  const controls = ['play', 'restart', 'previous', 'next', 'seek'];
  let active, clip, duration = 0, ready = false, wantedPlay = false, generation = 0;
  const status = text => { $('status').textContent = text; };
  function pause() { wantedPlay = false; videos.forEach(v => v.pause()); $('play').textContent = 'Play both'; }
  function time(t) { t = Math.max(0, t || 0); return `${String(Math.floor(t/60)).padStart(2,'0')}:${(t%60).toFixed(2).padStart(5,'0')}`; }
  function seek(t) { const safe = Math.max(0, Math.min(duration - 0.001, t)); videos.forEach(v => { v.currentTime = safe; }); update(); }
  function update() {
    $('time').textContent = `${time(videos[0].currentTime)} / ${time(duration)}`;
    if (document.activeElement !== $('seek')) $('seek').value = duration ? Math.round(videos[0].currentTime / duration * 1000) : 0;
  }
  async function play() {
    if (!ready) return;
    if (videos[0].currentTime >= duration - .04) seek(0);
    videos[1].currentTime = videos[0].currentTime;
    wantedPlay = true; const token = generation;
    try {
      await Promise.all(videos.map(v => v.play()));
      if (token !== generation || !wantedPlay) return;
      $('play').textContent = 'Pause both'; status('Playing in sync');
    } catch (error) {
      if (token !== generation || error.name === 'AbortError') return;
      pause(); status(`Playback unavailable: ${error.message}`);
    }
  }
  const toggle = () => wantedPlay ? (pause(), status('Paused')) : play();
  function loadVideo(v, src, poster) {
    return new Promise((resolve, reject) => {
      v.onloadeddata = () => { v.onloadeddata = null; resolve(); };
      v.onerror = () => reject(new Error('An MP4 could not be loaded. Keep preview/ and dancers/ in the same project folder.'));
      v.poster = poster; v.src = src; v.playbackRate = Number($('speed').value); v.load();
    });
  }
  async function selectAnimation() {
    const token = ++generation; pause(); ready = false; controls.forEach(id => $(id).disabled = true); status('Loading both dancers…');
    clip = active.animations.find(x => x.id === $('animation').value); duration = clip.duration;
    $('clipInfo').textContent = `${clip.fps} fps · ${clip.duration.toFixed(2)} seconds · ${clip.frames} frames`;
    try {
      await Promise.all([loadVideo(videos[0], clip.stock, clip.stockPoster), loadVideo(videos[1], clip.converted, clip.convertedPoster)]);
      if (token !== generation) return;
      duration = Math.min(...videos.map(v => v.duration)); ready = true; seek(0);
      controls.forEach(id => $(id).disabled = false); status('Ready · synchronized MP4');
    } catch (error) { if (token === generation) status(error.message); }
  }
  function step(direction) { if (!ready) return; pause(); seek(videos[0].currentTime + direction/clip.fps); status('Paused · frame step'); }
  $('play').addEventListener('click', toggle);
  $('restart').addEventListener('click', () => { pause(); seek(0); status('Ready'); });
  $('previous').addEventListener('click', () => step(-1)); $('next').addEventListener('click', () => step(1));
  $('seek').addEventListener('input', () => { pause(); seek(Number($('seek').value)/1000*duration); status('Paused · seeking'); });
  $('speed').addEventListener('change', () => videos.forEach(v => { v.playbackRate = Number($('speed').value); }));
  $('animation').addEventListener('change', selectAnimation);
  videos[0].addEventListener('ended', () => { if ($('loop').checked && wantedPlay) { seek(0); play(); } else { pause(); status('Finished'); } });
  document.addEventListener('keydown', event => {
    if (['INPUT','SELECT','BUTTON','TEXTAREA'].includes(document.activeElement.tagName)) return;
    if (event.code === 'Space') { event.preventDefault(); toggle(); }
    if (event.code === 'ArrowRight') { event.preventDefault(); step(1); }
    if (event.code === 'ArrowLeft') { event.preventDefault(); step(-1); }
  });
  function sync() {
    if (ready) {
      if (wantedPlay && !videos[0].paused && !videos[1].seeking && Math.abs(videos[1].currentTime-videos[0].currentTime) > .045) videos[1].currentTime = videos[0].currentTime;
      update();
    }
    requestAnimationFrame(sync);
  }
  const models = library?.models || (library?.animations ? [library] : []);
  if (!models.length) { status('No previews found. Run scripts/build_previews.py.'); return; }
  function selectDancer() {
    const previous = $('animation').value;
    active = models.find(m => m.converted.id === $('dancer').value);
    if (!active.converted.credit?.trim()) { pause(); ready = false; status('Mandatory credits missing'); return; }
    $('stockName').textContent = active.stock.name;
    $('stockCredit').textContent = active.stock.credit;
    $('convertedName').textContent = active.converted.name;
    $('comparisonRole').textContent = active.converted.kind === 'Original DDR custom mod' ? 'CUSTOM MOD REFERENCE' : 'CONVERTED';
    $('convertedCredit').textContent = active.converted.credit;
    $('convertedKind').textContent = active.converted.kind;
    $('notes').textContent = active.notes;
    $('animation').replaceChildren();
    for (const animation of active.animations) {
      const option = new Option(animation.label, animation.id); $('animation').append(option);
    }
    if (active.animations.some(a => a.id === previous)) $('animation').value = previous;
    $('animation').disabled = false; selectAnimation();
  }
  for (const model of models) {
    if (!model.converted.credit?.trim() || !model.animations.length) continue;
    const option = new Option(model.converted.name, model.converted.id);
    option.title = model.converted.credit; $('dancer').append(option);
  }
  if (!$('dancer').options.length) { status('Cannot preview: mandatory credits missing.'); return; }
  $('dancer').disabled = false;
  $('dancer').addEventListener('change', selectDancer);
  selectDancer(); sync();
})();
