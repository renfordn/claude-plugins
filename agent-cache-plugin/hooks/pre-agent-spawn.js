'use strict';
/**
 * Hook: pre-agent-spawn (PreToolUse) — M1 conditional
 *
 * Registered in hooks/hooks.json (PreToolUse, matcher "Agent") -- plugin.json carries no
 * hooks key; Claude Code discovers hooks/hooks.json directly, and tests/hook-wiring.test.js
 * asserts this hook is wired there. An earlier note here claimed the hook was deliberately
 * left unregistered pending a PreToolUse schema-validation bug; that is no longer true.
 *
 * stdin  → { toolName, input, metadata? }
 * stdout → { permissionDecision: 'allow', tempFilePath? }
 * exit   → always 0
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { readStdinJSON } = require('./_stdin-reader');

function sha256(s) {
  return crypto.createHash('sha256').update(s).digest('hex');
}

function cacheKey(agentType, taskSlug, inputDigest) {
  return sha256(agentType + '\x00' + taskSlug + '\x00' + inputDigest);
}

function passthrough() {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'allow' }
  }) + '\n');
}

function resolveDbPath() {
  const d = process.env.CLAUDE_PLUGIN_DATA;
  if (!d) {
    throw new Error('[agent-cache-plugin] CLAUDE_PLUGIN_DATA is not set. Run this through Claude Code, or set CLAUDE_PLUGIN_DATA to this plugin\'s data directory.');
  }
  fs.mkdirSync(d, { recursive: true });
  return path.join(d, 'cache.db');
}

async function main() {
  let input;
  try {
    input = await readStdinJSON();
  } catch {
    passthrough(); process.exit(0);
  }

  try {
    const dbPath = resolveDbPath();
    const { CacheManager } = require('../skills/sqlite-cache');
    const db = new CacheManager(dbPath);

    const agentType = input.toolName || '';
    const taskSlug = (input.metadata && input.metadata.taskSlug) || 'unknown';
    const inputDigest = sha256(JSON.stringify(input.input || {}));
    const key = cacheKey(agentType, taskSlug, inputDigest);

    const row = db.retrieve(key);
    db.close();

    if (!row) {
      passthrough(); process.exit(0);
    }

    // Write cached output to a temp file
    const tmpFile = path.join(os.tmpdir(), `cache-hit-${key.slice(0, 12)}-${Date.now()}.json`);
    fs.writeFileSync(tmpFile, row.output_blob, 'utf8');

    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'allow',
        permissionDecisionReason: `cache-hit: ${tmpFile}`
      }
    }) + '\n');
  } catch (err) {
    process.stderr.write('[agent-cache-plugin] pre-agent-spawn error: ' + err.message + '\n');
    passthrough();
  }

  process.exit(0);
}

main();
