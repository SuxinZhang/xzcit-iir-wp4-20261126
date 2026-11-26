const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const OTA_JS = path.resolve(__dirname, '..', 'js', 'ota.js');
const OTA_CSS = path.resolve(__dirname, '..', 'styles', 'ota.css');

test('ota.js exposes management page hooks', () => {
  const source = fs.readFileSync(OTA_JS, 'utf8');
  assert.match(source, /C\.OTA/);
  assert.match(source, /\/api\/ota\/upload/);
  assert.match(source, /\/api\/ota\/apply/);
  assert.match(source, /\/ws\/ota\/progress/);
  assert.match(source, /ota-rollback-btn/);
});

test('ota page includes upload and version cards', () => {
  const source = fs.readFileSync(OTA_JS, 'utf8');
  assert.match(source, /ota-fw-version/);
  assert.match(source, /ota-master-version/);
  assert.match(source, /ota-model-version/);
  assert.match(source, /ota-interlocks/);
});

test('ota.css keeps responsive layout', () => {
  const source = fs.readFileSync(OTA_CSS, 'utf8');
  assert.match(source, /@media/);
  assert.match(source, /ota-progress-bar/);
});
