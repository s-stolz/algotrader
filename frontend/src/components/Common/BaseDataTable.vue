<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDataTable, NScrollbar, NTable, dataTableProps, type DataTableProps } from 'naive-ui';

const themeOverrides: NonNullable<DataTableProps['themeOverrides']> = {
  tdColor: 'var(--surface-panel)',
  tdColorStriped: 'var(--surface-striped)',
  tdColorHover: 'var(--surface-hover)',
  tdColorSorting: 'var(--surface-sorted)',
  thColor: 'var(--surface-header)',
  thColorHover: 'var(--surface-hover)',
  thColorSorting: 'var(--surface-sorted)',
  borderColor: 'var(--surface-border)',
  tdTextColor: '#dce4ed',
  thTextColor: '#a5acba',
  thFontWeight: '600',
  thIconColor: '#8190a0',
  thIconColorActive: '#63d2b0',
  thButtonColorHover: 'var(--surface-hover)',
  loadingColor: '#63d2b0',
  borderRadius: '4px',
  boxShadowBefore: 'inset -12px 0 8px -12px rgba(0, 0, 0, .4)',
  boxShadowAfter: 'inset 12px 0 8px -12px rgba(0, 0, 0, .4)',
  tdColorModal: 'var(--surface-panel)',
  tdColorStripedModal: 'var(--surface-striped)',
  tdColorHoverModal: 'var(--surface-hover)',
  tdColorSortingModal: 'var(--surface-sorted)',
  thColorModal: 'var(--surface-header)',
  thColorHoverModal: 'var(--surface-hover)',
  thColorSortingModal: 'var(--surface-sorted)',
  borderColorModal: 'var(--surface-border)',
  tdColorPopover: 'var(--surface-panel)',
  tdColorStripedPopover: 'var(--surface-striped)',
  tdColorHoverPopover: 'var(--surface-hover)',
  tdColorSortingPopover: 'var(--surface-sorted)',
  thColorPopover: 'var(--surface-header)',
  thColorHoverPopover: 'var(--surface-hover)',
  thColorSortingPopover: 'var(--surface-sorted)',
  borderColorPopover: 'var(--surface-border)',
};

export default defineComponent({
  name: 'BaseDataTable',
  inheritAttrs: false,
  props: {
    ...dataTableProps,
    rowHover: { type: Boolean, default: true },
  },
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({ ...themeOverrides, ...props.themeOverrides }));

    return () => {
      const { rowHover: _rowHover, ...tableProps } = props;
      return slots.default ? h('div', mergeProps(attrs, {
        class: ['base-data-table', { 'base-data-table--row-hover': props.rowHover }],
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
      })]) : h(NDataTable, mergeProps(attrs, tableProps, {
        class: ['base-data-table', { 'base-data-table--row-hover': props.rowHover }],
        bordered: props.bordered ?? false,
        themeOverrides: mergedTheme.value,
      }), slots);
    };
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

.base-data-table--row-hover :deep(.n-table tbody tr:hover td) {
  background: var(--n-td-color-hover, var(--surface-hover));
}

.base-data-table:not(.base-data-table--row-hover) :deep(.n-data-table-tr:hover .n-data-table-td) {
  background-color: var(--n-merged-td-color);
}

.base-data-table:not(.base-data-table--row-hover) :deep(.n-data-table-tr--striped:hover .n-data-table-td) {
  background-color: var(--n-merged-td-color-striped);
}

.base-data-table:not(.base-data-table--row-hover) :deep(.n-data-table-tr:hover .n-data-table-td--sorting) {
  background-color: var(--n-merged-td-color-sorting);
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
