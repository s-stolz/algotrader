import vue from 'eslint-plugin-vue';
import tseslint from 'typescript-eslint';
import vueParser from 'vue-eslint-parser';

const unusedVarsOptions = {
  vars: 'all',
  args: 'after-used',
  argsIgnorePattern: '^_',
  varsIgnorePattern: '^_',
  caughtErrors: 'all',
  caughtErrorsIgnorePattern: '^_',
  destructuredArrayIgnorePattern: '^_',
  ignoreRestSiblings: true,
};

const sharedRules = {
  'no-unused-vars': 'off',
  '@typescript-eslint/no-unused-vars': ['error', unusedVarsOptions],
  'no-unreachable': 'error',
  'no-unused-expressions': ['error', {
    allowShortCircuit: false,
    allowTernary: false,
    allowTaggedTemplates: false,
  }],
  semi: ['error', 'always'],
  'max-lines': ['warn', {
    max: 500,
    skipBlankLines: true,
    skipComments: true,
  }],
  'no-trailing-spaces': 'error',
  'no-multiple-empty-lines': ['error', {
    max: 2,
    maxEOF: 1,
    maxBOF: 0,
  }],
  'comma-dangle': ['error', 'always-multiline'],
};

const vueRules = {
  'vue/order-in-components': ['error', {
    order: [
      'name',
      'components',
      'directives',
      'mixins',
      'extends',
      'provide',
      'inject',
      'props',
      'emits',
      'setup',
      'data',
      'computed',
      'watch',
      'LIFECYCLE_HOOKS',
      'methods',
      'expose',
      'template',
      'render',
      'renderError',
    ],
  }],
  'vue/no-unused-components': 'error',
  'vue/no-unused-vars': 'error',
  'vue/no-unused-properties': ['error', {
    groups: ['props', 'data', 'computed', 'methods', 'setup'],
  }],
  'vue/no-empty-component-block': 'error',
  'vue/multi-word-component-names': 'off',
  'vue/custom-event-name-casing': ['error', 'kebab-case'],
  'vue/html-closing-bracket-newline': ['error', {
    singleline: 'never',
    multiline: 'always',
  }],
  'vue/max-attributes-per-line': ['error', {
    singleline: {
      max: 99,
    },
    multiline: {
      max: 1,
    },
  }],
  'vue/first-attribute-linebreak': ['error', {
    singleline: 'ignore',
    multiline: 'below',
  }],
};

export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'coverage/**'],
  },
  {
    files: ['**/*.{js,ts}'],
    languageOptions: {
      parser: tseslint.parser,
      ecmaVersion: 'latest',
      sourceType: 'module',
    },
    plugins: {
      '@typescript-eslint': tseslint.plugin,
    },
    rules: sharedRules,
  },
  {
    files: ['**/*.vue'],
    languageOptions: {
      parser: vueParser,
      parserOptions: {
        parser: tseslint.parser,
        ecmaVersion: 'latest',
        sourceType: 'module',
        extraFileExtensions: ['.vue'],
      },
    },
    plugins: {
      vue,
      '@typescript-eslint': tseslint.plugin,
    },
    rules: {
      ...sharedRules,
      ...vueRules,
    },
  },
];
