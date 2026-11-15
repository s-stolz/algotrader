import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import * as prettier from 'prettier';
import { frontendSourceFiles } from './frontend-source.mjs';
import { measureSource, readabilityFailures } from './source-readability.mjs';

function fixture(t, files) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'frontend-readability-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  for (const [file, content] of Object.entries(files)) {
    fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
    fs.writeFileSync(path.join(root, file), content);
  }
  return root;
}

test('counts code while excluding only blank and actual comment-only lines', () => {
  const ts =
    '// comment\n/* comment\n */\nconst text = "/* value */";\n\ncall(); // end\n';
  assert.equal(measureSource(ts, 'example.ts').countedLines, 2);
  const css = '/* comment\n */\n.foo {\n content: "/* value */";\n}\n';
  assert.equal(measureSource(css, 'example.css').countedLines, 3);
  const vue = [
    '<!-- outside -->',
    '<template>',
    '<!-- inside -->',
    '<div />',
    '</template>',
    '<script setup lang="ts">',
    '// comment',
    'const value = 1;',
    '</script>',
    '<style>',
    '/* comment',
    ' */',
    '.foo { color: red; }',
    '</style>',
  ].join('\n');
  assert.equal(measureSource(vue, 'example.vue').countedLines, 9);
});

test('counts deployment code and quoted/heredoc content, excluding hash comments', () => {
  const shell = [
    '#!/bin/sh',
    '# comment',
    "printf '%s' 'first",
    '# literal',
    "last'",
    "cat <<'DATA'",
    '# literal',
    'DATA',
  ].join('\n');
  assert.equal(measureSource(shell, 'entrypoint-frontend.sh').countedLines, 6);
  const docker = '# comment\nFROM node:20\nRUN <<EOF\n# literal\nEOF';
  assert.equal(measureSource(docker, 'Dockerfile').countedLines, 4);
  assert.equal(
    measureSource('# comment\ndist\n', '.gitignore').countedLines,
    1,
  );
});

test('enforces 500 counted lines for source, tests, CSS, Vue and scripts', () => {
  for (const file of [
    'src/a.ts',
    'test/a.spec.ts',
    'scripts/a.mjs',
    'src/a.css',
    'src/a.vue',
    'entrypoint-frontend.sh',
    'Dockerfile',
  ]) {
    const line = file.endsWith('.css') ? '.a { color: red; }' : 'call();';
    const wrap = (text) =>
      file.endsWith('.vue') ? `<script>\n${text}</script>` : text;
    const boundary = file.endsWith('.vue') ? 498 : 500;
    const accepted = measureSource(wrap(`${line}\n`.repeat(boundary)), file);
    assert.equal(readabilityFailures({ [file]: accepted }).length, 0);
    const rejected = measureSource(
      wrap(`${line}\n`.repeat(boundary + 1)),
      file,
    );
    assert.equal(readabilityFailures({ [file]: rejected }).length, 1);
  }
});

test('limits width in all Vue blocks, CSS, scripts, and test files', () => {
  const long = 'x'.repeat(110);
  for (const [file, source] of [
    ['src/a.ts', `const text = '${long}';`],
    ['test/a.spec.ts', `expect('${long}').toBeTruthy();`],
    ['scripts/a.mjs', `console.log('${long}');`],
    ['entrypoint-frontend.sh', `printf '%s' '${long}'`],
    ['Dockerfile', `RUN echo '${long}'`],
    ['src/a.css', `.a { content: '${long}'; }`],
    ['src/a.vue', `<template><div title="${long}" /></template>`],
    ['src/a.vue', `<script>const text = '${long}';</script>`],
    ['src/a.vue', `<style>.a { content: '${long}'; }</style>`],
  ])
    assert.equal(measureSource(source, file).width.length, 1);
  assert.equal(measureSource('a'.repeat(100), 'a.ts').width.length, 0);
});

