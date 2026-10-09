'use strict';
// Inspect safe srcdoc as data. Imported JavaScript is never evaluated.
const report = {total: 0, ready: 0, failures: [], sourceDOMMismatches: [], stylesheets: [], diagnostics: {}, complete: false};
for (const item of cssRecords) {
  const preview = MotionPreview.create(item, {compact: true, paused: true, lang: 'en'});
  report.total++;
  const srcdoc = preview.querySelector('iframe')?.srcdoc;
  if (preview.dataset.state === 'ready' && srcdoc) {
    report.ready++;
    const parsed = new DOMParser().parseFromString(srcdoc, 'text/html');
    const root = parsed.body.firstElementChild;
    if (parsed.body.children.length !== 1 || root?.localName !== item.preview.dom.tag || root?.className !== item.preview.dom.className || root?.children.length !== 0 || root?.textContent !== (item.preview.dom.text || '')) report.sourceDOMMismatches.push(item.id);
    report.stylesheets.push({id: item.id, css: parsed.querySelector('style').textContent});
  } else report.failures.push({id: item.id, state: preview.dataset.state, reason: preview.dataset.reason});
  preview.destroy();
}
report.diagnostics = MotionPreview.diagnostics();
report.complete = true;
document.getElementById('result').textContent = JSON.stringify(report);
document.getElementById('result').dataset.complete = 'true';
