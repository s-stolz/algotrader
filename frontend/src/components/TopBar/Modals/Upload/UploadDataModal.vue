<template>
  <BaseModal
    ref="baseModal"
    :modalId="'uploadData'"
    :title="`Upload Data for ${market.symbol}`"
  >
    <div class="upload-content">
      <n-tabs default-value="upload" type="line" :tabs-padding="20">
        <n-tab-pane name="upload" tab="Upload & Options">
          <UploadDataSection
            :file-list="fileList"
            @file-change="handleFileChange"
            @file-remove="handleFileRemove"
            class="upload-data-section"
          />
        </n-tab-pane>

        <n-tab-pane
          name="preview"
          tab="Preview & Mapping"
          :disabled="fileList.length === 0"
        >
          <UploadDataPreview
            :header-line="headerLine"
            v-model:column-mapping="columnMapping"
            class="upload-data-preview"
          />
        </n-tab-pane>
      </n-tabs>
    </div>

    <template #footer>
      <div class="modal-actions">
        <n-button @click="closeModal" class="button-cancel">Cancel</n-button>
        <n-button
          type="primary"
          @click="uploadData"
          :loading="isUploading"
          :disabled="!canUpload"
          class="button-upload"
        >
          Upload Data
        </n-button>
      </div>
    </template>
  </BaseModal>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { NButton, NTabPane, NTabs, type UploadFileInfo, type UploadOnChange } from 'naive-ui';

import BaseModal from '@/components/Common/BaseModal.vue';
import type { Candle, Market, UploadColumnMapping } from '@/types/contracts';

import UploadDataPreview from './UploadDataPreview.vue';
import UploadDataSection from './UploadDataSection.vue';
import {
  getColumnMapping,
  getHeaderLine,
  getSeparator,
  parseCsvToCandles,
  uploadCandlesInBatches,
} from './utils';

defineOptions({
  name: 'UploadDataModal',
});

interface BaseModalExpose {
  close: () => void;
}

const props = defineProps<{
  market: Market;
}>();

const emit = defineEmits<{
  (event: 'upload-successful', market: Market): void;
}>();

const baseModal = ref<BaseModalExpose | null>(null);
const isUploading = ref(false);
const fileList = ref<UploadFileInfo[]>([]);
const headerLine = ref<string[]>([]);
const separator = ref<string | null>(null);
const columnMapping = ref<UploadColumnMapping>({});
const separatorOptions = [',', '\t', ';', '|'];

const canUpload = computed(() => fileList.value.length > 0 && !isUploading.value);

function resetForm(): void {
  isUploading.value = false;
  fileList.value = [];
  headerLine.value = [];
  separator.value = null;
  columnMapping.value = {};
}

function closeModal(): void {
  baseModal.value?.close();
  resetForm();
}

function handleFileRemove(): void {
  fileList.value = [];
  headerLine.value = [];
  columnMapping.value = {};
}

async function handleFileChange(data: Parameters<UploadOnChange>[0]): Promise<void> {
  fileList.value = data.fileList;
  if (fileList.value.length === 0) {
    resetForm();
    return;
  }

  const file = fileList.value[0]?.file;
  if (!file) {
    resetForm();
    return;
  }

  const sampleSize = Math.min(10 * 1024, file.size);
  const sampleBlob = file.slice(0, sampleSize);
  const csvSample = await sampleBlob.text();

  separator.value = getSeparator(csvSample, separatorOptions);
  headerLine.value = getHeaderLine(csvSample, separator.value);
  columnMapping.value = getColumnMapping(headerLine.value);
}

async function uploadData(): Promise<void> {
  if (!canUpload.value) return;

  const file = fileList.value[0]?.file;
  if (!file || !separator.value) return;

  isUploading.value = true;

  try {
    console.log(`Processing file (${(file.size / 1024 / 1024).toFixed(1)}MB)...`);

    const candleData: Candle[] = await parseCsvToCandles(
      file,
      separator.value,
      columnMapping.value,
      (progress, rowCount) => {
        console.log(`Processing: ${progress.toFixed(1)}% (${rowCount} rows)`);
      },
    );

    if (candleData.length === 0) {
      throw new Error('No valid candle data found in CSV file');
    }

    console.log(`Parsed ${candleData.length} candles, uploading...`);

    await uploadCandlesInBatches(
      props.market.symbol,
      candleData,
      props.market.exchange,
      (progress, uploadedCount) => {
        console.log(`Upload progress: ${progress.toFixed(1)}% (${uploadedCount} candles)`);
      },
    );

    emit('upload-successful', props.market);
    closeModal();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error('Error uploading data:', error);
    alert(`Error uploading data: ${message}`);
  } finally {
    isUploading.value = false;
  }
}
</script>

<style scoped>
.upload-content {
  height: 300px;
}

.upload-data-section,
.upload-data-preview {
  padding: 0 20px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
