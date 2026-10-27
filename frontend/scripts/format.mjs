import fs from 'node:fs/promises';
import path from 'node:path';
import * as prettier from 'prettier';
import { frontendSourceFiles } from './frontend-source.mjs';

const root = process.cwd();
const check = process.argv.includes('--check');
const failures = [];
for (const file of frontendSourceFiles(root)) {
  const filepath = path.join(root, file);
  const source = await fs.readFile(filepath, 'utf8');
  const options = { ...(await prettier.resolveConfig(filepath)), filepath };
  if (check) {
    if (!(await prettier.check(source, options))) failures.push(file);
  } else {
    await fs.writeFile(filepath, await prettier.format(source, options));
  }
}
if (failures.length) {
  console.error(`Unformatted frontend source:\n${failures.join('\n')}`);
  process.exitCode = 1;
} else {
  console.log(`Frontend formatting ${check ? 'check passed' : 'applied'}.`);
}
