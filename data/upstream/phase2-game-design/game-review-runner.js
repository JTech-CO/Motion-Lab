'use strict';
const report = {total: 0, ready: 0, originalNodes: 0, preservedNodes: 0, comparedAttributes: 0, lostAttributes: [], changedAttributes: [], failures: [], diagnostics: {}, sourceJavaScriptExecuted: false, complete: false};
const query = new URLSearchParams(location.search);
const offset = Math.max(0, Math.min(199, Number(query.get('offset') || '0')));
const count = Math.max(1, Math.min(199, Number(query.get('count') || '199')));
for (const item of candidates.slice(offset, offset + count)) {
  const original = new DOMParser().parseFromString(item.code, 'image/svg+xml').documentElement;
  const before = [original, ...original.querySelectorAll('*')];
  const copy = MotionPreview.sanitizeSvg(item.code);
  const after = copy ? [copy, ...copy.querySelectorAll('*')] : [];
  report.total++;
  report.originalNodes += before.length; report.preservedNodes += after.length;
  if (!copy || before.length !== after.length) report.failures.push({id: item.id, reason: 'SVG tree mismatch'});
  else {
    report.ready++;
    for (let i = 0; i < before.length; i++) {
      if (before[i].localName !== after[i].localName) report.failures.push({id: item.id, reason: 'SVG element order or type changed', node: i});
      for (const attr of before[i].attributes) {
        if (attr.name.startsWith('xmlns')) continue;
        report.comparedAttributes++;
        if (!after[i].hasAttribute(attr.name)) report.lostAttributes.push({id: item.id, attribute: attr.name});
        else if (after[i].getAttribute(attr.name) !== attr.value) report.changedAttributes.push({id: item.id, attribute: attr.name});
      }
    }
    const card = document.createElement('article'), label = document.createElement('label');
    label.textContent = item.title + ' / ' + item.sourceAuthor;
    card.append(label, copy); document.getElementById('samples').append(card);
  }
  // These originals contain no animation nodes; skip detached SMIL clock calls.
  const playback = MotionPreview.create(item, {compact: true, paused: false, lang: 'en'});
  if (playback.dataset.state !== 'ready') report.failures.push({id: item.id, reason: playback.dataset.reason});
  playback.destroy();
}
report.diagnostics = MotionPreview.diagnostics(); report.complete = true;
document.getElementById('result').textContent = JSON.stringify(report);
document.getElementById('result').dataset.complete = 'true';
