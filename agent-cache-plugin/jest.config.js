'use strict';
/**
 * Jest config.
 *
 * The important part is the env isolation: several suites exercise code paths that call
 * sqlite-cache's getSingleton() / the hooks' resolveDataDir() with no explicit path, which
 * uses CLAUDE_PLUGIN_DATA (and throws when it's unset -- there is no guessed fallback).
 * setup-env.js forces CLAUDE_PLUGIN_DATA to a throwaway per-worker directory
 * before any test module loads, so no test can reach the real one.
 */
module.exports = {
  testEnvironment: 'node',
  testMatch: ['**/tests/**/*.test.js'],
  globalSetup: '<rootDir>/tests/helpers/global-setup.js',
  globalTeardown: '<rootDir>/tests/helpers/global-teardown.js',
  setupFiles: ['<rootDir>/tests/helpers/setup-env.js'],
  setupFilesAfterEnv: ['<rootDir>/tests/helpers/setup-after-env.js']
};
