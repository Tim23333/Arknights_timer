import {createSourceMeta} from '../sourceMeta.mjs';
import {metaLabel} from '../model.mjs';
const element = document.getElementById('metadata');
const display = createSourceMeta(element);
document.getElementById('run').onclick = async () => {
  const meta = value => ({collectionState:'current', sourceFrame:value, latestKnownFrame:value});
  display.update(meta(2415));
  const boxes = [...element.querySelectorAll('.meta-frame')];
  const textNodes = boxes.map(box => box.firstChild);
  const geometry = () => [element, ...element.children, ...boxes].map(node => {
    const rect = node.getBoundingClientRect();
    return [rect.left, rect.top, rect.width, rect.height];
  });
  const before = geometry();
  // ROOT CAUSE: the old plain metadata string has variable width and is
  // right-aligned in the table title, shifting labels on null/numeric changes.
  const legacy = document.createElement('span');
  element.before(legacy); legacy.textContent = metaLabel(meta(2415));
  const numericWidth = legacy.getBoundingClientRect().width;
  legacy.textContent = metaLabel(meta(null));
  const legacyDelta = Math.abs(numericWidth - legacy.getBoundingClientRect().width);
  legacy.remove();
  let maxDelta = 0;
  for (let index=0; index<30; index++) {
    display.update(meta([null, 0, 2415, 2147483647][index % 4]));
    await new Promise(requestAnimationFrame);
    const current = geometry();
    maxDelta = Math.max(maxDelta, ...current.flatMap((rect, row) => rect.map((value, column) => Math.abs(value - before[row][column]))));
  }
  const retained = boxes.every((box, index) => box.firstChild === textNodes[index]);
  display.update(meta(null));
  const unknown = boxes.every(box => box.textContent === '—');
  display.update(meta(0));
  const zero = boxes.every(box => box.textContent === '0');
  display.update(meta(2415));
  document.getElementById('result').textContent = JSON.stringify({passed:legacyDelta>0 && maxDelta<0.1 && retained && unknown && zero,
    cycles:30, legacyDelta, maxDelta, retained, unknown, zero}, null, 2);
};
