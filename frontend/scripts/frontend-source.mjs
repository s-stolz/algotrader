import fs from 'node:fs';
import path from 'node:path';

const sourceExtensions = new Set([
  '.vue',
  '.ts',
  '.tsx',
  '.js',
  '.mjs',
  '.cjs',
  '.css',
  '.json',
  '.html',
]);
const generatedDirectories = new Set([
  'node_modules',
  'dist',
  'coverage',
  '.git',
  '.vite',
  '.vite-temp',
]);
const generatedFiles = new Set([
  'package-lock.json',
  'readability-inventory.json',
]);

export function frontendSourceFiles(root) {
  const files = [];
  function visit(directory) {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const absolute = path.join(directory, entry.name);
      const relative = path.relative(root, absolute).split(path.sep).join('/');
      if (entry.isDirectory() && !generatedDirectories.has(relative)) {
        visit(absolute);
      } else if (
        entry.isFile() &&
        sourceExtensions.has(path.extname(entry.name)) &&
        !generatedFiles.has(relative)
      ) {
        files.push(relative);
      }
    }
  }
  visit(root);
  return files.sort();
}
