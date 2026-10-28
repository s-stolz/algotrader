import { installDesignProperties } from '@/design/cssProperties';

const PANE_OVERLAY_CLASS = 'indicators-wrapper';

export const PANE_OVERLAY_SELECTOR = `.${PANE_OVERLAY_CLASS}`;

export function getOrCreatePaneOverlayWrapper(
  paneHtmlElement: HTMLElement,
): HTMLDivElement {
  paneHtmlElement.style.position = 'relative';

  const existingWrapper = paneHtmlElement.querySelector(PANE_OVERLAY_SELECTOR);
  if (existingWrapper instanceof HTMLDivElement) {
    return existingWrapper;
  }

  const wrapper = document.createElement('div');
  wrapper.className = PANE_OVERLAY_CLASS;
  installDesignProperties(wrapper);
  wrapper.style.fontFamily = 'var(--design-font-ui)';
  wrapper.style.fontSize = 'var(--design-text-body)';
  wrapper.style.color = 'var(--design-color-body)';
  wrapper.style.fontVariantNumeric = 'tabular-nums';
  wrapper.style.cssText += `
    position: absolute;
    top: 10px;
    left: 0px;
    z-index: 1000;
    max-width: 350px;
  `;
  paneHtmlElement.appendChild(wrapper);

  return wrapper;
}
