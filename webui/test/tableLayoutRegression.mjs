import {createTableLayout} from '../tableLayout.mjs';
const table = document.getElementById('sample');
const layout = createTableLayout(table);
layout.apply([{key:'name', label:'名称', width:130}, {key:'hp', label:'血量', width:185}, {key:'next_action', label:'下一动作预测', width:260}]);
const result = document.getElementById('result');
const widths = () => [...table.tHead.rows[0].cells].map(cell => cell.getBoundingClientRect().width);
function render(long) {
  const row = table.tBodies[0].insertRow();
  for (const text of long ? ['很长的敌人名称'.repeat(8), '123456789.123456/999999999.999999', '等待目标与技能触发条件'.repeat(15)] : ['敌人', '1/1', '移动']) {
    const cell = row.insertCell(); cell.textContent = text; cell.title = text;
  }
}
document.getElementById('run').onclick = async () => {
  const before = widths(); let maxDelta = 0;
  for (let index = 0; index < 30; index++) {
    table.tBodies[0].replaceChildren();
    if (index % 3 !== 2) render(index % 3 === 1);
    await new Promise(requestAnimationFrame);
    maxDelta = Math.max(maxDelta, ...widths().map((width, column) => Math.abs(width - before[column])));
  }
  render(true);
  result.textContent = JSON.stringify({passed: maxDelta < 0.1, cycles: 30, before, after: widths(), maxDelta}, null, 2);
};
document.getElementById('fit').onclick = () => { layout.fit(); result.textContent = JSON.stringify({fitted:widths(), max:480}, null, 2); };
// Regression: explicitly fitting one column must not resize its neighbors or
// re-enable automatic sizing on subsequent samples. Use real browser layout.
document.getElementById('fit-one').onclick = async () => {
  table.tBodies[0].replaceChildren(); render(true);
  const before = widths();
  const handle = table.tHead.rows[0].cells[0].querySelector('.column-fit-handle');
  if (!handle) { result.textContent = JSON.stringify({passed:false, reason:'missing column boundary handle'}); return; }
  handle.dispatchEvent(new MouseEvent('dblclick', {bubbles:true}));
  const after = widths();
  table.tBodies[0].replaceChildren(); render(false);
  await new Promise(requestAnimationFrame);
  const stable = widths();
  result.textContent = JSON.stringify({
    passed: after[0] > before[0] && after.slice(1).every((width, index) => Math.abs(width - before[index + 1]) < 0.1)
      && stable.every((width, index) => Math.abs(width - after[index]) < 0.1),
    before, after, stable,
  }, null, 2);
};
