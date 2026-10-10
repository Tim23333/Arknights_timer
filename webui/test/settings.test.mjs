import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const html = await readFile(new URL('../index.html', import.meta.url), 'utf8');
const app = await readFile(new URL('../app.mjs', import.meta.url), 'utf8');

// The user requested removing persistent progress banners, not the existing
// automatic detection toggle or notification path. Rendering must not retain a
// direct dataset write to the removed element, which would break initialization.
test('settings omit persistent refresh banners and their render references', () => {
  assert.doesNotMatch(html, /id="auto-refresh-status"/);
  assert.doesNotMatch(html, /id="overview-auto-refresh"/);
  assert.doesNotMatch(app, /['"]auto-refresh-status['"]/);
  assert.doesNotMatch(app, /['"]overview-auto-refresh['"]/);
  assert.match(html, /自动检测关卡变化/);
  assert.match(app, /ui\.data\.notifications/);
});

test('settings hide generation while policy writes still carry concurrency generation', () => {
  assert.doesNotMatch(html, /id="policy-generation"/);
  assert.doesNotMatch(app, /['"]policy-generation['"]/);
  assert.match(app, /api\("\/api\/policy", \{generation: ui\.policy\.generation,/);
  assert.match(html, /<th>采集<\/th><th>本地展示<\/th><th>WS 发布<\/th>/);
});
