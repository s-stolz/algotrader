import fs from 'node:fs';
import path from 'node:path';
import { frontendSourceFiles } from './frontend-source.mjs';
import {
  limits,
  measureSource,
  readabilityFailures,
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
  const failures = readabilityFailures(measurements);
  if (failures.length) {
    console.error(`Frontend readability check failed:\n${failures.join('\n')}`);
    process.exitCode = 1;
  } else {
    console.log(
      `Frontend readability passed for ${Object.keys(measurements).length} files.`,
    );
  }
}
