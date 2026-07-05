const PANE_OVERLAY_CLASS = 'indicators-wrapper';

export const PANE_OVERLAY_SELECTOR = `.${PANE_OVERLAY_CLASS}`;

export function getOrCreatePaneOverlayWrapper(paneHtmlElement: HTMLElement): HTMLDivElement {
  paneHtmlElement.style.position = 'relative';

  const existingWrapper = paneHtmlElement.querySelector(PANE_OVERLAY_SELECTOR);
  if (existingWrapper instanceof HTMLDivElement) {
    return existingWrapper;
  }

  const wrapper = document.createElement('div');
  wrapper.className = PANE_OVERLAY_CLASS;
  wrapper.style.cssText = `
    position: absolute;
    top: 10px;
    left: 0px;
    z-index: 1000;
    max-width: 350px;
  `;
  paneHtmlElement.appendChild(wrapper);

  return wrapper;
}
