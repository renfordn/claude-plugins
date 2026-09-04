#!/usr/bin/env node

/**
 * Discovery Engine for plan-skill-generator
 * Analyzes a project directory and generates a structured discovery plan.
 *
 * Usage: node discovery.mjs [projectDir]
 * Output: JSON plan conforming to references/plan_schema.json
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Discovery patterns - what files/content indicate project characteristics
const DISCOVERY_PATTERNS = {
  'web-app': {
    indicators: [
      { file: 'package.json', content: /react|vue|svelte|angular|next|nuxt/ },
      { file: 'package.json', content: /vite|webpack|parcel|esbuild/ },
      { file: '.github/workflows/*.yml', content: /npm.*start|vite|build/ },
      { file: 'index.html', exists: true },
      { file: 'tsconfig.json', exists: true },
    ],
    score: 10,
  },
  'cli': {
    indicators: [
      { file: 'package.json', content: /bin|cli|yargs|commander|oclif/ },
      { file: 'Cargo.toml', content: /clap|structopt/ },
      { file: 'go.mod', exists: true },
      { file: 'Makefile', content: /bin\/|^all:/ },
      { file: 'setup.py', content: /console_scripts|entry_points/ },
    ],
    score: 8,
  },
  'library': {
    indicators: [
      { file: 'package.json', content: /"main"|"exports"/ },
      { file: 'package.json', content: /false.*private/ }, // not marked private
      { file: 'src/index.ts', exists: true },
      { file: 'lib/index.js', exists: true },
    ],
    score: 7,
  },
  'desktop': {
    indicators: [
      { file: 'package.json', content: /electron|tauri|nwjs/ },
      { file: 'src-tauri/tauri.conf.json', exists: true },
      { file: '.github/workflows/*.yml', content: /electron|dmg|msi/ },
    ],
    score: 9,
  },
  'server': {
    indicators: [
      { file: 'package.json', content: /express|fastify|hapi|koa|nestjs|django|flask|rails/ },
      { file: 'package.json', content: /"start"|"dev"/ },
      { file: 'main.rs', content: /actix|axum|rocket/ },
      { file: 'go.mod', content: /chi|gin|echo/ },
      { file: 'Dockerfile', exists: true },
    ],
    score: 8,
  },
};

const TECH_PATTERNS = {
  react: { file: 'package.json', content: /react/ },
  vue: { file: 'package.json', content: /vue/ },
  svelte: { file: 'package.json', content: /svelte/ },
  angular: { file: 'package.json', content: /angular/ },
  vite: { file: 'package.json', content: /vite/ },
  webpack: { file: 'package.json', content: /webpack/ },
  typescript: { file: 'tsconfig.json', exists: true },
  node: { file: 'package.json', exists: true },
  rust: { file: 'Cargo.toml', exists: true },
  go: { file: 'go.mod', exists: true },
  python: { file: 'pyproject.toml', exists: true },
  electron: { file: 'package.json', content: /electron/ },
  docker: { file: 'Dockerfile', exists: true },
};

const BUILD_SYSTEMS = {
  npm: { file: 'package.json', exists: true },
  yarn: { file: 'yarn.lock', exists: true },
  pnpm: { file: 'pnpm-lock.yaml', exists: true },
  cargo: { file: 'Cargo.toml', exists: true },
  go: { file: 'go.mod', exists: true },
  python: { file: 'pyproject.toml', exists: true },
  make: { file: 'Makefile', exists: true },
  gradle: { file: 'build.gradle', exists: true },
};

const TEST_FRAMEWORKS = {
  vitest: { file: 'package.json', content: /vitest/ },
  jest: { file: 'package.json', content: /jest/ },
  mocha: { file: 'package.json', content: /mocha/ },
  pytest: { file: 'pyproject.toml', content: /pytest/ },
  'cargo test': { file: 'Cargo.toml', exists: true },
  'go test': { file: 'go.mod', exists: true },
};

/**
 * Read file with error handling
 */
function readFileSync(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8');
  } catch {
    return null;
  }
}

/**
 * Check if a pattern matches in a directory
 */
