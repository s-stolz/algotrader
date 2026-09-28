<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDataTable, NScrollbar, NTable, dataTableProps, type DataTableProps } from 'naive-ui';

const themeOverrides: NonNullable<DataTableProps['themeOverrides']> = {
  tdColor: '#1a2029',
  tdColorStriped: '#1d2530',
  tdColorHover: '#253340',
  tdColorSorting: '#202c38',
  thColor: '#171e27',
  thColorHover: '#253340',
  thColorSorting: '#202c38',
  borderColor: '#2b3541',
  tdTextColor: '#dce4ed',
  thTextColor: '#9aafbf',
  thFontWeight: '600',
  thIconColor: '#8190a0',
  thIconColorActive: '#63d2b0',
  thButtonColorHover: '#253340',
  loadingColor: '#63d2b0',
  borderRadius: '8px',
  boxShadowBefore: 'inset -12px 0 8px -12px rgba(0, 0, 0, .4)',
  boxShadowAfter: 'inset 12px 0 8px -12px rgba(0, 0, 0, .4)',
  tdColorModal: '#1a2029',
  tdColorStripedModal: '#1d2530',
  tdColorHoverModal: '#253340',
  tdColorSortingModal: '#202c38',
  thColorModal: '#171e27',
  thColorHoverModal: '#253340',
  thColorSortingModal: '#202c38',
  borderColorModal: '#2b3541',
  tdColorPopover: '#1a2029',
  tdColorStripedPopover: '#1d2530',
  tdColorHoverPopover: '#253340',
  tdColorSortingPopover: '#202c38',
  thColorPopover: '#171e27',
  thColorHoverPopover: '#253340',
  thColorSortingPopover: '#202c38',
  borderColorPopover: '#2b3541',
};

export default defineComponent({
  name: 'BaseDataTable',
  inheritAttrs: false,
  props: dataTableProps,
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({ ...themeOverrides, ...props.themeOverrides }));

    return () => slots.default ? h('div', mergeProps(attrs, {
      class: 'base-data-table',
    }), [h(NScrollbar, {
      ...props.scrollbarProps,
      xScrollable: true,
      style: { maxHeight: typeof props.maxHeight === 'number' ? `${props.maxHeight}px` : props.maxHeight },
    }, {
      default: () => h(NTable, {
        bordered: props.bordered ?? false,
        striped: props.striped,
        size: props.size,
        singleLine: props.singleLine,
        themeOverrides: mergedTheme.value,
        style: { minWidth: props.scrollX ? `${props.scrollX}px` : '100%' },
      }, { default: slots.default }),
    })]) : h(NDataTable, mergeProps(attrs, props, {
      class: 'base-data-table',
      bordered: props.bordered ?? false,
      themeOverrides: mergedTheme.value,
    }), slots);
  },
});
</script>

<style scoped>
.base-data-table {
  font-variant-numeric: tabular-nums;
}

.base-data-table :deep(.n-table th) {
  font-size: 11px;
  letter-spacing: .025em;
}

.base-data-table :deep(.n-table tbody tr:hover td) {
  background: #253340;
}

.base-data-table :deep(.n-data-table-th) {
  font-size: 11px;
  letter-spacing: .025em;
}

.base-data-table :deep(.n-data-table-td--fixed-left),
.base-data-table :deep(.n-data-table-td--fixed-right) {
  --n-merged-td-color: color-mix(in srgb, var(--n-td-color) 94%, white);
  --n-merged-td-color-striped: color-mix(in srgb, var(--n-td-color-striped) 94%, white);
  --n-merged-td-color-hover: color-mix(in srgb, var(--n-td-color-hover) 94%, white);
  --n-merged-td-color-sorting: color-mix(in srgb, var(--n-td-color-sorting) 94%, white);
}

.base-data-table :deep(.n-data-table-th--fixed-left),
.base-data-table :deep(.n-data-table-th--fixed-right) {
  --n-merged-th-color: color-mix(in srgb, var(--n-th-color) 94%, white);
  --n-merged-th-color-hover: color-mix(in srgb, var(--n-th-color-hover) 94%, white);
  --n-merged-th-color-sorting: color-mix(in srgb, var(--n-th-color-sorting) 94%, white);
}

.base-data-table :deep(.n-data-table-tr:focus-visible) {
  outline: 2px solid #63d2b0;
  outline-offset: -2px;
}
</style>
