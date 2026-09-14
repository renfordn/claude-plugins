#!/usr/bin/env node

/**
 * CLI Entry Point: cache-command.js
 *
 * Routes cache-related commands to appropriate handlers.
 * Used by Claude Code's command system to dispatch /cache-status, /cache-clear, /cache-config.
 *
 * Usage:
 *   node scripts/cache-command.js status [--detailed] [--export FORMAT]
 *   node scripts/cache-command.js clear [--all] [--agent AGENT] [--task TASK]
 *   node scripts/cache-command.js config [--list] [--set KEY VALUE]
 */

const fs = require('fs');
const path = require('path');

// Command handlers
const commands = {
  status: require('../commands/cache-status'),
  clear: require('../commands/cache-clear'),
  config: require('../commands/cache-config')
};

/**
 * Parse command-line arguments into an object
 * Supports:
 *   --flag => { flag: true }
 *   --key value => { key: 'value' }
 *   --key val1 val2 => { key: ['val1', 'val2'] }
 */
function parseArgs(argv) {
  const args = {};
  let i = 0;

  while (i < argv.length) {
    const arg = argv[i];

    if (arg.startsWith('--')) {
      const key = arg.slice(2);
      const values = [];

      // Collect values until next flag
      i++;
      while (i < argv.length && !argv[i].startsWith('--')) {
        values.push(argv[i]);
        i++;
      }

      if (values.length === 0) {
        args[key] = true;
      } else if (values.length === 1) {
        args[key] = values[0];
      } else {
        args[key] = values;
      }
    } else {
      i++;
    }
  }

  return args;
}

/**
 * Main entry point
 */
async function main() {
  const argv = process.argv.slice(2);

  if (argv.length === 0) {
    printUsage();
    process.exit(0);
  }

  const command = argv[0];
  const commandArgv = argv.slice(1);

  if (!commands[command]) {
    console.error(`Error: Unknown command '${command}'`);
    console.error(`Available commands: ${Object.keys(commands).join(', ')}`);
    process.exit(1);
  }

  try {
    // Parse command-line arguments into object
    const args = parseArgs(commandArgv);

    // Call the command handler with parsed arguments
    const result = await commands[command].execute(args);

    if (result && result.success !== false) {
      // Output result
      if (result.output) {
        console.log(result.output);
      }
      process.exit(0);
    } else {
      // Error case
      if (result && result.error) {
        console.error(`Error: ${result.error}`);
      }
      process.exit(1);
    }
  } catch (error) {
    console.error(`Error executing command '${command}':`, error.message);
    if (process.env.DEBUG) {
      console.error(error.stack);
    }
    process.exit(1);
  }
}

/**
 * Print usage information
 */
function printUsage() {
  console.log(`
Cache Plugin CLI
================

Usage: cache-command.js <command> [options]

Commands:
  status     Display cache statistics and health metrics
             Usage: cache-command.js status [--detailed] [--export FORMAT]

  clear      Clear cache entries by criteria
             Usage: cache-command.js clear [--all] [--agent AGENT] [--task TASK] [--older-than DAYS]

  config     Configure cache behavior and thresholds
             Usage: cache-command.js config [--list] [--set KEY VALUE] [--validate]

Options:
  --help     Show this help message
  --version  Show version information

Examples:
  # Display cache status
  cache-command.js status

  # Clear old entries
  cache-command.js clear --older-than 7

  # Show configuration
  cache-command.js config --list

  # Set configuration
  cache-command.js config --set relevanceThreshold 85
  `);
}

// Handle --help and --version globally
if (process.argv.includes('--help') || process.argv.includes('-h')) {
  printUsage();
  process.exit(0);
}

if (process.argv.includes('--version') || process.argv.includes('-v')) {
  const packageJson = require('../package.json');
  console.log(`Cache Plugin v${packageJson.version}`);
  process.exit(0);
}

// Run main
main().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
