'use strict';
/**
 * Hook: post-agent-completion (PostToolUse)
 *
 * stdin  → { toolName, input, output, sessionId, metadata? }
 * stdout → { hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext? } }
 * exit   → always 0
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { readStdinJSON } = require('./_stdin-reader');
const { sanitizeDeep } = require('../utils/sanitize-deep');

const CACHE_MD_MAX_BYTES = 500 * 1024; // 500 KB

function resolveDataDir() {
  const d = process.env.CLAUDE_PLUGIN_DATA;
  if (!d) {
    throw new Error('[agent-cache-plugin] CLAUDE_PLUGIN_DATA is not set. Run this through Claude Code, or set CLAUDE_PLUGIN_DATA to this plugin\'s data directory.');
  }
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function sha256(str) {
  return crypto.createHash('sha256').update(str).digest('hex');
}

function cacheKey(agentType, taskSlug, inputDigest) {
  return sha256(agentType + '\x00' + taskSlug + '\x00' + inputDigest);
}

function writePostToolUse(additionalContext) {
  const hookSpecificOutput = { hookEventName: 'PostToolUse' };
  if (additionalContext) hookSpecificOutput.additionalContext = additionalContext;
  process.stdout.write(JSON.stringify({ hookSpecificOutput }) + '\n');
}

function determineCacheability(output, parameters) {
  if (parameters && parameters.noCache === true) return false;
  try {
    const s = JSON.stringify(output).toLowerCase();
    if (['current time', 'now', 'today', 'live data', 'real-time'].some(p => s.includes(p))) return false;
  } catch { /* ignore */ }
  if (parameters && (parameters.isRandomized || parameters.isUserSpecific)) return false;
  return true;
}

function serializeOutput(output) {
  if (typeof output === 'string') return output;
  try { return JSON.stringify(output); } catch { return String(output); }
}

function buildTags(agentType, parameters) {
  const tags = [agentType];
  if (parameters && parameters.taskType) tags.push(parameters.taskType);
  if (parameters && parameters.domain) tags.push(parameters.domain);
  if (parameters && parameters.complexity) tags.push(`complexity-${parameters.complexity}`);
  return tags.filter(Boolean);
}

function appendCachemd(mdPath, block) {
  try {
    // Rotate if over size limit
    if (fs.existsSync(mdPath)) {
      const stat = fs.statSync(mdPath);
      if (stat.size >= CACHE_MD_MAX_BYTES) {
        fs.renameSync(mdPath, mdPath + '.bak');
      }
    }
    fs.appendFileSync(mdPath, block + '\n');
  } catch (err) {
    process.stderr.write('[agent-cache-plugin] CACHE.md write error: ' + err.message + '\n');
  }
}

async function main() {
  let input;
  try {
    input = await readStdinJSON();
  } catch {
    writePostToolUse();
    process.exit(0);
  }

  // Validate required fields
  if (!input.toolName || typeof input.toolName !== 'string' || !input.toolName.trim()) {
    writePostToolUse(); process.exit(0);
  }
  if (!input.sessionId || typeof input.sessionId !== 'string' || !input.sessionId.trim()) {
    writePostToolUse(); process.exit(0);
  }
  if (!input.output || typeof input.output !== 'object') {
    writePostToolUse(); process.exit(0);
  }
  if (!input.input || typeof input.input !== 'object') {
    writePostToolUse(); process.exit(0);
  }

  const metadata = input.metadata || {};
  const parameters = metadata.parameters || {};
  if (!determineCacheability(input.output, parameters)) {
    writePostToolUse(); process.exit(0);
  }

  try {
    const dataDir = resolveDataDir();
    const dbPath = path.join(dataDir, 'cache.db');
    const mdPath = path.join(dataDir, 'CACHE.md');

    const { getSingleton, resetSingleton } = require('../skills/sqlite-cache');
    // Use a per-path singleton; in tests CLAUDE_PLUGIN_DATA changes each run
    resetSingleton();
    const db = getSingleton(dbPath);

    const taskSlug = metadata.taskSlug || 'unknown';
    const inputDigest = sha256(JSON.stringify(input.input));
    const key = cacheKey(input.toolName, taskSlug, inputDigest);

    const cleanOutput = sanitizeDeep(input.output);
    const outputBlob = serializeOutput(cleanOutput);
    const outputDigest = sha256(outputBlob);
    const tokenCount = (metadata.inputTokens || 0) + (metadata.outputTokens || 0);

    const cleanDecisions = typeof cleanOutput.decisions === 'string'
      ? cleanOutput.decisions
      : (Array.isArray(cleanOutput.decisions) ? cleanOutput.decisions.join(' ') : '');
    const cleanWarnings = typeof cleanOutput.warnings === 'string'
      ? cleanOutput.warnings
      : 'none';

    db.store({
      key,
      agent_type: input.toolName,
      task_slug: taskSlug,
      output_digest: outputDigest,
      output_blob: outputBlob,
      decisions: cleanDecisions || null,
      warnings: cleanWarnings,
      token_count: tokenCount,
      ttl: (72 * 60 * 60 * 1000)
    });

    // Append CACHE.md block
    const iso = new Date().toISOString();
    const block = [
      `## [${iso}] ${input.toolName} / ${taskSlug}`,
      `Key: ${key.slice(0, 12)}`,
      `Tokens: ${tokenCount}`,
      `Decisions: ${cleanDecisions || 'none'}`,
      `Warnings: ${cleanWarnings}`,
      `Digest: ${outputDigest.slice(0, 12)}`
    ].join('\n');
    appendCachemd(mdPath, block);

    writePostToolUse(`cache: stored (tokensSaved=${tokenCount}, cacheKey=${key.slice(0, 12)})`);
  } catch (err) {
    process.stderr.write('[agent-cache-plugin] post-agent-completion error: ' + err.message + '\n');
    writePostToolUse();
  }

  process.exit(0);
}

main();
