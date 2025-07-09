import vue from 'eslint-plugin-vue'
import parser from 'vue-eslint-parser'

export default [
  {
    ignores: ['dist/**', 'node_modules/**'],
    files: ['**/*.js', '**/*.vue'],
    languageOptions: {
      parser,
      ecmaVersion: 'latest',
      sourceType: 'module'
    },
    plugins: {
      vue
    },
    rules: {
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
          'renderError'
        ]
      }],

      'vue/no-unused-components': 'error',
      'vue/no-unused-vars': 'error',
      'vue/no-unused-properties': ['error', {
        'groups': ['props', 'data', 'computed', 'methods', 'setup']
      }],
      'vue/no-empty-component-block': 'error',
      'vue/multi-word-component-names': 'off',
      'no-unused-vars': ['error', {
        'vars': 'all',
        'args': 'after-used',
        'argsIgnorePattern': '^_',
        'varsIgnorePattern': '^_',
        'caughtErrors': 'all',
        'caughtErrorsIgnorePattern': '^_',
        'destructuredArrayIgnorePattern': '^_',
        'ignoreRestSiblings': true
      }],
      'no-unreachable': 'error',
      'no-unused-expressions': ['error', {
        'allowShortCircuit': false,
        'allowTernary': false,
        'allowTaggedTemplates': false
      }],
      'semi': ['error', 'always'],
      'max-lines': ['warn', {
        'max': 200,
        'skipBlankLines': true,
        'skipComments': true
      }]
    }
  },
]
