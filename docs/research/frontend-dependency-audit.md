# Frontend dependency audit — 2026-11-06

Planning snapshot; no packages upgraded. All 21 direct dependencies were checked against npm's live `latest` tag. Installed direct versions in both the local workspace and running `frontend` container (`npm ls --depth=0`) match the lockfile. Local Node is 24.18.0, but the Docker build uses `node:20-bookworm`. An extraneous local `ws@8.18.2` also exists; restore a clean installation with `npm ci` during implementation. All 281 installed package names, including transitives, were also checked against npm: see [installed dependency inventory](frontend-installed-dependencies.md). This is not a vulnerability audit.

## Inventory

Each registry link is the primary source for the latest version and its engine/peer constraints, queried on the date above. Latest does not imply an approved compatible target.

| Dependency | Declared | Installed / locked | Latest | Decision |
| --- | --- | --- | --- | --- |
| [lightweight-charts](https://registry.npmjs.org/lightweight-charts/latest) | `^5.0.2` | 5.0.7 | 5.2.1 | Upgrade in staged batch |
| [mitt](https://registry.npmjs.org/mitt/latest) | `~3.0.1` | 3.0.1 | 3.0.1 | Keep; current |
| [pinia](https://registry.npmjs.org/pinia/latest) | `^3.0.2` | 3.0.2 | 4.1.0 | Upgrade in staged batch |
| [vue](https://registry.npmjs.org/vue/latest) | `^3.5.16` | 3.5.16 | 3.5.45 | Upgrade in staged batch |
| [vue-router](https://registry.npmjs.org/vue-router/latest) | `~4.4.3` | 4.4.5 | 5.4.0 | Upgrade in staged batch |
| [@types/node](https://registry.npmjs.org/@types/node/latest) | `^25.8.0` | 25.8.0 | 26.6.6 | Align to chosen runtime major; prefer 24.x for Node 24 |
| [@vicons/ionicons5](https://registry.npmjs.org/@vicons/ionicons5/latest) | `^0.13.0` | 0.13.0 | 0.13.0 | Keep; current |
| [@vitejs/plugin-vue](https://registry.npmjs.org/@vitejs/plugin-vue/latest) | `^5.0.3` | 5.2.4 | 6.0.10 | Upgrade in staged batch |
| [@vue/test-utils](https://registry.npmjs.org/@vue/test-utils/latest) | `^2.4.10` | 2.4.10 | 2.5.1 | Upgrade in staged batch |
| [eslint](https://registry.npmjs.org/eslint/latest) | `^9.29.0` | 9.29.0 | 10.14.0 | Upgrade in staged batch |
| [eslint-config-prettier](https://registry.npmjs.org/eslint-config-prettier/latest) | `10.1.8` | 10.1.8 | 10.1.8 | Keep; current |
| [eslint-plugin-vue](https://registry.npmjs.org/eslint-plugin-vue/latest) | `^10.2.0` | 10.2.0 | 10.12.0 | Upgrade in staged batch |
| [jsdom](https://registry.npmjs.org/jsdom/latest) | `^29.1.1` | 29.1.1 | 31.0.0 | Upgrade in staged batch |
| [naive-ui](https://registry.npmjs.org/naive-ui/latest) | `^2.42.0` | 2.42.0 | 2.45.3 | Upgrade in staged batch |
| [prettier](https://registry.npmjs.org/prettier/latest) | `3.6.2` | 3.6.2 | 3.9.10 | Upgrade in staged batch |
| [typescript](https://registry.npmjs.org/typescript/latest) | `^6.0.3` | 6.0.3 | 7.0.2 | Hold 6.0.3: typescript-eslint latest requires <6.1.0 |
| [typescript-eslint](https://registry.npmjs.org/typescript-eslint/latest) | `^8.59.3` | 8.59.3 | 8.72.1 | Upgrade in staged batch |
| [vite](https://registry.npmjs.org/vite/latest) | `^6.3.5` | 6.3.5 | 8.3.6 | Upgrade in staged batch |
| [vitest](https://registry.npmjs.org/vitest/latest) | `^4.1.6` | 4.1.6 | 5.1.0 | Upgrade in staged batch |
| [vue-eslint-parser](https://registry.npmjs.org/vue-eslint-parser/latest) | `^10.1.3` | 10.1.3 | 10.4.1 | Upgrade in staged batch |
| [vue-tsc](https://registry.npmjs.org/vue-tsc/latest) | `^3.2.9` | 3.2.9 | 3.3.14 | Upgrade in staged batch |

## Ordered implementation plan and notable changes

1. **Normalize Node first.** Move Docker and CI/local tooling to a pinned Node 24 release at least 24.15.0; local 24.18.0 already meets the observed package requirements. Align `@types/node` with runtime major rather than blindly selecting 26. Latest jsdom requires `^22.22.2 || ^24.15.0 || >=26.0.0`; Vitest 5 requires Node 22.12+. These are verified registry engine constraints, not evidence that deployment has this runtime.
2. **Refresh Vue 3 and companion tooling without changing architectural patterns.** Vue 3.5.45, Vue test utils 2.5.1, vue-tsc 3.3.14 and Naive UI 2.45.3. Treat these as maintenance updates; verify reactive draft retention, keep-alive views, drawers, tables, focus and overlays. No major Vue migration is needed. Review each package's release details when implementing; no specific feature benefit is asserted here.
3. **Upgrade the build system in two reviewable steps: Vite 6 → 7 → 8.3.6, with plugin-vue 6.0.10.** Vite 8 replaces Rollup/esbuild internals with Rolldown/Oxc and changes the default browser target to Chrome/Edge 111, Firefox 114 and Safari 16.4. Check bundle output, proxying, dynamic imports, source maps and supported browser policy. The current config has no custom Rollup/esbuild options, reducing migration surface. Read both the [Vite 7 migration guide](https://v7.vite.dev/guide/migration) and [Vite 8 guide](https://vite.dev/guide/migration).
4. **Upgrade tests separately: Vitest 5.1.0, then jsdom 31.0.0.** Vitest 5 requires Vite >=6.4, makes Vite a peer dependency, and enables `clearMocks` by default. Audit tests relying on mock calls surviving between tests. Run tests after each upgrade so DOM behavior changes can be isolated. jsdom's major release and stricter runtime requirement warrant a separate batch; detailed jsdom 31 behavioral release notes were not verified in this audit. Sources: [Vitest migration](https://vitest.dev/guide/migration/), [jsdom registry metadata](https://registry.npmjs.org/jsdom/latest).
5. **Upgrade linting together; formatting separately.** ESLint 10.14.0 + typescript-eslint 8.72.1 + eslint-plugin-vue 10.12.0 + vue-eslint-parser 10.4.1 satisfy the observed peer ranges. ESLint 10 removes legacy config support, changes config lookup, and adds recommended rules. Validate editor and CLI behavior. Keep TypeScript 6.0.3: the latest typescript-eslint still declares `>=4.8.4 <6.1.0`, so TypeScript 7.0.2 is currently blocked for this supported combination. Upgrade Prettier to 3.9.10 in its own change to isolate formatting churn. Sources: [ESLint migration](https://eslint.org/docs/latest/use/migrate-to-10.0.0), [typescript-eslint peers](https://registry.npmjs.org/typescript-eslint/latest).
6. **Upgrade state and routing after the Vue/build baseline.** Pinia 4.1.0 is ESM-only and requires installing `@vue/devtools-api` alongside it (latest Pinia peer: `^8.2.1`). It improves diagnostics, fixes duplicate subscriptions, and adds `getStores()`. Vue Router 5.4.0 incorporates file-based routing; the official migration guide says ordinary v4 users without unplugin-vue-router have no breaking code changes. Do not introduce file-based routing merely to upgrade. Registry peers require Vue >=3.5.34 and compatible Vite/Pinia when those integrations are used. Check optional peer metadata before adding integrations. Verify navigation, keep-alive workspace state and subscription cleanup. Sources: [Pinia 4 release](https://github.com/vuejs/pinia/releases/tag/v4.0.0), [Pinia releases](https://github.com/vuejs/pinia/releases), [Router migration](https://router.vuejs.org/guide/migration/v4-to-v5.html).
7. **Upgrade charts in a dedicated visual regression change: 5.0.7 → 5.2.1.** Notable benefits include lower hover cost for large datasets with markers, autoscale reset fixes, corrected large marker anchoring, and a fix for crosshair errors when replacing multiple series with shorter data. Validate custom primitives, opening ranges, trades/protective overlays, measurement overlays, crosshair, pane sizing and history paging. Source: [Lightweight Charts release notes](https://tradingview.github.io/lightweight-charts/docs/release-notes).
8. **Hold already-current dependencies.** mitt 3.0.1, ionicons5 0.13.0 and eslint-config-prettier 10.1.8 need no version change. Reconsider TypeScript 7 only once lint tooling explicitly supports it and Vue typechecking passes in a trial branch.

For every batch, regenerate and review the lockfile, use a clean install, run `make test frontend`, and inspect production build output. Run `make verify` at integration. Do not mix intentional visual changes with dependency regression fixes. Revert the batch's manifest and lockfile together if its gate fails; retain the preceding tested runtime image. No application tests were run for this research-only document.

## Scope and follow-up

All direct dependencies are covered above, including UI packages currently classified as devDependencies. Transitive dependencies are inventoried separately and should be refreshed through their owners and audited from a clean resolved tree before implementation; this report does not claim they are free of advisories. The registry JSON captured during this audit is available in `/tmp/frontend-audit.json` for this session, but the durable version snapshot is the table above. Running frontend container direct dependencies were inspected and match the table; this does not establish versions in remote deployments.