test('allows only standalone indivisible content, not surrounding compressible code', () => {
  const url = `https://example.com/${'x'.repeat(110)}`;
  const literal = 'x'.repeat(110);
  for (const source of [
    `'${literal}',`,
    `/${literal}/;`,
    `// ${url}`,
    `href="${url}"`,
  ]) {
    assert.equal(measureSource(source, 'a.css').width.length, 0);
  }
  for (const source of [
    `const url = '${url}';`,
    `call(/${literal}/);`,
    `title="${'ordinary text '.repeat(10)}"`,
    `'${'ordinary text '.repeat(10)}'`,
    `<a href="${url}" target="_blank">`,
  ])
    assert.equal(measureSource(source, 'a.css').width.length, 1);
});

test('discovers nested source/configuration and excludes generated artifacts', (t) => {
  const root = fixture(t, {
    'src/a.vue': '',
    'src/a.css': '',
    'src/dist/handwritten.ts': '',
    'test/a.spec.ts': '',
    'tools/check.mjs': '',
    'eslint.config.mjs': '',
    '.prettierrc.json': '{}',
    'tsconfig.json': '{}',
    'entrypoint-frontend.sh': '#!/bin/sh\n',
    Dockerfile: 'FROM node:20\n',
    '.dockerignore': 'node_modules\n',
    '.gitignore': 'dist\n',
    '.prettierignore': 'dist\n',
    'node_modules/pkg/a.ts': '',
    'dist/a.js': '',
    'coverage/a.js': '',
    'src/assets/font.ttf': '',
    'package-lock.json': '{}',
  });
  assert.deepEqual(frontendSourceFiles(root), [
    '.dockerignore',
    '.gitignore',
    '.prettierignore',
    '.prettierrc.json',
    'Dockerfile',
    'entrypoint-frontend.sh',
    'eslint.config.mjs',
    'src/a.css',
    'src/a.vue',
    'src/dist/handwritten.ts',
    'test/a.spec.ts',
    'tools/check.mjs',
    'tsconfig.json',
  ]);
});

test('normal CLI enforces hard limits without an inventory or exemptions', (t) => {
  const root = fixture(t, {
    'src/a.css': '.a { color: red; }\n'.repeat(501),
    'test/a.spec.ts': `call('${'x'.repeat(110)}');`,
  });
  const checker = fileURLToPath(
    new URL('./check-readability.mjs', import.meta.url),
  );
  const run = (...args) =>
    spawnSync(process.execPath, [checker, ...args], {
      cwd: root,
      encoding: 'utf8',
    });
  const failed = run();
  assert.equal(failed.status, 1);
  assert.match(failed.stderr, /src\/a.css: 501 counted lines/);
  assert.match(failed.stderr, /test\/a.spec.ts:1: width/);
  assert.equal(
    JSON.parse(run('--inventory').stdout)['src/a.css'].countedLines,
    501,
  );
  fs.writeFileSync(path.join(root, 'src/a.css'), '.a { color: red; }\n');
  fs.writeFileSync(path.join(root, 'test/a.spec.ts'), 'call();\n');
  assert.equal(run().status, 0);
});

test('formatter rejects compressed CSS and multi-attribute Vue equivalents', async () => {
  const config = await prettier.resolveConfig(process.cwd());
  for (const [filepath, source] of [
    ['a.css', '.a{color:red;background:blue}'],
    ['a.vue', '<template><div id="one" class="two" /></template>'],
    ['a.ts', 'const value={one:1,two:2};'],
  ]) {
    assert.equal(await prettier.check(source, { ...config, filepath }), false);
    assert.equal(
      await prettier.check(
        await prettier.format(source, { ...config, filepath }),
        { ...config, filepath },
      ),
      true,
    );
  }
});

test('formatter checks supported source beside deployment inputs', (t) => {
  const root = fixture(t, {
    'entrypoint-frontend.sh': '#!/bin/sh\nprintf "%s" "ready"\n',
    Dockerfile: 'FROM node:20\n',
    'src/a.ts': 'const value={one:1};',
  });
  const formatter = fileURLToPath(new URL('./format.mjs', import.meta.url));
  const run = () =>
    spawnSync(process.execPath, [formatter, '--check'], {
      cwd: root,
      encoding: 'utf8',
    });
  assert.equal(run().status, 1);
  assert.match(run().stderr, /src\/a.ts/);
  fs.writeFileSync(path.join(root, 'src/a.ts'), 'const value = { one: 1 };\n');
  assert.equal(run().status, 0);
});
