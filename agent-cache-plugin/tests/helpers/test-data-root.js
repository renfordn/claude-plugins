'use strict';
/**
 * The one throwaway directory every test run uses instead of the real plugin data dir.
 * Computed identically (not passed through env) so globalSetup, globalTeardown and each
 * worker's setup file agree without relying on env propagation across Jest processes.
 */
const os = require('os');
const path = require('path');

const TEST_DATA_ROOT = path.join(os.tmpdir(), 'agent-cache-plugin-jest');
const TEST_DATA_DIR = path.join(TEST_DATA_ROOT, 'data');

module.exports = { TEST_DATA_ROOT, TEST_DATA_DIR };
