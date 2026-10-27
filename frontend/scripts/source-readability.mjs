import path from 'node:path';
import tseslint from 'typescript-eslint';
import vueParser from 'vue-eslint-parser';

export const limits = { width: 100, lines: 500 };
const parserOptions = {
  ecmaVersion: 'latest',
  sourceType: 'module',
  range: true,
  loc: true,
  comment: true,
};

function cssComments(source, offset = 0) {
  const ranges = [];
  let quote = null;
  for (let index = 0; index < source.length; index += 1) {
    const character = source[index];
    if (character === '\\') {
      index += 1;
    } else if (quote) {
      if (character === quote) quote = null;
    } else if (character === '"' || character === "'") {
      quote = character;
    } else if (source.slice(index, index + 2) === '/*') {
      const end = source.indexOf('*/', index + 2);
      const stop = end < 0 ? source.length : end + 2;
      ranges.push([offset + index, offset + stop]);
      index = stop - 1;
    }
  }
  return ranges;
}

function commentRanges(source, extension) {
  if (extension === '.css') return cssComments(source);
  if (extension === '.json') return [];
  if (extension === '.vue' || extension === '.html') {
    const parsed = vueParser.parseForESLint(source, {
      ...parserOptions,
      parser: tseslint.parser,
    });
    const document = parsed.services.getDocumentFragment();
    const comments = [...parsed.ast.comments, ...document.comments];
    const ranges = comments.map((comment) => comment.range);
    for (const node of document.children) {
      if (node.type === 'VElement' && node.name === 'style') {
        const start = node.startTag.range[1];
        const end = node.endTag?.range[0] ?? node.range[1];
        ranges.push(...cssComments(source.slice(start, end), start));
      }
    }
    return ranges;
  }
  return tseslint.parser
    .parseForESLint(source, parserOptions)
    .ast.comments.map((comment) => comment.range);
}

function isIndivisible(line) {
  const trimmed = line.trim();
  if (/^(?:\/\/\s*|\*\s*)?https?:\/\/\S+$/.test(trimmed)) return true;
  const attribute = trimmed.match(
    /^(?:href|src|action)="(https?:\/\/[^\s"]+)"$/,
  );
  if (attribute) return attribute[1].length > limits.width;
  const expression = trimmed.replace(/[,;]$/, '');
  try {
    const { ast } = tseslint.parser.parseForESLint(expression, parserOptions);
    if (ast.body.length !== 1 || ast.body[0].type !== 'ExpressionStatement') {
      return false;
    }
    const value = ast.body[0].expression;
    if (value.type === 'Literal' && value.regex)
      return expression.length > limits.width;
    const text = value.type === 'Literal' ? value.value : null;
    return (
      typeof text === 'string' && !/\s/.test(text) && text.length > limits.width
    );
  } catch {
    return false;
  }
}

export function measureSource(source, filename) {
  const characters = source.split('');
  for (const [start, end] of commentRanges(source, path.extname(filename))) {
    for (let index = start; index < end; index += 1) {
      if (characters[index] !== '\n' && characters[index] !== '\r') {
        characters[index] = ' ';
      }
    }
  }
  const countedLines = characters
    .join('')
    .split(/\r?\n/)
    .filter((line) => line.trim()).length;
  const width = source
    .split(/\r?\n/)
    .flatMap((line, index) =>
      [...line].length > limits.width && !isIndivisible(line)
        ? [{ line: index + 1, width: [...line].length, text: line }]
        : [],
    );
  return { countedLines, width };
}

export function migrationFailures(measurements, inventory) {
  const failures = [];
  for (const [file, measurement] of Object.entries(measurements)) {
    const allowance = inventory.files[file];
    const maximum = allowance?.countedLines ?? limits.lines;
    if (measurement.countedLines > Math.max(limits.lines, maximum)) {
      failures.push(`${file}: ${measurement.countedLines} counted lines`);
    }
    const remaining = new Map();
    for (const line of allowance?.width ?? []) {
      remaining.set(line, (remaining.get(line) ?? 0) + 1);
    }
    for (const violation of measurement.width) {
      const count = remaining.get(violation.text) ?? 0;
      if (count) remaining.set(violation.text, count - 1);
      else failures.push(`${file}:${violation.line}: width ${violation.width}`);
    }
  }
  for (const file of Object.keys(inventory.files)) {
    const measurement = measurements[file];
    if (
      !measurement ||
      (measurement.countedLines <= limits.lines && !measurement.width.length)
    )
      failures.push(`${file}: remove resolved migration inventory entry`);
  }
  return failures;
}
