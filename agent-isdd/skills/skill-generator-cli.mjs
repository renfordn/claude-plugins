#!/usr/bin/env node

/**
 * Skill Generator CLI
 * Integrated entry point for plan + execute workflow
 *
 * Usage:
 *   skill-generator-cli plan [<dir>] [--output <file>]
 *   skill-generator-cli execute [<dir>] [--plan <file>] [--output-dir <dir>]
 *   skill-generator-cli auto [<dir>] [--output-dir <dir>]  (plan + execute combined)
 */

import path from 'path';
import { fileURLToPath } from 'url';
import discover from './plan-skill-generator/discovery.mjs';
import execute from './run-skill-generator-execute/executor.mjs';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Parse command-line arguments
 */
function parseArgs(args) {
  const result = {
    command: 'auto',
    projectDir: '.',
    options: {},
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (['plan', 'execute', 'auto'].includes(arg)) {
      result.command = arg;
    } else if (arg === '--output') {
      result.options.output = args[++i];
    } else if (arg === '--output-dir') {
      result.options.outputDir = args[++i];
    } else if (arg === '--plan') {
      result.options.planFile = args[++i];
    } else if (arg === '--no-verify') {
      result.options.noVerify = true;
    } else if (!arg.startsWith('--')) {
      result.projectDir = arg;
    }
  }

  return result;
}

/**
 * Run the plan phase
 */
async function runPlan(projectDir, options) {
  console.log(`[1/2] Discovering project structure in ${projectDir}...`);

  try {
    const plan = discover(projectDir);

    // Output plan
    if (options.output) {
      fs.writeFileSync(options.output, JSON.stringify(plan, null, 2), 'utf8');
      console.log(`✓ Plan written to ${options.output}`);
    } else {
      console.log(`✓ Plan generated (confidence: ${plan.confidence_level})`);
      console.log(JSON.stringify(plan, null, 2));
    }

    return plan;
  } catch (error) {
    console.error('✗ Discovery failed:', error.message);
    process.exit(1);
  }
}

/**
 * Run the execute phase
 */
async function runExecute(projectDir, options) {
  console.log(`[2/2] Building skill for ${projectDir}...`);

  try {
    const result = execute({
      projectDir,
      planFile: options.planFile,
      outputDir: options.outputDir,
      noVerify: options.noVerify,
    });

    console.log(`✓ ${result.message}`);
    return result;
  } catch (error) {
    console.error('✗ Execution failed:', error.message);
    process.exit(1);
  }
}

/**
 * Run plan + execute (auto mode)
 */
async function runAuto(projectDir, options) {
  console.log('Skill Generator: Auto Mode');
  console.log('==========================\n');

  // Phase 1: Plan
  const plan = await runPlan(projectDir, {});

  // Phase 2: Execute with the plan
  console.log('\n');

  // Save plan to temp file for execute to use
  const tempPlanFile = `/tmp/skill-generator-plan-${Date.now()}.json`;
  fs.writeFileSync(tempPlanFile, JSON.stringify(plan, null, 2), 'utf8');

  try {
    const result = await runExecute(projectDir, {
      ...options,
      planFile: tempPlanFile,
    });

    console.log('\n✓ Skill generation complete!');
    console.log(`  Location: ${result.skillPath}`);
    console.log(`  SKILL.md: ${result.skillMdPath}`);

    return result;
  } finally {
    // Clean up temp file
    try {
      fs.unlinkSync(tempPlanFile);
    } catch {
      // Ignore
    }
  }
}

/**
 * Main CLI handler
 */
async function main() {
  const args = process.argv.slice(2);

  if (args.length === 0 || args[0] === 'help' || args[0] === '--help' || args[0] === '-h') {
    console.log(`
Skill Generator CLI
===================

Commands:
  plan [<dir>] [--output <file>]
    Fast project discovery. Outputs JSON plan.
    --output: Write plan to file (default: stdout)

  execute [<dir>] [--plan <file>] [--output-dir <dir>]
    Build SKILL.md + driver. Optionally uses a pre-computed plan.
    --plan: Use existing plan (skips discovery, faster)
    --output-dir: Where to write skill (default: ./.claude/skills/)

  auto [<dir>] [--output-dir <dir>]
    Run plan + execute in sequence. Recommended default.
    Combines discovery and build into one command.

Examples:
  # Discover a project
  skill-generator-cli plan /path/to/project --output plan.json

  # Build skill with plan (50% faster)
  skill-generator-cli execute /path/to/project --plan plan.json

  # Full workflow (plan + execute)
  skill-generator-cli auto /path/to/project

Options:
  --help, -h          Show this help
    `);
    process.exit(0);
  }

  const { command, projectDir, options } = parseArgs(args);

  try {
    switch (command) {
      case 'plan':
        await runPlan(projectDir, options);
        break;

      case 'execute':
        await runExecute(projectDir, options);
        break;

      case 'auto':
        await runAuto(projectDir, options);
        break;

      default:
        console.error(`Unknown command: ${command}`);
        process.exit(1);
    }
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

// Run CLI
if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

export { runPlan, runExecute, runAuto };
