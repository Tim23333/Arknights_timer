/**
 * Resolves widths from column definitions, never from changing sample values.
 * Explicitly fitted widths are keyed by field so hiding/reordering columns does
 * not transfer a width to the wrong field. Returned widths are CSS pixels.
 */
export function columnWidths(columns, fitted = new Map()) {
  return columns.map(column => {
    const width = fitted.get(column.key) ?? column.width;
    if (typeof width === 'number' && Number.isFinite(width) && width > 0) {
      return Math.max(36, Math.min(480, Math.ceil(width)));
    }
    if (column.key === 'detail') return 64;
    if (column.key === 'row') return 40;
    return Math.max(120, Math.min(240, String(column.label || column.key).length * 12 + 24));
  });
}

/**
 * Owns stable geometry for a live data table. Call apply only when its column
 * definitions change; fit measures the currently displayed page once, on an
 * explicit user request (all columns or one field key). Normal sample updates
 * do not measure or resize cells.
 * Long values stay in the DOM/title; the presentation clips, not the data.
 */
export function createTableLayout(table) {
  let columns = [];
  const fitted = new Map();
  const group = table.ownerDocument.createElement('colgroup');
  table.prepend(group);
  table.classList.add('stable-table');

  function apply(nextColumns) {
    columns = nextColumns;
    const widths = columnWidths(columns, fitted);
    group.replaceChildren(...widths.map(width => {
      const col = table.ownerDocument.createElement('col');
      col.style.width = `${width}px`;
      return col;
    }));
    table.style.width = `${widths.reduce((total, width) => total + width, 0)}px`;
    for (const [index, column] of columns.entries()) {
      const header = table.tHead.rows[0]?.cells[index];
      if (!header || header.querySelector('.column-fit-handle')) continue;
      const handle = table.ownerDocument.createElement('button');
      handle.type = 'button';
      handle.className = 'column-fit-handle';
      handle.title = `双击自适应「${column.label || column.key}」列宽`;
      handle.setAttribute('aria-label', handle.title);
      handle.ondblclick = event => { event.preventDefault(); event.stopPropagation(); fit(column.key); };
      handle.onkeydown = event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault(); event.stopPropagation(); fit(column.key);
      };
      header.append(handle);
    }
  }

  function fit(key) {
    if (!columns.length || (key !== undefined && !columns.some(column => column.key === key))) return false;
    const context = table.ownerDocument.createElement('canvas').getContext('2d');
    if (!context) return false;
    const view = table.ownerDocument.defaultView;
    const rows = [...table.tBodies[0].rows].filter(row => !row.classList.contains('empty-row'));
    const defaults = columnWidths(columns);
    columns.forEach((column, index) => {
      if (key !== undefined && column.key !== key) return;
      if (key === undefined && column.key === 'detail') return;
      const header = table.tHead.rows[0].cells[index];
      const headerStyle = view.getComputedStyle(header);
      const bodyStyle = rows.length ? view.getComputedStyle(rows[0].cells[index]) : headerStyle;
      const font = style => `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
      const padding = style => parseFloat(style.paddingLeft) + parseFloat(style.paddingRight) + 2;
      context.font = font(headerStyle);
      let width = context.measureText(header.textContent).width + padding(headerStyle);
      context.font = font(bodyStyle);
      for (const row of rows) {
        // Match nowrap's whitespace collapsing, without changing the source text.
        const cell = row.cells[index];
        const text = cell.textContent.replace(/\s+/g, ' ');
        // The freshness marker is a CSS pseudo-element, not source text.
        // Include its reserved width when the user explicitly fits a column.
        const markerWidth = cell.dataset.freshness ? parseFloat(view.getComputedStyle(cell, '::before').width) || 0 : 0;
        width = Math.max(width, context.measureText(text).width + padding(bodyStyle) + markerWidth);
      }
      // Bound very long predictions/JSON so one cell cannot consume the screen.
      // With no data, retain the meaningful default rather than fitting to '--'.
      fitted.set(column.key, rows.length ? Math.max(36, Math.min(480, Math.ceil(width + 8))) : defaults[index]);
    });
    apply(columns);
    return true;
  }

  return {apply, fit};
}