function matchPattern(projectDir, pattern) {
  const { file, content, exists } = pattern;

  // Handle glob patterns (*.yml)
  if (file.includes('*')) {
    const dir = path.dirname(file);
    const glob = path.basename(file);
    const fullDir = path.join(projectDir, dir);

    if (!fs.existsSync(fullDir)) return false;

    const files = fs.readdirSync(fullDir);
    const regex = new RegExp(`^${glob.replace('*', '.*')}$`);

    return files.some(f => {
      if (!regex.test(f)) return false;
      const fullPath = path.join(fullDir, f);
      if (!content) return true;
      const fileContent = readFileSync(fullPath);
      return fileContent && content.test(fileContent);
    });
  }

  const fullPath = path.join(projectDir, file);

  if (exists) {
    return fs.existsSync(fullPath);
  }

  if (content) {
    const fileContent = readFileSync(fullPath);
    return fileContent && content.test(fileContent);
  }

  return false;
}

/**
 * Detect project type by scoring patterns
 */
function detectProjectType(projectDir) {
  const scores = {};

  for (const [type, config] of Object.entries(DISCOVERY_PATTERNS)) {
    let score = 0;
    for (const indicator of config.indicators) {
      if (matchPattern(projectDir, indicator)) {
        score += 1;
      }
    }
    scores[type] = score;
  }

  const [type, maxScore] = Object.entries(scores).reduce(([t, s], [kt, ks]) => ks > s ? [kt, ks] : [t, s]);

  return { type, confidence: maxScore > 0 ? Math.min(1, maxScore / 5) : 0 };
}

/**
 * Detect technologies used
 */
function detectTechnologies(projectDir) {
  const techs = [];

  for (const [tech, pattern] of Object.entries(TECH_PATTERNS)) {
    if (matchPattern(projectDir, pattern)) {
      techs.push(tech);
    }
  }

  return techs;
}

/**
 * Detect build system
 */
function detectBuildSystem(projectDir) {
  for (const [system, pattern] of Object.entries(BUILD_SYSTEMS)) {
    if (matchPattern(projectDir, pattern)) {
      return system;
    }
  }
  return 'none';
}

/**
 * Detect test framework
 */
function detectTestFramework(projectDir) {
  for (const [framework, pattern] of Object.entries(TEST_FRAMEWORKS)) {
    if (matchPattern(projectDir, pattern)) {
      return framework;
    }
  }
  return null;
}

/**
 * Detect launch method by examining package.json scripts or entry points
 */
function detectLaunchMethod(projectDir, unitType) {
  const packageJsonPath = path.join(projectDir, 'package.json');
  const packageJson = readFileSync(packageJsonPath);

  if (packageJson) {
    try {
      const pkg = JSON.parse(packageJson);
      const scripts = pkg.scripts || {};

      if (scripts.start || scripts.dev) {
        return 'dev-server';
      }

      if (pkg.bin) {
        return 'binary';
      }

      if (pkg.main || pkg.exports) {
        return 'import';
      }
    } catch {
      // Ignore parse errors
    }
  }

  if (unitType === 'cli') return 'binary';
  if (unitType === 'library') return 'import';
  if (unitType === 'server') return 'dev-server';
  if (unitType === 'web-app') return 'dev-server';

  // Check for Makefile
  if (fs.existsSync(path.join(projectDir, 'Makefile'))) {
    return 'makefile';
  }

  // Check for Dockerfile
  if (fs.existsSync(path.join(projectDir, 'Dockerfile'))) {
    return 'dockerfile';
  }

  return 'unknown';
}

/**
 * Determine device type based on project
 */
function detectDeviceType(unitType, techs) {
  if (techs.includes('electron')) return 'gui';
  if (unitType === 'desktop') return 'gui';
  if (unitType === 'cli') return 'tty';
  if (unitType === 'web-app') return 'headless';
  if (unitType === 'server') return 'headless';
  return 'headless';
}

/**
 * Recommend driver pattern
 */
function recommendDriverPattern(unitType, techs) {
  if (techs.includes('electron')) return 'tmux';
  if (unitType === 'web-app') return 'playwright';
  if (unitType === 'cli') return 'cli';
  if (unitType === 'library') return 'library';
  if (unitType === 'server') return 'curl';
  if (unitType === 'desktop') return 'tmux';
  return 'custom';
}

