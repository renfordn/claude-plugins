/**
 * Storage Backends Registry
 *
 * Provides factory and registry for available storage backends.
 */

const StorageBackend = require('./StorageBackend');
const MemoryBackend = require('./MemoryBackend');
const SQLiteBackend = require('./SQLiteBackend');
const FallbackBackend = require('./FallbackBackend');

let RedisBackend;
try {
  RedisBackend = require('./RedisBackend');
} catch (err) {
  // Redis backend optional - requires 'redis' package
}

const backends = {
  memory: MemoryBackend,
  sqlite: SQLiteBackend,
  fallback: FallbackBackend
};

if (RedisBackend) {
  backends.redis = RedisBackend;
}

/**
 * Create a backend instance
 * @param {string} type - Backend type ('memory', 'sqlite', etc)
 * @param {Object} config - Backend configuration
 * @returns {StorageBackend} Backend instance
 */
function createBackend(type = 'memory', config = {}) {
  const BackendClass = backends[type];
  if (!BackendClass) {
    throw new Error(`Unknown backend type: ${type}. Available: ${Object.keys(backends).join(', ')}`);
  }
  return new BackendClass(config);
}

/**
 * Register a custom backend
 * @param {string} name - Backend name
 * @param {class} BackendClass - Backend class (should extend StorageBackend)
 */
function registerBackend(name, BackendClass) {
  if (!(BackendClass.prototype instanceof StorageBackend)) {
    throw new Error('Backend must extend StorageBackend');
  }
  backends[name] = BackendClass;
}

/**
 * List available backends
 * @returns {Array<string>} Available backend names
 */
function listBackends() {
  return Object.keys(backends);
}

module.exports = {
  createBackend,
  registerBackend,
  listBackends,
  StorageBackend,
  MemoryBackend,
  SQLiteBackend,
  FallbackBackend,
  ...(RedisBackend && { RedisBackend })
};
