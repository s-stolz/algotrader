<template>
    <div
        v-if="visible"
        class="modal-backdrop"
        @mousedown="onMouseDown"
        @mouseup="onMouseUp"
    >
        <div class="modal" @click.stop>
            <header class="modal-header">
                <div class="header-content">
                    <h2 class="title">{{ title }}</h2>
                    <button class="close-button" @click="close">&times;</button>
                </div>
                <hr class="separator" />
            </header>
            <div class="modal-body">
                <slot></slot>
            </div>
            <footer class="modal-footer">
                <slot name="footer"></slot>
            </footer>
        </div>
    </div>
</template>

<script>
export default {
    name: "Modal",

    props: {
        visible: {
            type: Boolean,
            required: true,
        },
        title: {
            type: String,
            default: "Modal Title",
        },
        closeOnBackdrop: {
            type: Boolean,
            default: true,
        },
    },

    emits: ["update:visible"],

    expose: ["close"],

    data() {
        return {
            isMouseDownInside: false,
        };
    },

    methods: {
        close() {
            this.$emit("update:visible", false);
        },
        onMouseDown(event) {
            // Check if the mouse is pressed inside the modal
            this.isMouseDownInside = event.target.closest(".modal") !== null;
        },
        onMouseUp(event) {
            // Only close if the mouse started and ended outside the modal
            if (!this.isMouseDownInside && this.closeOnBackdrop) {
                this.close();
            }
        },
    },
};
</script>

<style scoped>
.modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal {
    position: relative;
    background: #131722;
    border-radius: 15px;
    border: 3px solid rgb(13, 14, 16);
    max-width: 500px;
    width: 100%;
    padding: 0;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.modal-header {
    display: flex;
    flex-direction: column;
    gap: 8px; /* Add space between the header content and the hr */
}

.header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header .title {
    margin: 0;
    padding-top: 10px;
    padding-left: 15px;
}

.modal-header .separator {
    border: none;
    height: 1px;
    background-color: #ddd;
    margin: 0;
}

.modal-footer {
    margin-top: 16px;
    text-align: right;
}

.close-button {
    position: absolute;
    top: 10px;
    right: 10px;
    background: none;
    border: none;
    font-size: 1.5rem;
    line-height: 1;
    cursor: pointer;
}
</style>
