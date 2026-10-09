import {createTableLayout} from './tableLayout.mjs';

/**
 * Owns keyed rows and stable geometry for a refreshing data table.
 * Use when: rendering live or historical pages without replacing unchanged DOM.
 * Expects: ordered rows with unique IDs and a pure cell-value projection.
 * Returns: update(columns, rows, values, offset), the manual column layout,
 * current column definitions and rowFor(id) for additional row presentation.
 * Only visible values, row order or schema changes cause table DOM updates;
 * sampling metadata outside the displayed cells does not invalidate the table.
 */
export function createTableRenderer(table) {
  const layout = createTableLayout(table);
  const rows = new Map();
  const body = table.tBodies[0];
  const element = (tag, className, text) => {
    const node = table.ownerDocument.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  let schema = null, visible = null, appliedColumns = [];

  function update(columns, items, values, offset = 0) {
    const signature = JSON.stringify(columns.map(column => [column.key, column.label, column.width]));
    const projection = items.map((item, index) => ({
      key: String(item.id ?? item.uniqueId ?? item.seq ?? (index + offset)),
      cells: columns.map(column => {
        if (['history', 'detail'].includes(column.key)) return null;
        const value = values(item, column, index + offset);
        return value && typeof value === 'object' && 'text' in value
          ? {text:String(value.text), title:String(value.title ?? value.text), freshness:value.freshness || ''}
          : {text:String(value), title:String(value), freshness:''};
      }),
    }));
    const nextVisible = JSON.stringify(projection);
    if (signature === schema && nextVisible === visible) return false;
    if (signature !== schema) {
      const head = element('tr');
      for (const column of columns) head.append(element('th', '', column.label));
      table.tHead.replaceChildren(head);
      body.replaceChildren(); rows.clear();
      layout.apply(columns); schema = signature; appliedColumns = columns;
    }
    const wanted = new Set();
    projection.forEach(({key, cells}, index) => {
      wanted.add(key);
      let row = rows.get(key);
      if (!row) { row = element('tr'); columns.forEach(() => row.append(element('td'))); rows.set(key, row); body.append(row); }
      columns.forEach((column, cellIndex) => {
        const cell = row.children[cellIndex];
        if (column.key === 'history' || column.key === 'detail') {
          if (!cell.firstChild) {
            const button = element('button', 'detail-button', column.key === 'history' ? '历史快照' : '详情');
            if (column.key === 'history') button.dataset.historyEntity = key;
            else { button.dataset.detailKind = table.id.startsWith('enemy') ? 'enemy' : 'character'; button.dataset.entity = key; }
            cell.append(button);
          }
        } else {
          const value = cells[cellIndex];
          // Keep the Text node itself. Replacing it on each update can disrupt
          // selections and create unnecessary child-list churn during sampling.
          if (!cell.firstChild) cell.append(table.ownerDocument.createTextNode(value.text));
          else if (cell.firstChild.data !== value.text) cell.firstChild.data = value.text;
          if (cell.title !== value.title) cell.title = value.title;
          if (value.freshness && cell.dataset.freshness !== value.freshness) cell.dataset.freshness = value.freshness;
          else if (!value.freshness && cell.dataset.freshness) delete cell.dataset.freshness;
        }
      });
      const current = body.children[index];
      if (current !== row) body.insertBefore(row, current || null);
    });
    for (const [key, row] of rows) if (!wanted.has(key)) { row.remove(); rows.delete(key); }
    const empty = body.querySelector('.empty-row');
    if (items.length) empty?.remove();
    else if (!empty) {
      const row = element('tr', 'empty-row');
      const cell = element('td', '', '当前没有可展示数据；请扫描或检查字段策略。');
      cell.colSpan = columns.length || 1; row.append(cell); body.append(row);
    }
    visible = nextVisible;
    return true;
  }
  return {update, layout, get columns() { return appliedColumns; }, rowFor: id => rows.get(String(id))};
}
