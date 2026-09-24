'use strict';
/**
 * Defence in depth for the data-dir isolation setup-env.js establishes.
 *
 * Individual suites legitimately mutate CLAUDE_PLUGIN_DATA (pointing it at their own temp dir)
 * and some used to `delete` it afterwards, which would make every later getSingleton() in that
 * worker throw (CLAUDE_PLUGIN_DATA is required). Re-pinning it before and after each test means a suite can still point it
 * wherever it likes for its own duration without leaking that change to its neighbours.
 */
const { resetSingleton } = require('../../skills/sqlite-cache');

const { TEST_DATA_DIR } = require('./test-data-root');

const WORKER_DATA_DIR = TEST_DATA_DIR;

function repin() {
  if (process.env.CLAUDE_PLUGIN_DATA !== WORKER_DATA_DIR) {
    process.env.CLAUDE_PLUGIN_DATA = WORKER_DATA_DIR;
    // The singleton caches its resolved path; drop it so the next getSingleton() re-resolves.
    try { resetSingleton(); } catch { /* not every suite loads the module */ }
  }
}

beforeEach(repin);
afterEach(repin);