/**
 * Generate key findings
 */
function generateKeyFindings(unitType, techs, buildSystem, launchMethod) {
  const findings = [];

  findings.push(`Project type: ${unitType}`);

  if (techs.length > 0) {
    findings.push(`Technologies: ${techs.join(', ')}`);
  }

  if (buildSystem !== 'none') {
    findings.push(`Build system: ${buildSystem}`);
  }

  if (launchMethod !== 'unknown') {
    findings.push(`Launch method: ${launchMethod}`);
  }

  return findings;
}

/**
 * Generate potential issues
 */
function generatePotentialIssues(projectDir, buildSystem) {
  const issues = [];

  // Check if dependencies need installation
  if (buildSystem === 'npm' || buildSystem === 'yarn' || buildSystem === 'pnpm') {
    if (fs.existsSync(path.join(projectDir, 'package.json'))) {
      if (!fs.existsSync(path.join(projectDir, 'node_modules'))) {
        issues.push(`Dependencies not installed. Run '${buildSystem} install' before launching.`);
      }
    }
  }

  // Check for native dependencies
  const packageJsonPath = path.join(projectDir, 'package.json');
  const packageJson = readFileSync(packageJsonPath);
  if (packageJson && (packageJson.includes('native') || packageJson.includes('binding'))) {
    issues.push('Project has native dependencies; may need compilation.');
  }

  return issues;
}

/**
 * Main discovery function
 */
export function discover(projectDir = '.') {
  const startTime = Date.now();
  let filesScanned = 0;
  let patternsMatched = 0;

  // Normalize path
  const resolvedDir = path.resolve(projectDir);

  if (!fs.existsSync(resolvedDir)) {
    throw new Error(`Project directory not found: ${resolvedDir}`);
  }

  // Count files scanned
  function countFiles(dir, depth = 0) {
    if (depth > 2) return; // Limit depth
    try {
      const entries = fs.readdirSync(dir);
      filesScanned += entries.length;
      for (const entry of entries) {
        const fullPath = path.join(dir, entry);
        if (fs.statSync(fullPath).isDirectory() && !entry.startsWith('.')) {
          countFiles(fullPath, depth + 1);
        }
      }
    } catch {
      // Ignore errors
    }
  }
  countFiles(resolvedDir);

  // Detect characteristics
  const { type: unitType, confidence: typeConfidence } = detectProjectType(resolvedDir);
  const techs = detectTechnologies(resolvedDir);
  const buildSystem = detectBuildSystem(resolvedDir);
  const testFramework = detectTestFramework(resolvedDir);
  const launchMethod = detectLaunchMethod(resolvedDir, unitType);
  const deviceType = detectDeviceType(unitType, techs);
  const driverPattern = recommendDriverPattern(unitType, techs);

  // Generate findings
  const keyFindings = generateKeyFindings(unitType, techs, buildSystem, launchMethod);
  const potentialIssues = generatePotentialIssues(resolvedDir, buildSystem);

  // Estimate confidence
  let confidence = typeConfidence;
  if (unitType === 'unknown') confidence = 0.3;

  const discoveryTimeMs = Date.now() - startTime;

  return {
    unit_path: '.',
    unit_type: unitType || 'unknown',
    detected_technologies: techs,
    build_system: buildSystem,
    test_framework: testFramework,
    launch_method: launchMethod,
    device_type: deviceType,
    key_findings: keyFindings,
    potential_issues: potentialIssues,
    recommended_driver_pattern: driverPattern,
    confidence_level: Math.round(confidence * 100) / 100,
    discovery_metadata: {
      files_scanned: filesScanned,
      patterns_matched: techs.length + (buildSystem !== 'none' ? 1 : 0) + (testFramework ? 1 : 0),
      discovery_time_ms: discoveryTimeMs,
    },
  };
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const projectDir = process.argv[2] || '.';

  try {
    const plan = discover(projectDir);
    console.log(JSON.stringify(plan, null, 2));
  } catch (error) {
    console.error('Discovery failed:', error.message);
    process.exit(1);
  }
}

export default discover;
