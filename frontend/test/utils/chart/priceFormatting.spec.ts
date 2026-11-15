import { expect, it } from 'vitest';
import { marketPricePrecision } from '@/utils/chart/priceFormatting';

it('derives display precision from the active market min move', () => {
  expect(marketPricePrecision(1)).toBe(0);
  expect(marketPricePrecision(0.01)).toBe(2);
  expect(marketPricePrecision(0.00001)).toBe(5);
  expect(marketPricePrecision(1e-8)).toBe(8);
});
