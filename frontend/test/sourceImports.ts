import { existsSync, readFileSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import ts from 'typescript';

const root = resolve(import.meta.dirname, '..');
export function runtimeImports(file: string): string[] {
  let source = readFileSync(resolve(root, file), 'utf8');
  if (file.endsWith('.vue'))
    source = [...source.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)]
      .map((match) => match[1])
      .join('\n');
  const tree = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true);
  return tree.statements.flatMap((node) => {
    if (ts.isImportDeclaration(node)) {
      if (node.importClause?.isTypeOnly) return [];
      const bindings = node.importClause?.namedBindings;
      if (
        !node.importClause?.name &&
        bindings &&
        ts.isNamedImports(bindings) &&
        bindings.elements.length &&
        bindings.elements.every((entry) => entry.isTypeOnly)
      )
        return [];
      return [(node.moduleSpecifier as ts.StringLiteral).text];
    }
    if (
      ts.isExportDeclaration(node) &&
      node.moduleSpecifier &&
      !node.isTypeOnly
    ) {
      if (
        node.exportClause &&
        ts.isNamedExports(node.exportClause) &&
        node.exportClause.elements.every((entry) => entry.isTypeOnly)
      )
        return [];
      return [(node.moduleSpecifier as ts.StringLiteral).text];
    }
    return [];
  });
}
export function staticModules(entry: string): Set<string> {
  const visited = new Set<string>();
  function visit(file: string) {
    if (visited.has(file)) return;
    visited.add(file);
    for (const spec of runtimeImports(file)) {
      const base = spec.startsWith('@/')
        ? resolve(root, 'src', spec.slice(2))
        : spec.startsWith('.')
          ? resolve(root, dirname(file), spec)
          : null;
      if (!base) continue;
      const target = [
        base,
        `${base}.ts`,
        `${base}.vue`,
        `${base}/index.ts`,
      ].find((path) => existsSync(path) && statSync(path).isFile());
      if (target) visit(target.slice(root.length + 1));
    }
  }
  visit(entry);
  return visited;
}
