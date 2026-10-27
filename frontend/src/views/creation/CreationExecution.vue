<template>
  <section
    class="settings-section"
    aria-labelledby="capital-heading"
  >
    <h3 id="capital-heading">Capital &amp; execution</h3>
    <p class="section-description"
      >Set the starting balance and simulation assumptions.</p
    >
    <div class="capital-field field-group">
      <label
        >Initial capital
        <n-input-number
          v-model:value="draft.initial_capital"
          :min="0.01"
          data-testid="creation-capital"
        />
      </label>
      <small
        v-if="fieldErrors.capital"
        role="alert"
        >{{ fieldErrors.capital }}</small
      >
    </div>
    <details class="execution-settings">
      <summary>Execution settings</summary>
      <div class="execution-group">
        <h4>Trading rules</h4>
        <div class="settings-grid">
          <label v-if="!isSweep"
            >Allowed Directions
            <BaseSelect
              v-model:value="draft.execution.allowed_directions"
              :options="directionOptions"
              data-testid="creation-directions"
            />
          </label>
          <label v-else
            >Allowed Directions
            <BaseSelect
              v-model:value="sweep.allowedDirections"
              multiple
              :options="directionOptions"
              data-testid="sweep-directions"
            />
          </label>
          <label
            >Engine
            <BaseSelect
              v-model:value="draft.engine"
              :options="engineOptions"
            />
          </label>
        </div>
      </div>
      <div class="execution-group">
        <h4>Trading costs</h4>
        <p class="section-description"
          >Costs are in basis points: 1 bp = 0.01%.</p
        >
        <div class="settings-grid">
          <label
            >Commission (bps)
            <n-input-number
              v-model:value="draft.execution.commission_bps"
              :min="0"
            />
          </label>
          <label
            >Slippage (bps)
            <n-input-number
              v-model:value="draft.execution.slippage_bps"
              :min="0"
            />
          </label>
        </div>
      </div>
      <div class="execution-group">
        <h4>Data &amp; fills</h4>
        <div class="settings-grid">
          <label
            >Gap policy
            <BaseSelect
              v-model:value="draft.execution.gap_policy"
              :options="gapOptions"
            />
          </label>
          <label
            >Intrabar exit policy
            <BaseSelect
              v-model:value="draft.execution.intrabar_exit_policy"
              :options="exitOptions"
            />
          </label>
        </div>
      </div>
    </details>
  </section>
</template>

<script setup lang="ts">
import BaseSelect from '@/components/Common/BaseSelect.vue';
import { NInputNumber } from 'naive-ui';
import {
  directionOptions,
  engineOptions,
  gapOptions,
  exitOptions,
} from './creationOptions';
import { useCreation } from './creationContext';
const { isSweep, draft, sweep, fieldErrors } = useCreation();
</script>
