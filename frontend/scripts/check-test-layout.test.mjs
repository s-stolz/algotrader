import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const checker = fileURLToPath(
  new URL('./check-test-layout.mjs', import.meta.url),
);
function fixture(t, files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'frontend-layout-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const file of ['test/setup.ts', ...files]) {
    fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
    fs.writeFileSync(path.join(root, file), '');
  }
  return spawnSync(process.execPath, [checker], {
    cwd: root,
    encoding: 'utf8',
  });
}

test('accepts exact, dotted-owner and descriptive suites with shared helpers', (t) => {
  const result = fixture(t, [
    'src/chart/session.ts',
    'src/chart/chart.options.ts',
    'test/chart/session.spec.ts',
    'test/chart/session.history-paging.spec.ts',
    'test/chart/chart.options.spec.ts',
    'test/chart/session.fixtures.ts',
    'test/helpers/adapter.ts',
  ]);
  assert.equal(result.status, 0, result.stderr);
});

test('rejects behavior suites whose actual mirrored source owner does not exist', (t) => {
  const result = fixture(t, [
    'src/chart/session.ts',
    'test/chart/missing.history-paging.spec.ts',
    'test/other/session.history-paging.spec.ts',
  ]);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /missing.history-paging.spec.ts/);
  assert.match(result.stderr, /other\/session.history-paging.spec.ts/);
});

test('retains source-tree spec and setup-file placement checks', (t) => {
  const result = fixture(t, ['src/chart/session.spec.ts', 'setup.ts']);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Spec files must not live under src/);
  assert.match(result.stderr, /Vitest setup must live under test/);
});
