'use strict';
const report = {total: 0, originalNodes: 0, preservedNodes: 0, originalAttributes: 0, comparedAttributes: 0, animationNodes: 0, animatedAttributeCounts: {}, intentionalRewriteCounts: {safeLocalIdPrefix: 0, beginListWhitespace: 0}, semanticNormalizations: ['Renderer-owned local ID prefixes', 'Whitespace separating semicolon-delimited SMIL begin expressions'], lostNodes: [], lostAttributes: [], changedAttributes: [], attributesNotCompared: ['xmlns', 'xmlns:xlink'], complete: false};
const animatedTags = new Set(['animate', 'animateTransform', 'set']);
function normalized(value, name) {
  const unprefixed = value.replace(/ml-svg-\d+-/g, '');
  return name === 'begin' ? unprefixed.replace(/\s+/g, '') : unprefixed;
}
for (const item of svgRecords) {
  const original = new DOMParser().parseFromString(item.code, 'image/svg+xml').documentElement;
  const preserved = MotionPreview.sanitizeSvg(item.code);
  const originals = [original, ...original.querySelectorAll('*')];
  const copies = preserved ? [preserved, ...preserved.querySelectorAll('*')] : [];
  report.total++; report.originalNodes += originals.length; report.preservedNodes += copies.length;
  if (originals.length !== copies.length) report.lostNodes.push({id: item.id, original: originals.length, preserved: copies.length});
  for (let index = 0; index < originals.length; index++) {
    const before = originals[index], after = copies[index];
    if (!after || before.localName !== after.localName) {
      report.lostNodes.push({id: item.id, index, originalTag: before.localName, preservedTag: after?.localName || null}); continue;
    }
    if (animatedTags.has(before.localName)) report.animationNodes++;
    for (const attr of before.attributes) {
      report.originalAttributes++;
      if (report.attributesNotCompared.includes(attr.name)) continue;
      const name = attr.name === 'xlink:href' ? 'href' : attr.name;
      report.comparedAttributes++;
      if (animatedTags.has(before.localName)) report.animatedAttributeCounts[name] = (report.animatedAttributeCounts[name] || 0) + 1;
      if (!after.hasAttribute(name)) report.lostAttributes.push({id: item.id, index, tag: before.localName, name, source: attr.value});
      else {
        const value = after.getAttribute(name);
        if (/ml-svg-\d+-/.test(value)) report.intentionalRewriteCounts.safeLocalIdPrefix++;
        if (name === 'begin' && value.replace(/ml-svg-\d+-/g, '') !== attr.value && normalized(value, name) === normalized(attr.value, name)) report.intentionalRewriteCounts.beginListWhitespace++;
        if (normalized(value, name) !== normalized(attr.value, name)) report.changedAttributes.push({id: item.id, index, tag: before.localName, name, source: attr.value, preserved: value});
      }
    }
  }
}
report.complete = true;
document.getElementById('result').textContent = JSON.stringify(report, null, 2);
document.getElementById('result').dataset.complete = 'true';
