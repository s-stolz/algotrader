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

<script>
import { NIcon, NUpload, NUploadDragger, NText, NP } from "naive-ui";
import { CloudUploadOutline } from "@/icons";

export default {
  name: "UploadDataSection",

  components: {
    NIcon,
    NUpload,
    NUploadDragger,
    NText,
    NP,
    CloudUploadOutline,
  },

  props: {
    fileList: {
      type: Array,
      default: () => [],
    },
  },

  emits: ["file-change", "file-remove"],

  methods: {
    beforeUpload(data) {
      const { file } = data;
      const maxSize = 100 * 1024 * 1024; // 100MB

      if (file.size > maxSize) {
        console.error("File size exceeds 100MB limit");
        return false;
      }

      return true;
    },

    handleFileChange(data) {
      this.$emit("file-change", data);
    },

    handleFileRemove() {
      this.$emit("file-remove");
    },
  },
};
</script>
