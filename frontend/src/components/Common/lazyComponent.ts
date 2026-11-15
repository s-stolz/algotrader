import {
  defineComponent,
  h,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onMounted,
  ref,
  shallowRef,
  type Component,
  type VNode,
} from 'vue';
import BaseAsyncState from './BaseAsyncState.vue';

type LoadingContent = (state: VNode, attrs: Record<string, unknown>) => VNode;

// Declarative consumers receive props, events and slots; child methods are not exposed.
export function lazyComponent<T extends Component>(
  loader: () => Promise<{ default: T }>,
  label: string,
  loadingContent?: LoadingContent,
): T {
  return defineComponent({
    name: `Lazy${label.replace(/\W/g, '')}`,
    inheritAttrs: false,
    setup(_, { attrs, slots }) {
      const content = shallowRef<Component | null>(null);
      const failed = ref(false);
      let loaded: Component | null = null;
      let pending = false;
      let active = true;
      async function load(): Promise<void> {
        if (pending || loaded) return;
        pending = true;
        failed.value = false;
        try {
          loaded = (await loader()).default;
          // Downloads may finish in the cache without mounting hidden consumers.
          if (active) content.value = loaded;
        } catch {
          failed.value = true;
        } finally {
          pending = false;
        }
      }
      function activate() {
        active = true;
        content.value = loaded;
        void load();
      }
      onMounted(activate);
      onActivated(activate);
      onDeactivated(() => {
        active = false;
      });
      onBeforeUnmount(() => {
        active = false;
      });
      return () => {
        if (content.value) return h(content.value, attrs, slots);
        const state = h(BaseAsyncState, {
          style: { minHeight: '100%' },
          kind: failed.value ? 'error' : 'loading',
          label: failed.value ? `${label} unavailable` : `Loading ${label}`,
          message: failed.value ? `Couldn’t load ${label}.` : '',
          retry: failed.value,
          onRetry: load,
        });
        return loadingContent ? loadingContent(state, attrs) : state;
      };
    },
  }) as unknown as T;
}
