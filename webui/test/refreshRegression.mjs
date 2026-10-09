import {createPager} from '../pagination.mjs';
import {createTableRenderer} from '../tableRenderer.mjs';
import {createFieldDisplay} from '../fieldDisplay.mjs';
const items = Array.from({length:23}, (_, id) => ({id}));
let changed = 0;
const pager = createPager('历史记录', () => { changed++; pager.slice(items); }, 5);
document.getElementById('pager').append(pager.element);
const table = document.getElementById('enemy-history-test');
const renderer = createTableRenderer(table);
document.getElementById('run').onclick = async () => {
  const size = pager.element.querySelector('select');
  size.value = '5'; size.dispatchEvent(new Event('change')); changed = 0;
  const columns = [{key:'name', label:'名称', width:120}, {key:'hp', label:'最后血量', width:170}, {key:'history', label:'历史快照', width:100}];
  let data = [{id:'a', name:'合成敌人 A', hp:'10/20'}, {id:'b', name:'合成敌人 B', hp:'5/20'}];
  const value = (row, column) => row[column.key];
  renderer.update(columns, data, value);
  const firstRow = table.tBodies[0].rows[0];
  const firstButton = firstRow.querySelector('button');
  const oldWidths = [...table.querySelectorAll('col')].map(col => col.style.width);
  pager.slice(items);
  // ROOT CAUSE: unchanged textContent and disabled assignments still generate
  // DOM mutations on every poll, invalidating the history table's surrounding UI.
  const records = [];
  const observer = new MutationObserver(batch => records.push(...batch));
  observer.observe(pager.element, {subtree:true, childList:true, attributes:true, characterData:true});
  observer.observe(table, {subtree:true, childList:true, attributes:true, characterData:true});
  let noop = true;
  for (let index = 0; index < 30; index++) {
    pager.slice(items);
    // Frame metadata may change without changing historical visible values.
    noop = !renderer.update(columns.map(column => ({...column})), data.map(row => ({...row, latestKnownFrame:index})), value) && noop;
  }
  await Promise.resolve(); observer.disconnect();
  const retained = firstRow === table.tBodies[0].rows[0] && firstButton === firstRow.querySelector('button');
  data = [{...data[0], hp:'9/20'}, data[1]];
  const updated = renderer.update(columns, data, value) && firstRow.cells[1].textContent === '9/20';
  const widthStable = [...table.querySelectorAll('col')].every((col, index) => col.style.width === oldWidths[index]);
  renderer.update(columns, [...data].reverse(), value);
  const reordered = table.tBodies[0].rows[1] === firstRow;
  renderer.update(columns, [], value);
  const empty = table.tBodies[0].querySelector('.empty-row') !== null;
  renderer.update(columns, data, value);
  const restored = table.tBodies[0].rows.length === 2 && !table.tBodies[0].querySelector('.empty-row');
  pager.element.querySelector('button:last-child').click();
  const page = pager.slice(items);
  const actions = pager.element.querySelector('.pagination-actions');
  const adjacent = actions?.children.length === 2 && actions.children[0].textContent === '上一页'
    && actions.children[1].textContent === '下一页';
  // Real DOM regression: alternating validity must not replace the row, cell
  // or value Text node, or alternate its displayed number with unavailable.
  const display = createFieldDisplay();
  const context = {kind:'enemy', precision:2, policy:{generation:0, fields:[]}};
  const payload = (frame, good) => ({meta:{sessionId:'test-only', policyGeneration:0, collectionState:'current', sourceFrame:frame},
    items:[{id:'a', name:'合成敌人 A', hp:good ? '10/20' : '不可用',
      fieldStates:{'enemy.hp':{collectionState:good ? 'current' : 'unavailable', sourceFrame:good ? frame : null}}}]});
  let view = display.project(payload(100, true), context, columns, value, 0);
  renderer.update(columns, view.rows, view.cell);
  const stableRow = table.tBodies[0].rows[0], stableCell = stableRow.cells[1], stableText = stableCell.firstChild;
  const range = document.createRange(); range.selectNodeContents(stableCell);
  const textLeft = range.getBoundingClientRect().left;
  const fieldRecords = [];
  const fieldObserver = new MutationObserver(batch => fieldRecords.push(...batch));
  fieldObserver.observe(table, {subtree:true, childList:true, attributes:true, characterData:true});
  let steadyValue = true, markedOld = false, markerStable = true;
  for (let index=1; index<=30; index++) {
    view = display.project(payload(100+index, index % 2 === 0), context, columns, value, index*20);
    renderer.update(columns, view.rows, view.cell);
    steadyValue = steadyValue && stableCell.textContent === '10/20';
    if (index % 2) markedOld = markedOld || (stableCell.dataset.freshness === 'last_known' && stableCell.title.includes('非当前值'));
    await new Promise(requestAnimationFrame);
    markerStable = markerStable && Math.abs(range.getBoundingClientRect().left - textLeft) < 0.1;
  }
  await Promise.resolve(); fieldObserver.disconnect();
  const textRetained = stableText === stableCell.firstChild && stableRow === table.tBodies[0].rows[0];
  const childListChanges = fieldRecords.filter(record => record.type === 'childList').length;
  view = display.project(payload(131, false), context, columns, value, 1100);
  renderer.update(columns, view.rows, view.cell);
  const expired = stableCell.textContent === '不可用' && stableCell.dataset.freshness === 'unavailable';
  const healthy = payload(132, true); healthy.items[0].hp = '9/20';
  view = display.project(healthy, context, columns, value, 1120);
  renderer.update(columns, view.rows, view.cell);
  const recoveredImmediately = stableCell.textContent === '9/20' && stableCell.dataset.freshness === 'current';
  view = display.project(payload(133, false), context, columns, value, 1140);
  renderer.update(columns, view.rows, view.cell);
  document.getElementById('result').textContent = JSON.stringify({
    passed: records.length === 0 && noop && retained && updated && widthStable && reordered && empty && restored && adjacent && page.page === 2 && changed > 0 && steadyValue && markedOld && markerStable && textRetained && childListChanges === 0 && expired && recoveredImmediately,
    cycles:30, unchangedMutations:records.length, noop, retained, updated, widthStable, reordered, empty, restored, adjacent, nextPage:page.page,
    steadyValue, markedOld, markerStable, textRetained, childListChanges, expired, recoveredImmediately,
  }, null, 2);
};
