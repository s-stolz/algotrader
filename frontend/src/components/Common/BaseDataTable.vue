<script lang="ts">
import { computed, defineComponent, h, mergeProps } from 'vue';
import { NDataTable, NScrollbar, NTable, dataTableProps } from 'naive-ui';

import { designTableTheme } from '@/design/naiveTheme';
import { designCssProperties } from '@/design/cssProperties';
import { designTokens } from '@/design/tokens';

export default defineComponent({
  name: 'BaseDataTable',
  inheritAttrs: false,
  props: {
    ...dataTableProps,
    rowHover: { type: Boolean, default: true },
  },
  setup(props, { attrs, slots }) {
    const mergedTheme = computed(() => ({
      ...designTableTheme,
      ...props.themeOverrides,
    }));

    const pagination = computed(() => {
      if (!props.pagination) return props.pagination;
      return {
        ...props.pagination,
        selectProps: {
          ...props.pagination.selectProps,
          menuProps: mergeProps(
            {
              style: {
                ...designCssProperties,
                fontFamily: designTokens.font.ui,
              },
            },
            { ...props.pagination.selectProps?.menuProps },
          ),
        },
      };
    });

    return () => {
      const { rowHover: _rowHover, ...tableProps } = props;
      return slots.default
        ? h(
            'div',
            mergeProps(attrs, {
              class: [
                'base-data-table',
                {
                  'base-data-table--row-hover': props.rowHover,
                },
              ],
            }),
            [
              h(
                NScrollbar,
                {
                  ...props.scrollbarProps,
                  xScrollable: true,
                  style: {
                    maxHeight:
                      typeof props.maxHeight === 'number'
                        ? `${props.maxHeight}px`
                        : props.maxHeight,
                  },
                },
                {
                  default: () =>
                    h(
                      NTable,
                      {
                        bordered: props.bordered ?? false,
                        striped: props.striped,
                        size: props.size,
                        singleLine: props.singleLine,
                        themeOverrides: mergedTheme.value,
                        style: {
                          minWidth: props.scrollX
                            ? `${props.scrollX}px`
                            : '100%',
                        },
                      },
                      { default: slots.default },
                    ),
                },
              ),
            ],
          )
        : h(
            NDataTable,
            mergeProps(attrs, tableProps, {
              class: [
                'base-data-table',
                {
                  'base-data-table--row-hover': props.rowHover,
                },
              ],
              bordered: props.bordered ?? false,
              themeOverrides: mergedTheme.value,
              pagination: pagination.value,
            }),
            slots,
          );
    };
  },
});
</script>

<style scoped>
.base-data-table {
  font-variant-numeric: tabular-nums;
  --table-heading-size: var(--design-text-secondary);
  --table-focus: var(--design-color-interactive);
}

/* Naive exposes a shared cell font size; headers need the secondary role. */
.base-data-table :deep(.n-table th) {
  font-size: var(--table-heading-size);
  letter-spacing: 0.025em;
}

/* Slot tables have no row-hover prop; column tables also support disabling it. */
.base-data-table--row-hover :deep(.n-table tbody tr:hover td) {
  background: var(--n-td-color-hover, var(--design-color-hover));
}

.base-data-table:not(.base-data-table--row-hover)
  :deep(.n-data-table-tr:hover .n-data-table-td) {
  background-color: var(--n-merged-td-color);
}

.base-data-table:not(.base-data-table--row-hover)
  :deep(.n-data-table-tr--striped:hover .n-data-table-td) {
  background-color: var(--n-merged-td-color-striped);
}

.base-data-table:not(.base-data-table--row-hover)
  :deep(.n-data-table-tr:hover .n-data-table-td--sorting) {
  background-color: var(--n-merged-td-color-sorting);
}

.base-data-table :deep(.n-data-table-th) {
  font-size: var(--table-heading-size);
  letter-spacing: 0.025em;
}

/* Naive has no separate fixed-cell theme; retain the opaque fixed surfaces. */
.base-data-table :deep(.n-data-table-td--fixed-left),
.base-data-table :deep(.n-data-table-td--fixed-right) {
  --n-merged-td-color: var(--design-color-fixed);
  --n-merged-td-color-striped: var(--design-color-fixed);
  --n-merged-td-color-hover: var(--design-color-fixed-hover);
  --n-merged-td-color-sorting: var(--design-color-fixed);
}

.base-data-table :deep(.n-data-table-th--fixed-left),
.base-data-table :deep(.n-data-table-th--fixed-right) {
  --n-merged-th-color: var(--design-color-selected);
  --n-merged-th-color-hover: var(--design-color-selected-hover);
  --n-merged-th-color-sorting: var(--design-color-selected-hover);
}

.base-data-table :deep(.n-data-table-tr:focus-visible) {
  outline: 2px solid var(--table-focus);
  outline-offset: -2px;
}
</style>
