<template>
  <span class="experiment-name">
    <input
      v-if="editing"
      ref="input"
      v-model="draft"
      aria-label="Experiment name"
      :aria-invalid="Boolean(error)"
      :aria-describedby="error ? errorId : undefined"
      @input="draftRevision++"
      @keydown.enter.prevent="commit"
      @keydown.esc.prevent="cancel"
      @blur="commit"
    >
    <button v-else type="button" :aria-label="`Edit experiment name: ${displayName}`" @click="start" @keydown.enter.prevent="start" @keydown.space.prevent="start">
      {{ displayName }}
    </button>
    <small v-if="saving || saved" role="status">{{ saving ? 'Saving…' : 'Saved' }}</small>
    <small v-if="error" :id="errorId" role="alert">{{ error }}</small>
  </span>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, useId, watch } from 'vue';
import { useBacktestWorkspaceStore } from '@/stores/backtestWorkspaceStore';
import { normalizeExperimentName } from '@/types/backtesterContracts';

const props = defineProps<{ kind: 'run' | 'batch'; experimentId: string; name?: string | null }>();
const store = useBacktestWorkspaceStore();
const editing = ref(false);
const draft = ref('');
const input = ref<HTMLInputElement | null>(null);
const saving = ref(false);
const saved = ref(false);
const error = ref<string | null>(null);
const errorId = useId();
const displayName = computed(() => props.name ??
  (props.kind === 'batch' ? 'Unnamed parameter sweep' : 'Unnamed standalone run'));
let editSession = 0;
let draftRevision = 0;
let activeSaveRevision: number | null = null;
type CommittedName = { kind: 'run' | 'batch'; id: string; name: string | null; revision: number };
let queuedCommit: CommittedName | null = null;
let savedTimer: ReturnType<typeof setTimeout> | undefined;

function reset(cancelQueued = false): void {
  const committed = queuedCommit;
  queuedCommit = null;
  if (committed && !cancelQueued) {
    // Leaving detail detaches presentation, but the committed identity still owns its write.
    void store.saveName(committed.kind, committed.id, committed.name).catch(() => undefined);
  }
  editSession++;
  activeSaveRevision = null;
  editing.value = false;
  saving.value = false;
  saved.value = false;
  error.value = null;
  draft.value = props.name ?? '';
  clearTimeout(savedTimer);
}
watch(() => `${props.kind}:${props.experimentId}`, () => reset());
onBeforeUnmount(reset);

async function start(): Promise<void> {
  reset();
  editing.value = true;
  await nextTick();
  input.value?.focus();
  input.value?.select();
}

function cancel(): void { reset(true); }

async function commit(): Promise<void> {
  if (!editing.value) return;
  let name: string | null;
  try { name = normalizeExperimentName(draft.value); } catch (failure) {
    error.value = failure instanceof Error ? failure.message : 'Invalid experiment name';
    return;
  }
  const committed: CommittedName = { name, revision: draftRevision, kind: props.kind, id: props.experimentId };
  if (saving.value) {
    if (draftRevision !== activeSaveRevision) queuedCommit = committed;
    return;
  }
  if (name === (props.name ?? null) && !error.value) { editing.value = false; return; }
  await saveCommittedDraft(committed);
}

async function saveCommittedDraft({ name, revision, kind, id }: CommittedName): Promise<void> {
  const session = editSession;
  saving.value = true;
  activeSaveRevision = revision;
  if (revision === draftRevision) error.value = null;
  try {
    const authoritative = await store.saveName(kind, id, name);
    if (session !== editSession) return;
    if (revision === draftRevision && !queuedCommit) {
      draft.value = authoritative ?? '';
      editing.value = false;
      saved.value = true;
      savedTimer = setTimeout(() => { saved.value = false; }, 2500);
    }
  } catch (failure) {
    if (session === editSession && revision === draftRevision) {
      error.value = failure instanceof Error ? failure.message : 'Save failed';
    }
  } finally {
    if (session === editSession) {
      saving.value = false;
      activeSaveRevision = null;
      const next = queuedCommit;
      queuedCommit = null;
      if (next) void saveCommittedDraft(next);
    }
  }
}
</script>

<style scoped>
.experiment-name { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 8px; }
button { font: inherit; color: inherit; background: none; border: none; padding: 0; cursor: text; text-align: left; }
button:focus-visible, input:focus-visible { outline: 2px solid var(--color-primary, #63b3ed); outline-offset: 3px; }
input { font: inherit; color: inherit; background: var(--surface-inset); border: 1px solid var(--surface-border); border-radius: 4px; padding: 2px 6px; width: min(32ch, 100%); }
small { font-size: 12px; font-weight: normal; }
small[role="alert"] { color: var(--color-error, #e88080); }
</style>
