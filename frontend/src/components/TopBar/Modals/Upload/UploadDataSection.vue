<template>
  <div>
    <n-alert
      v-if="fileError"
      type="error"
      class="upload-feedback"
      role="alert"
    >
      {{ fileError }}
    </n-alert>
    <n-upload
      ref="upload"
      :file-list="fileList"
      :max="1"
      accept=".csv,.tsv"
      :before-upload="beforeUpload"
      @change="handleFileChange"
      @remove="handleFileRemove"
    >
      <n-upload-dragger>
        <div>
          <n-icon
            size="48"
            :depth="3"
          >
            <CloudUploadOutline />
          </n-icon>
        </div>
        <n-text class="upload-instruction">
          Click or drag a file to this area to upload
        </n-text>
        <n-p
          depth="3"
          class="upload-limits"
        >
          Supported formats: CSV or TSV<br />
          Maximum file size: 100MB
        </n-p>
      </n-upload-dragger>
    </n-upload>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import {
  NAlert,
  NIcon,
  NP,
  NText,
  NUpload,
  NUploadDragger,
  type UploadFileInfo,
  type UploadOnChange,
} from 'naive-ui';

import { CloudUploadOutline } from '@/icons';

defineOptions({
  name: 'UploadDataSection',
});

type UploadFileWithLegacySize = UploadFileInfo & {
  size?: number;
};

interface BeforeUploadData {
  file: UploadFileWithLegacySize;
}

withDefaults(
  defineProps<{
    fileList?: UploadFileInfo[];
  }>(),
  {
    fileList: () => [],
  },
);

const emit = defineEmits<{
  (event: 'file-change', data: Parameters<UploadOnChange>[0]): void;
  (event: 'file-remove'): void;
}>();

const fileError = ref('');

function beforeUpload(data: BeforeUploadData): boolean {
  fileError.value = '';
  const maxSize = 100 * 1024 * 1024;
  const fileSize = data.file.file?.size ?? data.file.size ?? 0;

  if (fileSize > maxSize) {
    fileError.value = 'File size exceeds 100MB limit';
    console.error(fileError.value);
    return false;
  }

  return true;
}

function handleFileChange(data: Parameters<UploadOnChange>[0]): void {
  emit('file-change', data);
}

function handleFileRemove(): void {
  fileError.value = '';
  emit('file-remove');
}
</script>

<style scoped>
.upload-feedback {
  margin-bottom: var(--design-space-md);
}

.upload-instruction {
  font-size: var(--design-text-heading);
}

.upload-limits {
  margin: var(--design-space-sm) 0 0;
  font-size: var(--design-text-secondary);
}
</style>
