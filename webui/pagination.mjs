/** Slice a display page without changing collected/exportable rows. Size 0 means all. */
export function paginate(items, size = 15, page = 1) {
  size = Number.isInteger(size) && size >= 0 && size <= 10000 ? size : 15;
  const pages = size ? Math.max(1, Math.ceil(items.length / size)) : 1;
  page = Number.isInteger(page) ? Math.min(pages, Math.max(1, page)) : 1;
  const offset = size ? (page - 1) * size : 0;
  return {items: size ? items.slice(offset, offset + size) : items, page, pages, offset, total: items.length};
}

/** Stable controls survive high-frequency rendering without rebuilding selects/inputs. */
export function createPager(label, changed, size = 15) {
  const host = document.createElement('div'); host.className = 'pagination';
  const title = document.createElement('span'); title.textContent = '每页条数';
  const select = document.createElement('select'); select.setAttribute('aria-label', label + '每页条数');
  for (const [value, text] of [[5,'5'],[10,'10'],[15,'15'],[20,'20'],[50,'50'],[100,'100'],[0,'全部'],[-1,'自定义']]) {
    const option = document.createElement('option'); option.value = value; option.textContent = text; select.append(option);
  }
  select.value = size;
  const input = document.createElement('input'); input.type = 'number'; input.min = '1'; input.max = '10000'; input.step = '1'; input.placeholder = '自定义'; input.setAttribute('aria-label', label + '自定义条数');
  const apply = document.createElement('button'); apply.textContent = '应用'; apply.type = 'button';
  const previous = document.createElement('button'); previous.textContent = '上一页'; previous.type = 'button';
  const next = document.createElement('button'); next.textContent = '下一页'; next.type = 'button';
  const status = document.createElement('span'); status.className = 'pagination-status';
  const actions = document.createElement('span'); actions.className = 'pagination-actions';
  actions.setAttribute('role', 'group'); actions.setAttribute('aria-label', label + '翻页');
  actions.append(previous, next);
  let page = 1, pages = 1;
  host.append(title, select, input, apply, status, actions);
  select.onchange = () => { if (select.value === '-1') return input.focus(); size = Number(select.value); page = 1; changed(); };
  const custom = () => {
    const value = Number(input.value);
    input.setCustomValidity(Number.isInteger(value) && value >= 1 && value <= 10000 ? '' : '请输入 1–10000 的整数');
    if (!input.reportValidity()) return;
    size = value; page = 1; select.value = '-1'; changed();
  };
  apply.onclick = custom; input.oninput = () => input.setCustomValidity('');
  input.onkeydown = event => { if (event.key === 'Enter') custom(); };
  previous.onclick = () => { page = Math.max(1, page - 1); changed(); };
  next.onclick = () => { page = Math.min(pages, page + 1); changed(); };
  return {element: host, last: () => {page = pages;}, slice(items) {
    const result = paginate(items, size, page); page = result.page; pages = result.pages;
    const text = `${page}/${pages} 页 · 共 ${result.total} 条${select.value === '-1' ? ` · 每页 ${size} 条` : ''}`;
    // Identical property assignments still replace text nodes/set attributes.
    // Do not invalidate the table's surrounding layout on every sample.
    if (status.textContent !== text) status.textContent = text;
    if (previous.disabled !== (page <= 1)) previous.disabled = page <= 1;
    if (next.disabled !== (page >= pages)) next.disabled = page >= pages;
    return result;
  }};
}
