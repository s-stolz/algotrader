import { designTokens } from '@/design/tokens';

const chartFont = `${designTokens.text.secondary} ${designTokens.font.ui}`;

export function whenChartFontReady(render: () => void): () => void {
  let cancelled = false;
  const fonts = document.fonts;
  if (!fonts || fonts.check(chartFont)) {
    render();
  } else {
    // Request the face explicitly: an empty canvas has not triggered font loading.
    void fonts
      .load(chartFont)
      .then(() => fonts.ready)
      .then(
        () => {
          if (!cancelled) render();
        },
        () => {
          if (!cancelled) render();
        },
      );
  }
  return () => {
    cancelled = true;
  };
}
