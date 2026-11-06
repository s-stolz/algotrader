# Frontend installed dependency inventory — 2026-11-06

Read-only `docker exec frontend npm ls --all --json` inventory, compared with live npm latest tags. Includes direct and transitive libraries; multiple installed versions are preserved. A different latest version is not proof an upgrade is compatible. Upgrade transitive packages through their direct owners; do not force registry-latest overrides. Optional platform packages absent from this container are not included.

| Package | Installed version(s) | npm latest | Status |
| --- | --- | --- | --- |
| [@asamuzakjp/css-color](https://registry.npmjs.org/@asamuzakjp/css-color/latest) | 5.1.11 | 7.1.9 | Review through owner |
| [@asamuzakjp/dom-selector](https://registry.npmjs.org/@asamuzakjp/dom-selector/latest) | 7.1.1 | 10.0.5 | Review through owner |
| [@asamuzakjp/generational-cache](https://registry.npmjs.org/@asamuzakjp/generational-cache/latest) | 1.0.1 | 3.0.1 | Review through owner |
| [@asamuzakjp/nwsapi](https://registry.npmjs.org/@asamuzakjp/nwsapi/latest) | 2.3.9 | 2.3.9 | Current |
| [@babel/helper-string-parser](https://registry.npmjs.org/@babel/helper-string-parser/latest) | 7.27.1 | 8.0.8 | Review through owner |
| [@babel/helper-validator-identifier](https://registry.npmjs.org/@babel/helper-validator-identifier/latest) | 7.27.1 | 8.0.6 | Review through owner |
| [@babel/parser](https://registry.npmjs.org/@babel/parser/latest) | 7.27.3 | 8.1.0 | Review through owner |
| [@babel/types](https://registry.npmjs.org/@babel/types/latest) | 7.27.3 | 8.1.0 | Review through owner |
| [@bramus/specificity](https://registry.npmjs.org/@bramus/specificity/latest) | 2.4.2 | 2.4.3 | Review through owner |
| [@css-render/plugin-bem](https://registry.npmjs.org/@css-render/plugin-bem/latest) | 0.15.14 | 0.15.14 | Current |
| [@css-render/vue3-ssr](https://registry.npmjs.org/@css-render/vue3-ssr/latest) | 0.15.14 | 0.15.14 | Current |
| [@csstools/color-helpers](https://registry.npmjs.org/@csstools/color-helpers/latest) | 6.0.2 | 6.1.2 | Review through owner |
| [@csstools/css-calc](https://registry.npmjs.org/@csstools/css-calc/latest) | 3.2.1 | 3.4.3 | Review through owner |
| [@csstools/css-color-parser](https://registry.npmjs.org/@csstools/css-color-parser/latest) | 4.1.1 | 4.2.7 | Review through owner |
| [@csstools/css-parser-algorithms](https://registry.npmjs.org/@csstools/css-parser-algorithms/latest) | 4.0.0 | 4.0.2 | Review through owner |
| [@csstools/css-syntax-patches-for-csstree](https://registry.npmjs.org/@csstools/css-syntax-patches-for-csstree/latest) | 1.1.4 | 1.1.16 | Review through owner |
| [@csstools/css-tokenizer](https://registry.npmjs.org/@csstools/css-tokenizer/latest) | 4.0.0 | 4.0.2 | Review through owner |
| [@emotion/hash](https://registry.npmjs.org/@emotion/hash/latest) | 0.8.0 | 0.9.2 | Review through owner |
| [@esbuild/linux-arm64](https://registry.npmjs.org/@esbuild/linux-arm64/latest) | 0.25.5 | 0.28.2 | Review through owner |
| [@eslint-community/eslint-utils](https://registry.npmjs.org/@eslint-community/eslint-utils/latest) | 4.9.1 | 4.10.1 | Review through owner |
| [@eslint-community/regexpp](https://registry.npmjs.org/@eslint-community/regexpp/latest) | 4.12.2 | 4.12.2 | Current |
| [@eslint/config-array](https://registry.npmjs.org/@eslint/config-array/latest) | 0.20.1 | 0.23.5 | Review through owner |
| [@eslint/config-helpers](https://registry.npmjs.org/@eslint/config-helpers/latest) | 0.2.3 | 0.7.0 | Review through owner |
| [@eslint/core](https://registry.npmjs.org/@eslint/core/latest) | 0.14.0, 0.15.0 | 1.2.1 | Review through owner |
| [@eslint/eslintrc](https://registry.npmjs.org/@eslint/eslintrc/latest) | 3.3.1 | 3.3.7 | Review through owner |
| [@eslint/js](https://registry.npmjs.org/@eslint/js/latest) | 9.29.0 | 10.0.1 | Review through owner |
| [@eslint/object-schema](https://registry.npmjs.org/@eslint/object-schema/latest) | 2.1.6 | 3.0.5 | Review through owner |
| [@eslint/plugin-kit](https://registry.npmjs.org/@eslint/plugin-kit/latest) | 0.3.2 | 0.7.3 | Review through owner |
| [@exodus/bytes](https://registry.npmjs.org/@exodus/bytes/latest) | 1.15.0 | 1.16.0 | Review through owner |
| [@humanfs/core](https://registry.npmjs.org/@humanfs/core/latest) | 0.19.1 | 0.20.0 | Review through owner |
| [@humanfs/node](https://registry.npmjs.org/@humanfs/node/latest) | 0.16.6 | 0.17.0 | Review through owner |
| [@humanwhocodes/module-importer](https://registry.npmjs.org/@humanwhocodes/module-importer/latest) | 1.0.1 | 1.0.1 | Current |
| [@humanwhocodes/retry](https://registry.npmjs.org/@humanwhocodes/retry/latest) | 0.3.1, 0.4.3 | 0.4.3 | Review through owner |
| [@isaacs/cliui](https://registry.npmjs.org/@isaacs/cliui/latest) | 8.0.2 | 9.0.0 | Review through owner |
| [@jridgewell/sourcemap-codec](https://registry.npmjs.org/@jridgewell/sourcemap-codec/latest) | 1.5.5 | 1.6.0 | Review through owner |
| [@juggle/resize-observer](https://registry.npmjs.org/@juggle/resize-observer/latest) | 3.4.0 | 3.4.0 | Current |
| [@one-ini/wasm](https://registry.npmjs.org/@one-ini/wasm/latest) | 0.1.1 | 0.2.3 | Review through owner |
| [@pkgjs/parseargs](https://registry.npmjs.org/@pkgjs/parseargs/latest) | 0.11.0 | 0.11.0 | Current |
| [@rollup/rollup-linux-arm64-gnu](https://registry.npmjs.org/@rollup/rollup-linux-arm64-gnu/latest) | 4.41.1 | 4.67.5 | Review through owner |
| [@rollup/rollup-linux-arm64-musl](https://registry.npmjs.org/@rollup/rollup-linux-arm64-musl/latest) | 4.41.1 | 4.67.5 | Review through owner |
| [@standard-schema/spec](https://registry.npmjs.org/@standard-schema/spec/latest) | 1.1.0 | 1.1.0 | Current |
| [@types/chai](https://registry.npmjs.org/@types/chai/latest) | 5.2.3 | 5.2.3 | Current |
| [@types/deep-eql](https://registry.npmjs.org/@types/deep-eql/latest) | 4.0.2 | 4.0.2 | Current |
| [@types/estree](https://registry.npmjs.org/@types/estree/latest) | 1.0.7 | 1.0.10 | Review through owner |
| [@types/json-schema](https://registry.npmjs.org/@types/json-schema/latest) | 7.0.15 | 7.0.15 | Current |
| [@types/katex](https://registry.npmjs.org/@types/katex/latest) | 0.16.7 | 0.16.8 | Review through owner |
| [@types/lodash](https://registry.npmjs.org/@types/lodash/latest) | 4.17.19 | 4.17.27 | Review through owner |
| [@types/lodash-es](https://registry.npmjs.org/@types/lodash-es/latest) | 4.17.12 | 4.17.12 | Current |
| [@types/node](https://registry.npmjs.org/@types/node/latest) | 25.8.0 | 26.6.6 | Review through owner |
| [@typescript-eslint/eslint-plugin](https://registry.npmjs.org/@typescript-eslint/eslint-plugin/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/parser](https://registry.npmjs.org/@typescript-eslint/parser/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/project-service](https://registry.npmjs.org/@typescript-eslint/project-service/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/scope-manager](https://registry.npmjs.org/@typescript-eslint/scope-manager/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/tsconfig-utils](https://registry.npmjs.org/@typescript-eslint/tsconfig-utils/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/type-utils](https://registry.npmjs.org/@typescript-eslint/type-utils/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/types](https://registry.npmjs.org/@typescript-eslint/types/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/typescript-estree](https://registry.npmjs.org/@typescript-eslint/typescript-estree/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/utils](https://registry.npmjs.org/@typescript-eslint/utils/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@typescript-eslint/visitor-keys](https://registry.npmjs.org/@typescript-eslint/visitor-keys/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [@vicons/ionicons5](https://registry.npmjs.org/@vicons/ionicons5/latest) | 0.13.0 | 0.13.0 | Current |
| [@vitejs/plugin-vue](https://registry.npmjs.org/@vitejs/plugin-vue/latest) | 5.2.4 | 6.0.10 | Review through owner |
| [@vitest/expect](https://registry.npmjs.org/@vitest/expect/latest) | 4.1.6 | 5.1.0 | Review through owner |
| [@vitest/mocker](https://registry.npmjs.org/@vitest/mocker/latest) | 4.1.6 | 5.1.0 | Review through owner |
| [@vitest/pretty-format](https://registry.npmjs.org/@vitest/pretty-format/latest) | 4.1.6 | 5.1.0 | Review through owner |
| [@vitest/runner](https://registry.npmjs.org/@vitest/runner/latest) | 4.1.6 | 4.1.11 | Review through owner |
| [@vitest/snapshot](https://registry.npmjs.org/@vitest/snapshot/latest) | 4.1.6 | 5.1.0 | Review through owner |
| [@vitest/spy](https://registry.npmjs.org/@vitest/spy/latest) | 4.1.6 | 5.1.0 | Review through owner |
| [@vitest/utils](https://registry.npmjs.org/@vitest/utils/latest) | 4.1.6 | 5.1.0 | Review through owner |
| [@volar/language-core](https://registry.npmjs.org/@volar/language-core/latest) | 2.4.28 | 2.4.30 | Review through owner |
| [@volar/source-map](https://registry.npmjs.org/@volar/source-map/latest) | 2.4.28 | 2.4.30 | Review through owner |
| [@volar/typescript](https://registry.npmjs.org/@volar/typescript/latest) | 2.4.28 | 2.4.30 | Review through owner |
| [@vue/compiler-core](https://registry.npmjs.org/@vue/compiler-core/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/compiler-dom](https://registry.npmjs.org/@vue/compiler-dom/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/compiler-sfc](https://registry.npmjs.org/@vue/compiler-sfc/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/compiler-ssr](https://registry.npmjs.org/@vue/compiler-ssr/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/devtools-api](https://registry.npmjs.org/@vue/devtools-api/latest) | 6.6.4, 7.7.6 | 8.2.1 | Review through owner |
| [@vue/devtools-kit](https://registry.npmjs.org/@vue/devtools-kit/latest) | 7.7.6 | 8.2.1 | Review through owner |
| [@vue/devtools-shared](https://registry.npmjs.org/@vue/devtools-shared/latest) | 7.7.6 | 8.2.1 | Review through owner |
| [@vue/language-core](https://registry.npmjs.org/@vue/language-core/latest) | 3.2.9 | 3.3.14 | Review through owner |
| [@vue/reactivity](https://registry.npmjs.org/@vue/reactivity/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/runtime-core](https://registry.npmjs.org/@vue/runtime-core/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/runtime-dom](https://registry.npmjs.org/@vue/runtime-dom/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/server-renderer](https://registry.npmjs.org/@vue/server-renderer/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/shared](https://registry.npmjs.org/@vue/shared/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [@vue/test-utils](https://registry.npmjs.org/@vue/test-utils/latest) | 2.4.10 | 2.5.1 | Review through owner |
| [abbrev](https://registry.npmjs.org/abbrev/latest) | 2.0.0 | 5.0.0 | Review through owner |
| [acorn](https://registry.npmjs.org/acorn/latest) | 8.15.0 | 8.19.0 | Review through owner |
| [acorn-jsx](https://registry.npmjs.org/acorn-jsx/latest) | 5.3.2 | 5.3.2 | Current |
| [ajv](https://registry.npmjs.org/ajv/latest) | 6.12.6 | 8.20.0 | Review through owner |
| [alien-signals](https://registry.npmjs.org/alien-signals/latest) | 3.2.1 | 3.2.1 | Current |
| [ansi-regex](https://registry.npmjs.org/ansi-regex/latest) | 5.0.1, 6.2.2 | 6.5.0 | Review through owner |
| [ansi-styles](https://registry.npmjs.org/ansi-styles/latest) | 4.3.0, 6.2.3 | 7.0.0 | Review through owner |
| [argparse](https://registry.npmjs.org/argparse/latest) | 2.0.1 | 3.0.4 | Review through owner |
| [assertion-error](https://registry.npmjs.org/assertion-error/latest) | 2.0.1 | 2.0.1 | Current |
| [async-validator](https://registry.npmjs.org/async-validator/latest) | 4.2.5 | 4.2.5 | Current |
| [balanced-match](https://registry.npmjs.org/balanced-match/latest) | 1.0.2, 4.0.4 | 5.0.0 | Review through owner |
| [bidi-js](https://registry.npmjs.org/bidi-js/latest) | 1.0.3 | 1.1.0 | Review through owner |
| [birpc](https://registry.npmjs.org/birpc/latest) | 2.3.0 | 4.2.0 | Review through owner |
| [boolbase](https://registry.npmjs.org/boolbase/latest) | 1.0.0 | 2.0.0 | Review through owner |
| [brace-expansion](https://registry.npmjs.org/brace-expansion/latest) | 1.1.12, 2.1.0, 5.0.6 | 5.0.12 | Review through owner |
| [callsites](https://registry.npmjs.org/callsites/latest) | 3.1.0 | 4.2.0 | Review through owner |
| [chai](https://registry.npmjs.org/chai/latest) | 6.2.2 | 6.3.0 | Review through owner |
| [chalk](https://registry.npmjs.org/chalk/latest) | 4.1.2 | 6.0.1 | Review through owner |
| [color-convert](https://registry.npmjs.org/color-convert/latest) | 2.0.1 | 3.1.3 | Review through owner |
| [color-name](https://registry.npmjs.org/color-name/latest) | 1.1.4 | 2.1.1 | Review through owner |
| [commander](https://registry.npmjs.org/commander/latest) | 10.0.1 | 15.0.0 | Review through owner |
| [concat-map](https://registry.npmjs.org/concat-map/latest) | 0.0.1 | 0.0.2 | Review through owner |
| [config-chain](https://registry.npmjs.org/config-chain/latest) | 1.1.13 | 1.1.13 | Current |
| [convert-source-map](https://registry.npmjs.org/convert-source-map/latest) | 2.0.0 | 2.0.0 | Current |
| [copy-anything](https://registry.npmjs.org/copy-anything/latest) | 3.0.5 | 4.1.5 | Review through owner |
| [cross-spawn](https://registry.npmjs.org/cross-spawn/latest) | 7.0.6 | 7.0.6 | Current |
| [css-render](https://registry.npmjs.org/css-render/latest) | 0.15.14 | 0.15.14 | Current |
| [css-tree](https://registry.npmjs.org/css-tree/latest) | 3.2.1 | 3.2.1 | Current |
| [cssesc](https://registry.npmjs.org/cssesc/latest) | 3.0.0 | 3.0.0 | Current |
| [csstype](https://registry.npmjs.org/csstype/latest) | 3.0.11, 3.1.3 | 3.2.3 | Review through owner |
| [data-urls](https://registry.npmjs.org/data-urls/latest) | 7.0.0 | 8.0.0 | Review through owner |
| [date-fns](https://registry.npmjs.org/date-fns/latest) | 3.6.0 | 4.4.0 | Review through owner |
| [date-fns-tz](https://registry.npmjs.org/date-fns-tz/latest) | 3.2.0 | 3.2.0 | Current |
| [debug](https://registry.npmjs.org/debug/latest) | 4.4.3 | 4.4.3 | Current |
| [decimal.js](https://registry.npmjs.org/decimal.js/latest) | 10.6.0 | 10.6.0 | Current |
| [deep-is](https://registry.npmjs.org/deep-is/latest) | 0.1.4 | 0.1.4 | Current |
| [eastasianwidth](https://registry.npmjs.org/eastasianwidth/latest) | 0.2.0 | 0.3.0 | Review through owner |
| [editorconfig](https://registry.npmjs.org/editorconfig/latest) | 1.0.7 | 3.0.2 | Review through owner |
| [emoji-regex](https://registry.npmjs.org/emoji-regex/latest) | 8.0.0, 9.2.2 | 11.0.0 | Review through owner |
| [entities](https://registry.npmjs.org/entities/latest) | 4.5.0, 8.0.0 | 9.0.0 | Review through owner |
| [es-module-lexer](https://registry.npmjs.org/es-module-lexer/latest) | 2.1.0 | 3.0.4 | Review through owner |
| [esbuild](https://registry.npmjs.org/esbuild/latest) | 0.25.5 | 0.28.2 | Review through owner |
| [escape-string-regexp](https://registry.npmjs.org/escape-string-regexp/latest) | 4.0.0 | 5.0.0 | Review through owner |
| [eslint](https://registry.npmjs.org/eslint/latest) | 9.29.0 | 10.14.0 | Review through owner |
| [eslint-config-prettier](https://registry.npmjs.org/eslint-config-prettier/latest) | 10.1.8 | 10.1.8 | Current |
| [eslint-plugin-vue](https://registry.npmjs.org/eslint-plugin-vue/latest) | 10.2.0 | 10.12.0 | Review through owner |
| [eslint-scope](https://registry.npmjs.org/eslint-scope/latest) | 8.4.0 | 9.1.2 | Review through owner |
| [eslint-visitor-keys](https://registry.npmjs.org/eslint-visitor-keys/latest) | 3.4.3, 4.2.1, 5.0.1 | 5.0.1 | Review through owner |
| [espree](https://registry.npmjs.org/espree/latest) | 10.4.0 | 11.2.0 | Review through owner |
| [esquery](https://registry.npmjs.org/esquery/latest) | 1.6.0 | 1.7.0 | Review through owner |
| [esrecurse](https://registry.npmjs.org/esrecurse/latest) | 4.3.0 | 4.3.0 | Current |
| [estraverse](https://registry.npmjs.org/estraverse/latest) | 5.3.0 | 5.3.0 | Current |
| [estree-walker](https://registry.npmjs.org/estree-walker/latest) | 2.0.2, 3.0.3 | 3.0.3 | Review through owner |
| [esutils](https://registry.npmjs.org/esutils/latest) | 2.0.3 | 2.0.3 | Current |
| [evtd](https://registry.npmjs.org/evtd/latest) | 0.2.4 | 0.2.4 | Current |
| [expect-type](https://registry.npmjs.org/expect-type/latest) | 1.3.0 | 1.4.0 | Review through owner |
| [fancy-canvas](https://registry.npmjs.org/fancy-canvas/latest) | 2.1.0 | 2.1.0 | Current |
| [fast-deep-equal](https://registry.npmjs.org/fast-deep-equal/latest) | 3.1.3 | 3.1.3 | Current |
| [fast-json-stable-stringify](https://registry.npmjs.org/fast-json-stable-stringify/latest) | 2.1.0 | 2.1.0 | Current |
| [fast-levenshtein](https://registry.npmjs.org/fast-levenshtein/latest) | 2.0.6 | 3.0.0 | Review through owner |
| [fdir](https://registry.npmjs.org/fdir/latest) | 6.5.0 | 6.5.0 | Current |
| [file-entry-cache](https://registry.npmjs.org/file-entry-cache/latest) | 8.0.0 | 11.1.5 | Review through owner |
| [find-up](https://registry.npmjs.org/find-up/latest) | 5.0.0 | 8.0.0 | Review through owner |
| [flat-cache](https://registry.npmjs.org/flat-cache/latest) | 4.0.1 | 6.1.23 | Review through owner |
| [flatted](https://registry.npmjs.org/flatted/latest) | 3.3.3 | 3.4.4 | Review through owner |
| [foreground-child](https://registry.npmjs.org/foreground-child/latest) | 3.3.1 | 4.0.3 | Review through owner |
| [glob](https://registry.npmjs.org/glob/latest) | 10.5.0 | 14.0.4 | Review through owner |
| [glob-parent](https://registry.npmjs.org/glob-parent/latest) | 6.0.2 | 6.0.2 | Current |
| [globals](https://registry.npmjs.org/globals/latest) | 14.0.0 | 17.14.0 | Review through owner |
| [has-flag](https://registry.npmjs.org/has-flag/latest) | 4.0.0 | 5.0.1 | Review through owner |
| [highlight.js](https://registry.npmjs.org/highlight.js/latest) | 11.11.1 | 11.12.0 | Review through owner |
| [hookable](https://registry.npmjs.org/hookable/latest) | 5.5.3 | 6.1.2 | Review through owner |
| [html-encoding-sniffer](https://registry.npmjs.org/html-encoding-sniffer/latest) | 6.0.0 | 7.0.0 | Review through owner |
| [ignore](https://registry.npmjs.org/ignore/latest) | 5.3.2, 7.0.5 | 7.0.14 | Review through owner |
| [import-fresh](https://registry.npmjs.org/import-fresh/latest) | 3.3.1 | 4.0.1 | Review through owner |
| [imurmurhash](https://registry.npmjs.org/imurmurhash/latest) | 0.1.4 | 0.1.4 | Current |
| [ini](https://registry.npmjs.org/ini/latest) | 1.3.8 | 7.0.0 | Review through owner |
| [is-extglob](https://registry.npmjs.org/is-extglob/latest) | 2.1.1 | 2.1.1 | Current |
| [is-fullwidth-code-point](https://registry.npmjs.org/is-fullwidth-code-point/latest) | 3.0.0 | 5.1.0 | Review through owner |
| [is-glob](https://registry.npmjs.org/is-glob/latest) | 4.0.3 | 4.0.3 | Current |
| [is-potential-custom-element-name](https://registry.npmjs.org/is-potential-custom-element-name/latest) | 1.0.1 | 1.0.1 | Current |
| [is-what](https://registry.npmjs.org/is-what/latest) | 4.1.16 | 5.5.7 | Review through owner |
| [isexe](https://registry.npmjs.org/isexe/latest) | 2.0.0 | 4.0.0 | Review through owner |
| [jackspeak](https://registry.npmjs.org/jackspeak/latest) | 3.4.3 | 4.2.3 | Review through owner |
| [js-beautify](https://registry.npmjs.org/js-beautify/latest) | 1.15.4 | 2.0.3 | Review through owner |
| [js-cookie](https://registry.npmjs.org/js-cookie/latest) | 3.0.5 | 3.0.8 | Review through owner |
| [js-yaml](https://registry.npmjs.org/js-yaml/latest) | 4.1.0 | 5.5.0 | Review through owner |
| [jsdom](https://registry.npmjs.org/jsdom/latest) | 29.1.1 | 31.0.0 | Review through owner |
| [json-buffer](https://registry.npmjs.org/json-buffer/latest) | 3.0.1 | 3.0.1 | Current |
| [json-schema-traverse](https://registry.npmjs.org/json-schema-traverse/latest) | 0.4.1 | 1.0.0 | Review through owner |
| [json-stable-stringify-without-jsonify](https://registry.npmjs.org/json-stable-stringify-without-jsonify/latest) | 1.0.1 | 1.0.1 | Current |
| [keyv](https://registry.npmjs.org/keyv/latest) | 4.5.4 | 6.1.0 | Review through owner |
| [levn](https://registry.npmjs.org/levn/latest) | 0.4.1 | 0.4.1 | Current |
| [lightweight-charts](https://registry.npmjs.org/lightweight-charts/latest) | 5.0.7 | 5.2.1 | Review through owner |
| [locate-path](https://registry.npmjs.org/locate-path/latest) | 6.0.0 | 8.0.0 | Review through owner |
| [lodash](https://registry.npmjs.org/lodash/latest) | 4.17.21 | 4.18.1 | Review through owner |
| [lodash-es](https://registry.npmjs.org/lodash-es/latest) | 4.17.21 | 4.18.1 | Review through owner |
| [lodash.merge](https://registry.npmjs.org/lodash.merge/latest) | 4.6.2 | 4.6.2 | Current |
| [lru-cache](https://registry.npmjs.org/lru-cache/latest) | 10.4.3, 11.3.6 | 11.5.3 | Review through owner |
| [magic-string](https://registry.npmjs.org/magic-string/latest) | 0.30.21 | 1.4.5 | Review through owner |
| [mdn-data](https://registry.npmjs.org/mdn-data/latest) | 2.27.1 | 2.37.2 | Review through owner |
| [minimatch](https://registry.npmjs.org/minimatch/latest) | 10.2.5, 3.1.2, 9.0.9 | 11.0.5 | Review through owner |
| [minipass](https://registry.npmjs.org/minipass/latest) | 7.1.3 | 7.1.3 | Current |
| [mitt](https://registry.npmjs.org/mitt/latest) | 3.0.1 | 3.0.1 | Current |
| [ms](https://registry.npmjs.org/ms/latest) | 2.1.3 | 2.1.3 | Current |
| [muggle-string](https://registry.npmjs.org/muggle-string/latest) | 0.4.1 | 1.0.3 | Review through owner |
| [naive-ui](https://registry.npmjs.org/naive-ui/latest) | 2.42.0 | 2.45.3 | Review through owner |
| [nanoid](https://registry.npmjs.org/nanoid/latest) | 3.3.11 | 6.0.2 | Review through owner |
| [natural-compare](https://registry.npmjs.org/natural-compare/latest) | 1.4.0 | 1.4.0 | Current |
| [nopt](https://registry.npmjs.org/nopt/latest) | 7.2.1 | 10.0.1 | Review through owner |
| [nth-check](https://registry.npmjs.org/nth-check/latest) | 2.1.1 | 3.0.1 | Review through owner |
| [obug](https://registry.npmjs.org/obug/latest) | 2.1.1 | 3.0.0 | Review through owner |
| [optionator](https://registry.npmjs.org/optionator/latest) | 0.9.4 | 0.9.4 | Current |
| [p-limit](https://registry.npmjs.org/p-limit/latest) | 3.1.0 | 7.3.3 | Review through owner |
| [p-locate](https://registry.npmjs.org/p-locate/latest) | 5.0.0 | 7.0.0 | Review through owner |
| [package-json-from-dist](https://registry.npmjs.org/package-json-from-dist/latest) | 1.0.1 | 1.0.1 | Current |
| [parent-module](https://registry.npmjs.org/parent-module/latest) | 1.0.1 | 3.2.0 | Review through owner |
| [parse5](https://registry.npmjs.org/parse5/latest) | 8.0.1 | 8.1.0 | Review through owner |
| [path-browserify](https://registry.npmjs.org/path-browserify/latest) | 1.0.1 | 1.0.1 | Current |
| [path-exists](https://registry.npmjs.org/path-exists/latest) | 4.0.0 | 5.0.0 | Review through owner |
| [path-key](https://registry.npmjs.org/path-key/latest) | 3.1.1 | 4.0.0 | Review through owner |
| [path-scurry](https://registry.npmjs.org/path-scurry/latest) | 1.11.1 | 3.0.0 | Review through owner |
| [pathe](https://registry.npmjs.org/pathe/latest) | 2.0.3 | 2.0.3 | Current |
| [perfect-debounce](https://registry.npmjs.org/perfect-debounce/latest) | 1.0.0 | 2.1.0 | Review through owner |
| [picocolors](https://registry.npmjs.org/picocolors/latest) | 1.1.1 | 1.1.1 | Current |
| [picomatch](https://registry.npmjs.org/picomatch/latest) | 4.0.4 | 4.0.7 | Review through owner |
| [pinia](https://registry.npmjs.org/pinia/latest) | 3.0.2 | 4.1.0 | Review through owner |
| [postcss](https://registry.npmjs.org/postcss/latest) | 8.5.4 | 8.5.32 | Review through owner |
| [postcss-selector-parser](https://registry.npmjs.org/postcss-selector-parser/latest) | 6.1.2 | 7.1.7 | Review through owner |
| [prelude-ls](https://registry.npmjs.org/prelude-ls/latest) | 1.2.1 | 1.2.1 | Current |
| [prettier](https://registry.npmjs.org/prettier/latest) | 3.6.2 | 3.9.10 | Review through owner |
| [proto-list](https://registry.npmjs.org/proto-list/latest) | 1.2.4 | 1.2.4 | Current |
| [punycode](https://registry.npmjs.org/punycode/latest) | 2.3.1 | 2.3.1 | Current |
| [require-from-string](https://registry.npmjs.org/require-from-string/latest) | 2.0.2 | 2.0.2 | Current |
| [resolve-from](https://registry.npmjs.org/resolve-from/latest) | 4.0.0 | 5.0.0 | Review through owner |
| [rfdc](https://registry.npmjs.org/rfdc/latest) | 1.4.1 | 1.4.1 | Current |
| [rollup](https://registry.npmjs.org/rollup/latest) | 4.41.1 | 4.67.5 | Review through owner |
| [saxes](https://registry.npmjs.org/saxes/latest) | 6.0.0 | 6.0.0 | Current |
| [seemly](https://registry.npmjs.org/seemly/latest) | 0.3.10 | 0.3.10 | Current |
| [semver](https://registry.npmjs.org/semver/latest) | 7.8.0 | 7.8.6 | Review through owner |
| [shebang-command](https://registry.npmjs.org/shebang-command/latest) | 2.0.0 | 2.0.0 | Current |
| [shebang-regex](https://registry.npmjs.org/shebang-regex/latest) | 3.0.0 | 4.0.0 | Review through owner |
| [siginfo](https://registry.npmjs.org/siginfo/latest) | 2.0.0 | 2.0.0 | Current |
| [signal-exit](https://registry.npmjs.org/signal-exit/latest) | 4.1.0 | 4.1.0 | Current |
| [source-map-js](https://registry.npmjs.org/source-map-js/latest) | 1.2.1 | 1.2.2 | Review through owner |
| [speakingurl](https://registry.npmjs.org/speakingurl/latest) | 14.0.1 | 14.0.1 | Current |
| [stackback](https://registry.npmjs.org/stackback/latest) | 0.0.2 | 0.0.2 | Current |
| [std-env](https://registry.npmjs.org/std-env/latest) | 4.1.0 | 4.3.0 | Review through owner |
| [string-width](https://registry.npmjs.org/string-width/latest) | 4.2.3, 5.1.2 | 8.3.0 | Review through owner |
| [string-width-cjs](https://registry.npmjs.org/string-width-cjs/latest) | 4.2.3 | 5.1.1 | Review through owner |
| [strip-ansi](https://registry.npmjs.org/strip-ansi/latest) | 6.0.1, 7.2.0 | 7.2.0 | Review through owner |
| [strip-ansi-cjs](https://registry.npmjs.org/strip-ansi-cjs/latest) | 6.0.1 | 8.0.0 | Review through owner |
| [strip-json-comments](https://registry.npmjs.org/strip-json-comments/latest) | 3.1.1 | 5.0.3 | Review through owner |
| [superjson](https://registry.npmjs.org/superjson/latest) | 2.2.2 | 2.2.6 | Review through owner |
| [supports-color](https://registry.npmjs.org/supports-color/latest) | 7.2.0 | 11.0.0 | Review through owner |
| [symbol-tree](https://registry.npmjs.org/symbol-tree/latest) | 3.2.4 | 3.2.4 | Current |
| [tinybench](https://registry.npmjs.org/tinybench/latest) | 2.9.0 | 6.2.3 | Review through owner |
| [tinyexec](https://registry.npmjs.org/tinyexec/latest) | 1.1.2 | 1.3.1 | Review through owner |
| [tinyglobby](https://registry.npmjs.org/tinyglobby/latest) | 0.2.16 | 0.2.17 | Review through owner |
| [tinyrainbow](https://registry.npmjs.org/tinyrainbow/latest) | 3.1.0 | 3.2.0 | Review through owner |
| [tldts](https://registry.npmjs.org/tldts/latest) | 7.0.30 | 7.4.19 | Review through owner |
| [tldts-core](https://registry.npmjs.org/tldts-core/latest) | 7.0.30 | 7.4.20 | Review through owner |
| [tough-cookie](https://registry.npmjs.org/tough-cookie/latest) | 6.0.1 | 6.0.2 | Review through owner |
| [tr46](https://registry.npmjs.org/tr46/latest) | 6.0.0 | 7.0.0 | Review through owner |
| [treemate](https://registry.npmjs.org/treemate/latest) | 0.3.11 | 0.3.11 | Current |
| [ts-api-utils](https://registry.npmjs.org/ts-api-utils/latest) | 2.5.0 | 2.5.0 | Current |
| [type-check](https://registry.npmjs.org/type-check/latest) | 0.4.0 | 0.4.0 | Current |
| [typescript](https://registry.npmjs.org/typescript/latest) | 6.0.3 | 7.0.2 | Review through owner |
| [typescript-eslint](https://registry.npmjs.org/typescript-eslint/latest) | 8.59.3 | 8.72.1 | Review through owner |
| [undici](https://registry.npmjs.org/undici/latest) | 7.25.0 | 8.12.4 | Review through owner |
| [undici-types](https://registry.npmjs.org/undici-types/latest) | 7.24.6 | 8.12.4 | Review through owner |
| [uri-js](https://registry.npmjs.org/uri-js/latest) | 4.4.1 | 4.4.1 | Current |
| [util-deprecate](https://registry.npmjs.org/util-deprecate/latest) | 1.0.2 | 1.0.2 | Current |
| [vdirs](https://registry.npmjs.org/vdirs/latest) | 0.1.8 | 0.1.8 | Current |
| [vite](https://registry.npmjs.org/vite/latest) | 6.3.5 | 8.3.6 | Review through owner |
| [vitest](https://registry.npmjs.org/vitest/latest) | 4.1.6 | 5.1.0 | Review through owner |
| [vooks](https://registry.npmjs.org/vooks/latest) | 0.2.12 | 0.2.12 | Current |
| [vscode-uri](https://registry.npmjs.org/vscode-uri/latest) | 3.1.0 | 3.2.0 | Review through owner |
| [vue](https://registry.npmjs.org/vue/latest) | 3.5.16 | 3.5.45 | Review through owner |
| [vue-component-type-helpers](https://registry.npmjs.org/vue-component-type-helpers/latest) | 3.2.9 | 3.3.14 | Review through owner |
| [vue-eslint-parser](https://registry.npmjs.org/vue-eslint-parser/latest) | 10.1.3 | 10.4.1 | Review through owner |
| [vue-router](https://registry.npmjs.org/vue-router/latest) | 4.4.5 | 5.4.0 | Review through owner |
| [vue-tsc](https://registry.npmjs.org/vue-tsc/latest) | 3.2.9 | 3.3.14 | Review through owner |
| [vueuc](https://registry.npmjs.org/vueuc/latest) | 0.4.64 | 0.4.66 | Review through owner |
| [w3c-xmlserializer](https://registry.npmjs.org/w3c-xmlserializer/latest) | 5.0.0 | 6.0.0 | Review through owner |
| [webidl-conversions](https://registry.npmjs.org/webidl-conversions/latest) | 8.0.1 | 8.0.1 | Current |
| [whatwg-mimetype](https://registry.npmjs.org/whatwg-mimetype/latest) | 5.0.0 | 5.0.0 | Current |
| [whatwg-url](https://registry.npmjs.org/whatwg-url/latest) | 16.0.1 | 17.3.0 | Review through owner |
| [which](https://registry.npmjs.org/which/latest) | 2.0.2 | 7.0.0 | Review through owner |
| [why-is-node-running](https://registry.npmjs.org/why-is-node-running/latest) | 2.3.0 | 3.2.3 | Review through owner |
| [word-wrap](https://registry.npmjs.org/word-wrap/latest) | 1.2.5 | 1.2.5 | Current |
| [wrap-ansi](https://registry.npmjs.org/wrap-ansi/latest) | 8.1.0 | 10.0.2 | Review through owner |
| [wrap-ansi-cjs](https://registry.npmjs.org/wrap-ansi-cjs/latest) | 7.0.0 | 8.0.0 | Review through owner |
| [xml-name-validator](https://registry.npmjs.org/xml-name-validator/latest) | 4.0.0, 5.0.0 | 5.0.0 | Review through owner |
| [xmlchars](https://registry.npmjs.org/xmlchars/latest) | 2.2.0 | 2.2.0 | Current |
| [yocto-queue](https://registry.npmjs.org/yocto-queue/latest) | 0.1.0 | 1.2.2 | Review through owner |
