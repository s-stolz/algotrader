import fs from 'node:fs';
import path from 'node:path';
import { frontendSourceFiles } from './frontend-source.mjs';
import {
  limits,
  measureSource,
  migrationFailures,
} from './source-readability.mjs';

const root = process.cwd();
const measurements = Object.fromEntries(
  frontendSourceFiles(root).map((file) => [
    file,
    measureSource(fs.readFileSync(path.join(root, file), 'utf8'), file),
  ]),
);
const violations = Object.fromEntries(
  Object.entries(measurements).filter(
    ([, measurement]) =>
      measurement.countedLines > limits.lines || measurement.width.length,
  ),
);
if (process.argv.includes('--inventory')) {
  console.log(JSON.stringify(violations, null, 2));
} else {
  const strict = process.argv.includes('--strict');
  const inventory = strict
    ? { files: {} }
    : JSON.parse(
        fs.readFileSync(path.join(root, 'readability-inventory.json'), 'utf8'),
      );
  const failures = migrationFailures(measurements, inventory);
  if (failures.length) {
    console.error(`Frontend readability check failed:\n${failures.join('\n')}`);
    process.exitCode = 1;
  } else {
    console.log(
      `Frontend readability passed for ${Object.keys(measurements).length} files.`,
    );
    if (!strict)
      console.log(
        `Migration debt remains in ${Object.keys(violations).length} files.`,
      );
  }
}
