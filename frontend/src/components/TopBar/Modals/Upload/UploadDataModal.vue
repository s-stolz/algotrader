<template>
  <base-modal
    ref="baseModal"
    :modalId="'uploadData'"
    :title="`Upload Data for ${market.symbol}`"
  >
    <div class="upload-content">
      <n-tabs default-value="upload" type="line" :tabs-padding="20">
        <n-tab-pane name="upload" tab="Upload & Options">
          <upload-data-section
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
          <upload-data-preview
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
  </base-modal>
</template>

<script>
import { NButton, NTabs, NTabPane } from "naive-ui";
import BaseModal from "@/components/Common/BaseModal.vue";
import UploadDataPreview from "./UploadDataPreview.vue";
import UploadDataSection from "./UploadDataSection.vue";
import {
  getHeaderLine,
  getSeparator,
  getColumnMapping,
  parseCsvToCandles,
  uploadCandlesInBatches,
} from "./utils.js";

export default {
  name: "UploadDataModal",

  components: {
    NButton,
    NTabs,
    NTabPane,
    BaseModal,
    UploadDataPreview,
    UploadDataSection,
  },

  props: {
    market: {
      type: Object,
      required: true,
    },
  },

  emits: ["upload-successful"],

  data() {
    return {
      isUploading: false,
      fileList: [],
      headerLine: [],
      separator: undefined,
      columnMapping: {},
      separatorOptions: [",", "\t", ";", "|"],
    };
  },

  computed: {
    canUpload() {
      return this.fileList.length > 0 && !this.isUploading;
    },
  },

  methods: {
    closeModal() {
      this.$refs.baseModal.close();
      this.resetForm();
    },

    resetForm() {
      this.isUploading = false;
      this.fileList = [];
      this.headerLine = [];
      this.separator = null;
      this.columnMapping = {};
    },

    handleFileRemove() {
      this.fileList = [];
      this.headerLine = [];
      this.columnMapping = {};
    },

    async handleFileChange(data) {
      this.fileList = data.fileList;
      if (this.fileList.length == 0) {
        this.resetForm();
        return;
      }

      const file = this.fileList[0].file;
      const fileSize = file.size;

      const sampleSize = Math.min(10 * 1024, fileSize);
      const sampleBlob = file.slice(0, sampleSize);
      const csvSample = await sampleBlob.text();

      this.separator = getSeparator(csvSample, this.separatorOptions);
      this.headerLine = getHeaderLine(csvSample, this.separator);
      this.columnMapping = getColumnMapping(this.headerLine);
    },

    async uploadData() {
      if (!this.canUpload || !this.market) return;

      this.isUploading = true;

      try {
        const file = this.fileList[0].file;
        const fileSize = file.size;

        console.log(`Processing file (${(fileSize / 1024 / 1024).toFixed(1)}MB)...`);

        const candleData = await parseCsvToCandles(
          file,
          this.separator,
          this.columnMapping,
          (progress, rowCount) => {
            console.log(`Processing: ${progress.toFixed(1)}% (${rowCount} rows)`);
          },
        );

        if (!candleData || candleData.length === 0) {
          throw new Error("No valid candle data found in CSV file");
        }

        console.log(`Parsed ${candleData.length} candles, uploading...`);

        await uploadCandlesInBatches(
          this.market.symbol_id,
          candleData,
          (progress, uploadedCount) => {
            console.log(`Upload progress: ${progress.toFixed(1)}% (${uploadedCount} candles)`);
          },
        );

        this.$emit("upload-successful", this.market);
        this.closeModal();
      } catch (error) {
        console.error("Error uploading data:", error);
        alert(`Error uploading data: ${error.message}`);
      } finally {
        this.isUploading = false;
      }
    },
  },
};
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
