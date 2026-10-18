import {metaParts} from './model.mjs';

/**
 * Owns stable sampling-status geometry for live entity table headers.
 * Status, labels and numeric slots are created once. Unknown values remain
 * unknown: this renderer neither retains nor invents a source/current frame.
 * Only changed Text nodes are updated; fixed frame slots prevent shifting the
 * entire header when a frame alternates between a number and an em dash.
 */
export function createSourceMeta(container, {sourceLabel='来源帧', additionalFrames=[]} = {}) {
  const document = container.ownerDocument;
  const status = document.createElement('span');
  status.className = 'meta-status';
  const source = document.createElement('span');
  const latest = document.createElement('span');
  const extra=additionalFrames.map(field=>({...field,element:document.createElement('span')}));
  for (const [value, label] of [[source, sourceLabel], [latest, '最近已知帧'], ...extra.map(field=>[field.element,field.label])]) {
    const group = document.createElement('span');
    group.className = 'meta-field';
    const caption = document.createElement('span');
    caption.textContent = label;
    value.className = 'meta-frame';
    value.setAttribute('aria-label', label);
    group.append(caption, value);
    container.append(group);
  }
  container.prepend(status);
  container.classList.add('frame-meta');
  for (const value of [status, source, latest, ...extra.map(field=>field.element)]) value.append(document.createTextNode('—'));

  return {
    update(meta, statusText) {
      const parts = metaParts(meta);
      for (const [element, text] of [[status, statusText ?? parts.status], [source, parts.source], [latest, parts.latest], ...extra.map(field=>[field.element,String(meta?.[field.key] ?? '—')])]) {
        if (element.firstChild.data !== text) element.firstChild.data = text;
      }
    },
  };
}
