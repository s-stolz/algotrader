<script setup lang="ts">
import { NInputNumber } from 'naive-ui';
import BaseSelect from '@/components/Common/BaseSelect.vue';
import BacktestEntryLimitField from '../../BacktestEntryLimitField.vue';
import { directionOptions } from '../creationOptions';
import { useCreation } from '../creationContext';
const { draft, selections, setupErrors, touchSetup } = useCreation();
</script>
<template>
  <div class="settings-grid">
    <label data-setup-field="capital"
      >Initial capital
      <n-input-number
        v-model:value="draft.initial_capital"
        :min="0.01"
        data-testid="creation-capital"
        :status="setupErrors.capital ? 'error' : undefined"
        :input-props="{
          'aria-label': 'Initial capital',
          'aria-invalid': !!setupErrors.capital,
          'aria-describedby': setupErrors.capital
            ? 'creation-capital-error'
            : undefined,
        }"
        @update:value="touchSetup('capital')"
      />
      <small
        v-if="setupErrors.capital"
        id="creation-capital-error"
        role="alert"
        >{{ setupErrors.capital }}</small
      >
    </label>
    <BacktestEntryLimitField
      v-model:execution="draft.execution"
      data-setup-field="entryLimit"
    />
    <label
      class="full-width"
      data-setup-field="directions"
      >Allowed directions
      <BaseSelect
        v-model:value="selections.allowedDirections"
        multiple
        filterable
        clearable
        :options="directionOptions"
        data-testid="creation-directions"
        :status="setupErrors.directions ? 'error' : undefined"
        :input-props="{
          'aria-label': 'Allowed directions',
          'aria-invalid': !!setupErrors.directions,
          'aria-describedby': setupErrors.directions
            ? 'creation-directions-error'
            : undefined,
        }"
        @update:value="touchSetup('directions')"
      />
      <small
        v-if="setupErrors.directions"
        id="creation-directions-error"
        role="alert"
        >{{ setupErrors.directions }}</small
      >
    </label>
  </div>
</template>
