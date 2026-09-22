'use strict';
const fs = require('fs');
const { TEST_DATA_ROOT, TEST_DATA_DIR } = require('./test-data-root');

module.exports = () => {
  fs.rmSync(TEST_DATA_ROOT, { recursive: true, force: true });
  fs.mkdirSync(TEST_DATA_DIR, { recursive: true });
  // Set here, in the main Jest process, so forked workers inherit it -- and, crucially, so do
  // the child processes tests spawn (hooks, scripts/cache-command.js). Jest gives each test
  // environment its own copy of process.env, so a value set in setupFiles reaches the test
  // module but NOT a spawn()ed child, which inherits the worker's real env instead.
  process.env.CLAUDE_PLUGIN_DATA = TEST_DATA_DIR;
};
