import { designTokens } from './tokens';

function kebabCase(value: string): string {
  return value.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`);
}

export const designCssProperties: Record<`--design-${string}`, string> =
  Object.fromEntries(
    Object.entries(designTokens).flatMap(([group, values]) =>
      Object.entries(values).map(([role, value]) => [
        `--design-${group}-${kebabCase(role)}`,
        value,
      ]),
    ),
  );

export function installDesignProperties(target: HTMLElement): void {
  for (const [name, value] of Object.entries(designCssProperties)) {
    target.style.setProperty(name, value);
  }
}
