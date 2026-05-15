<template>
  <div>
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
          <n-icon size="48" :depth="3">
            <CloudUploadOutline />
          </n-icon>
        </div>
        <n-text style="font-size: 16px">
          Click or drag a file to this area to upload
        </n-text>
        <n-p depth="3" style="margin: 8px 0 0 0">
          Supported formats: CSV or TSV<br />
          Maximum file size: 100MB
        </n-p>
      </n-upload-dragger>
    </n-upload>
  </div>
</template>

<script setup lang="ts">
import { NIcon, NP, NText, NUpload, NUploadDragger, type UploadFileInfo, type UploadOnChange } from 'naive-ui';

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

withDefaults(defineProps<{
  fileList?: UploadFileInfo[];
}>(), {
  fileList: () => [],
});

const emit = defineEmits<{
  (event: 'file-change', data: Parameters<UploadOnChange>[0]): void;
  (event: 'file-remove'): void;
}>();

function beforeUpload(data: BeforeUploadData): boolean {
  const maxSize = 100 * 1024 * 1024;
  const fileSize = data.file.file?.size ?? data.file.size ?? 0;

  if (fileSize > maxSize) {
    console.error('File size exceeds 100MB limit');
    return false;
  }

  return true;
}

function handleFileChange(data: Parameters<UploadOnChange>[0]): void {
  emit('file-change', data);
}

function handleFileRemove(): void {
  emit('file-remove');
}
</script>
