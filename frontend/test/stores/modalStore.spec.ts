import { createPinia, setActivePinia } from 'pinia';
import { beforeEach, describe, expect, it } from 'vitest';

import { useModalStore } from '@/stores/modalStore';

describe('modalStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('tracks active modal state by name', () => {
    const store = useModalStore();

    expect(store.activeModal).toBeNull();
    expect(store.isModalOpen('symbolSearch')).toBe(false);

    store.openModal('symbolSearch');

    expect(store.activeModal).toBe('symbolSearch');
    expect(store.isModalOpen('symbolSearch')).toBe(true);
    expect(store.isModalOpen('indicatorSearch')).toBe(false);

    store.closeModal();

    expect(store.activeModal).toBeNull();
  });
});
