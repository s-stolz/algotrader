import fs from 'node:fs';
import path from 'node:path';

const projectRoot = process.cwd();
const sourceRoot = path.join(projectRoot, 'src');
const testRoot = path.join(projectRoot, 'test');
const sourceTestDirectory = path.join(sourceRoot, 'test');
const rootSetupFile = path.join(projectRoot, 'setup.ts');
const testSetupFile = path.join(testRoot, 'setup.ts');
const misplacedSpecPattern = /\.(?:spec|test)\.[^/]+$/;
const mirroredSpecPattern = /\.(?:spec|test)\.ts$/;
const sourceExtensions = ['.ts', '.tsx', '.vue', '.d.ts'];

const failures = [];

function toDisplayPath(filePath) {
  return path.relative(projectRoot, filePath).split(path.sep).join('/');
}

function walkFiles(directory) {
  if (!fs.existsSync(directory)) {
    return [];
  }

  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const fullPath = path.join(directory, entry.name);

    if (entry.isDirectory()) {
      files.push(...walkFiles(fullPath));
      continue;
    }

    if (entry.isFile()) {
      files.push(fullPath);
    }
  }

  return files;
}

if (fs.existsSync(sourceTestDirectory)) {
  failures.push(`src/test must not exist: ${toDisplayPath(sourceTestDirectory)}`);
}

if (fs.existsSync(rootSetupFile)) {
  failures.push(`Vitest setup must live under test/: ${toDisplayPath(rootSetupFile)}`);
}

if (!fs.existsSync(testSetupFile)) {
  failures.push(`Missing Vitest setup file: ${toDisplayPath(testSetupFile)}`);
}

const sourceSpecs = walkFiles(sourceRoot).filter((filePath) => (
  misplacedSpecPattern.test(path.basename(filePath))
));

for (const specPath of sourceSpecs) {
  failures.push(`Spec files must not live under src/: ${toDisplayPath(specPath)}`);
}

const testSpecs = walkFiles(testRoot).filter((filePath) => (
  mirroredSpecPattern.test(path.basename(filePath))
));

for (const specPath of testSpecs) {
  const relativeSpecPath = path.relative(testRoot, specPath);
  const parsed = path.parse(relativeSpecPath);
  const sourceBasename = parsed.name.replace(/\.(?:spec|test)$/, '');
  const sourceCandidates = sourceExtensions.map((extension) => (
    path.join(sourceRoot, parsed.dir, `${sourceBasename}${extension}`)
  ));

  if (!sourceCandidates.some((candidate) => fs.existsSync(candidate))) {
    failures.push(
      `Spec file does not map to a source file: ${toDisplayPath(specPath)}`,
    );
  }
}

if (failures.length > 0) {
  console.error('Frontend test layout check failed:');
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log(`Frontend test layout check passed for ${testSpecs.length} spec files.`);
