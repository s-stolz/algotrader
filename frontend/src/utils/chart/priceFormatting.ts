const DEFAULT_PRICE_PRECISION = 2;

export function marketPricePrecision(minMove: number): number {
  if (!Number.isFinite(minMove) || minMove <= 0) {
    return DEFAULT_PRICE_PRECISION;
  }

  const text = minMove.toString().toLowerCase();
  if (text.includes('e-')) {
    const [coefficient, exponentText] = text.split('e-');
    const exponent = Number(exponentText);
    const coefficientDecimals = coefficient.split('.')[1]?.length ?? 0;

    return Number.isFinite(exponent)
      ? exponent + coefficientDecimals
      : DEFAULT_PRICE_PRECISION;
  }

  if (text.includes('e+')) {
    return 0;
  }

  const decimalPart = text.split('.')[1];
  return decimalPart ? decimalPart.replace(/0+$/, '').length : 0;
}
