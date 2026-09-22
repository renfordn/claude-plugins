'use strict';
/**
 * Runs in every worker before the test framework loads, so any module that resolves the data
 * dir at require time sees the throwaway path. global-setup.js already put the same value in
 * the worker's real env (which is what spawn()ed children inherit); this pins the per-test
 * environment copy that test modules themselves read.
 */
const fs = require('fs');
const { TEST_DATA_DIR } = require('./test-data-root');

fs.mkdirSync(TEST_DATA_DIR, { recursive: true });
process.env.CLAUDE_PLUGIN_DATA = TEST_DATA_DIR;
