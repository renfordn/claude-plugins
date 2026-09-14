/**
 * Test Suite: Audit Logger
 *
 * Tests for comprehensive audit logging with compliance support
 */

const AuditLogger = require('../skills/audit-logger');
const fs = require('fs');
const path = require('path');

describe('AuditLogger', () => {
  let logger;
  const testLogDir = './test-audit-logs';

  beforeEach(() => {
    logger = new AuditLogger({
      logDir: testLogDir,
      retentionDays: 30
    });
  });

  afterEach(() => {
    // Cleanup test logs recursively
    const removeDir = (dir) => {
      if (fs.existsSync(dir)) {
        fs.readdirSync(dir).forEach(file => {
          const filePath = path.join(dir, file);
          if (fs.lstatSync(filePath).isDirectory()) {
            removeDir(filePath);
          } else {
            fs.unlinkSync(filePath);
          }
        });
        fs.rmdirSync(dir);
      }
    };
    removeDir(testLogDir);
  });

  describe('Initialization', () => {
    test('should initialize with default config', () => {
      const l = new AuditLogger();
      expect(l.config.enabled).toBe(true);
      expect(l.config.retentionDays).toBe(90);
      expect(l.config.includeParameters).toBe(true);
      expect(l.config.includeSensitiveDetection).toBe(true);
    });

    test('should accept custom configuration', () => {
      const l = new AuditLogger({
        enabled: false,
        retentionDays: 60,
        includeParameters: false
      });
      expect(l.config.enabled).toBe(false);
      expect(l.config.retentionDays).toBe(60);
      expect(l.config.includeParameters).toBe(false);
    });

    test('should generate unique session ID', () => {
      const l1 = new AuditLogger();
      const l2 = new AuditLogger();
      expect(l1.sessionId).not.toBe(l2.sessionId);
      expect(l1.sessionId).toMatch(/^session-/);
    });
  });

  describe('Operation Logging', () => {
    test('should log cache hit', () => {
      logger.logHit('entry-1', { userId: 'user1', agentType: 'analyzer' });

      expect(logger.logs.length).toBe(1);
      expect(logger.logs[0].type).toBe('retrieve');
      expect(logger.logs[0].success).toBe(true);
      expect(logger.logs[0].entryId).toBe('entry-1');
      expect(logger.logs[0].userId).toBe('user1');
    });

    test('should log cache miss', () => {
      logger.logMiss('entry-2', { userId: 'user2' });

      expect(logger.logs.length).toBe(1);
      expect(logger.logs[0].type).toBe('retrieve');
      expect(logger.logs[0].success).toBe(false);
      expect(logger.logs[0].entryId).toBe('entry-2');
    });

    test('should log invalidation', () => {
      logger.logInvalidation('entry-3', 'manual_clear', { userId: 'admin' });

      expect(logger.logs.length).toBe(1);
      expect(logger.logs[0].type).toBe('invalidate');
      expect(logger.logs[0].tags).toContain('manual_clear');
    });

    test('should log search operation', () => {
      const criteria = { agentType: 'analyzer', tags: ['ml'] };
      logger.logSearch(criteria, 5, { userId: 'user1' });

      expect(logger.logs.length).toBe(1);
      expect(logger.logs[0].type).toBe('search');
      expect(logger.logs[0].resultCount).toBe(5);
    });

    test('should track operation duration', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        duration: 42
      });

      expect(logger.logs[0].duration).toBe(42);
    });

    test('should track IP address', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        ipAddress: '192.168.1.1'
      });

      expect(logger.logs[0].ipAddress).toBe('192.168.1.1');
    });

    test('should not log when disabled', () => {
      logger.config.enabled = false;
      logger.logHit('entry-1');

      expect(logger.logs.length).toBe(0);
    });
  });

  describe('Sensitive Data Detection', () => {
    test('should detect email addresses', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: { email: 'user@example.com' }
      });

      expect(logger.logs[0].sensitiveDetected).toContain('email');
    });

    test('should detect credit cards', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: { card: '4532-1234-5678-9012' }
      });

      expect(logger.logs[0].sensitiveDetected).toContain('credit_card');
    });

    test('should detect API keys', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: { key: 'FAKE_TEST_KEY_0000000000000000' }
      });

      expect(logger.logs[0].sensitiveDetected).toContain('api_key');
    });

    test('should detect passwords', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: { credentials: 'password=mysecretpass123' }
      });

      expect(logger.logs[0].sensitiveDetected).toContain('password');
    });

    test('should not detect sensitive data when disabled', () => {
      logger.config.includeSensitiveDetection = false;
      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: { email: 'user@example.com' }
      });

      expect(logger.logs[0].sensitiveDetected).toBeUndefined();
    });

    test('should custom sensitive patterns', () => {
      const l = new AuditLogger({
        sensitivePatterns: [
          { name: 'custom_id', pattern: /ID:\s*\d{6}/ }
        ]
      });

      l.logOperation({
        type: 'retrieve',
        success: true,
        parameters: { data: 'ID: 123456' }
      });

      expect(l.logs[0].sensitiveDetected).toContain('custom_id');
    });
  });

  describe('Filtering', () => {
    beforeEach(() => {
      logger.logHit('entry-1', { userId: 'user1', tenantId: 'tenant1' });
      logger.logMiss('entry-2', { userId: 'user2', tenantId: 'tenant2' });
      logger.logHit('entry-3', { userId: 'user1', tenantId: 'tenant1' });
    });

    test('should filter by user ID', () => {
      const entries = logger.getEntries({ userId: 'user1' });
      expect(entries.length).toBe(2);
      expect(entries.every(e => e.userId === 'user1')).toBe(true);
    });

    test('should filter by operation type', () => {
      const entries = logger.getEntries({ type: 'retrieve' });
      expect(entries.length).toBe(3);
    });

    test('should filter by tenant ID', () => {
      const entries = logger.getEntries({ tenantId: 'tenant1' });
      expect(entries.length).toBe(2);
      expect(entries.every(e => e.tenantId === 'tenant1')).toBe(true);
    });

    test('should filter by time range', () => {
      const now = Date.now();
      const entries = logger.getEntries({
        startTime: now - 5000,
        endTime: now + 5000
      });
      expect(entries.length).toBe(3);
    });

    test('should filter failures only', () => {
      const entries = logger.getEntries({ failuresOnly: true });
      expect(entries.length).toBe(1);
      expect(entries[0].success).toBe(false);
    });
  });

  describe('Export Formats', () => {
    beforeEach(() => {
      logger.logHit('entry-1', { userId: 'user1', agentType: 'analyzer' });
      logger.logMiss('entry-2', { userId: 'user2' });
    });

    test('should export to JSON', () => {
      const json = logger.exportJSON();
      expect(json).toHaveProperty('exportedAt');
      expect(json).toHaveProperty('totalEntries', 2);
      expect(json).toHaveProperty('entries');
      expect(Array.isArray(json.entries)).toBe(true);
    });

    test('should export to CSV', () => {
      const csv = logger.exportCSV();
      const lines = csv.split('\n');
      expect(lines[0]).toContain('Timestamp');
      expect(lines[0]).toContain('User ID');
      expect(lines.length).toBeGreaterThan(2); // Header + 2 entries
    });

    test('should export with filters', () => {
      const json = logger.exportJSON({ userId: 'user1' });
      expect(json.entries.length).toBe(1);
      expect(json.entries[0].userId).toBe('user1');
    });

    test('should handle empty exports', () => {
      const json = logger.exportJSON({ userId: 'nonexistent' });
      expect(json.totalEntries).toBe(0);
      expect(json.entries.length).toBe(0);
    });
  });

  describe('File Operations', () => {
    test('should save to JSON file', async () => {
      logger.logHit('entry-1');
      const result = await logger.saveToFile(
        path.join(testLogDir, 'test.json'),
        'json'
      );

      expect(result.success).toBe(true);
      expect(fs.existsSync(result.filepath)).toBe(true);

      const content = fs.readFileSync(result.filepath, 'utf8');
      const data = JSON.parse(content);
      expect(data.entries.length).toBe(1);
    });

    test('should save to CSV file', async () => {
      logger.logHit('entry-1');
      const result = await logger.saveToFile(
        path.join(testLogDir, 'test.csv'),
        'csv'
      );

      expect(result.success).toBe(true);
      expect(fs.existsSync(result.filepath)).toBe(true);

      const content = fs.readFileSync(result.filepath, 'utf8');
      expect(content).toContain('Timestamp');
    });

    test('should auto-generate filename with date', async () => {
      logger.logHit('entry-1');
      const result = await logger.saveToFile(null, 'json');

      expect(result.success).toBe(true);
      expect(result.filepath).toContain('audit-');
    });

    test('should create directory if not exists', async () => {
      logger.logHit('entry-1');
      const deepPath = path.join(testLogDir, 'deep', 'nested', 'test.json');
      const result = await logger.saveToFile(deepPath, 'json');

      expect(result.success).toBe(true);
      expect(fs.existsSync(deepPath)).toBe(true);
    });
  });

  describe('Statistics', () => {
    beforeEach(() => {
      logger.logHit('entry-1', { userId: 'user1', duration: 10 });
      logger.logHit('entry-2', { userId: 'user2', duration: 20 });
      logger.logMiss('entry-3', { userId: 'user1', duration: 15 });
    });

    test('should calculate success rate', () => {
      const stats = logger.getStats();
      expect(stats.successCount).toBe(2);
      expect(stats.errorCount).toBe(1);
      expect(stats.successRate).toBe('66.7%');
    });

    test('should calculate average duration', () => {
      const stats = logger.getStats();
      expect(stats.avgDuration).toContain('ms');
    });

    test('should group by operation type', () => {
      logger.logSearch({}, 1, { userId: 'user1' });
      const stats = logger.getStats();
      expect(stats.operationTypes['retrieve']).toBeDefined();
      expect(stats.operationTypes['search']).toBeDefined();
    });

    test('should track top users', () => {
      const stats = logger.getStats();
      expect(stats.topUsers.length).toBeGreaterThan(0);
      expect(stats.topUsers[0][0]).toBe('user1'); // user1 has 2 operations
    });

    test('should return empty stats for no entries', () => {
      logger.clear();
      const stats = logger.getStats();
      expect(stats.totalOperations).toBe(0);
      expect(stats.successRate).toBe('N/A');
    });
  });

  describe('Retention & Cleanup', () => {
    test('should cleanup old logs', async () => {
      logger.logHit('entry-1');
      logger.logHit('entry-2');

      // Simulate old entry
      logger.logs[0].timestamp = Date.now() - (100 * 24 * 60 * 60 * 1000); // 100 days ago

      const result = await logger.cleanup();
      expect(result.deleted).toBe(1);
      expect(logger.logs.length).toBe(1);
    });

    test('should respect retention days config', async () => {
      const l = new AuditLogger({ retentionDays: 7 });
      l.logHit('entry-1');
      l.logs[0].timestamp = Date.now() - (14 * 24 * 60 * 60 * 1000); // 14 days ago

      const result = await l.cleanup();
      expect(result.deleted).toBe(1);
    });

    test('should handle zero retention', async () => {
      logger.config.retentionDays = 0;
      logger.logHit('entry-1');

      const result = await logger.cleanup();
      expect(result.deleted).toBe(0);
    });
  });

  describe('Alerts', () => {
    test('should subscribe to alerts', () => {
      const callback = jest.fn();
      logger.subscribe(callback);

      expect(logger.config.alertCallbacks.length).toBeGreaterThan(0);
    });

    test('should unsubscribe from alerts', () => {
      const callback = jest.fn();
      const unsubscribe = logger.subscribe(callback);

      expect(logger.config.alertCallbacks.length).toBeGreaterThan(0);

      unsubscribe();
      expect(logger.config.alertCallbacks.length).toBe(0);
    });

    test('should alert on sensitive data', () => {
      const alert = jest.fn();
      logger.subscribe(alert);

      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: { email: 'user@example.com' }
      });

      expect(alert).toHaveBeenCalled();
      const call = alert.mock.calls[0][0];
      expect(call.type).toBe('sensitive_access');
      expect(call.severity).toBe('high');
    });

    test('should not alert when disabled', () => {
      logger.config.enableAlerts = false;
      const alert = jest.fn();
      logger.subscribe(alert);

      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: { email: 'user@example.com' }
      });

      expect(alert).not.toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    test('should handle null parameters', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: null
      });

      expect(logger.logs[0].parameterHash).toBeUndefined();
    });

    test('should handle large parameter data', () => {
      const largeData = { data: 'x'.repeat(10000) };
      logger.logOperation({
        type: 'retrieve',
        success: true,
        parameters: largeData
      });

      expect(logger.logs[0].parameterSize).toBeGreaterThan(10000);
    });

    test('should handle missing context fields', () => {
      logger.logHit('entry-1');

      expect(logger.logs[0].userId).toBe('anonymous');
      expect(logger.logs[0].agentType).toBeUndefined();
      expect(logger.logs[0].tenantId).toBeUndefined();
    });

    test('should clear all logs', () => {
      logger.logHit('entry-1');
      logger.logHit('entry-2');

      const result = logger.clear();
      expect(result.cleared).toBe(2);
      expect(logger.logs.length).toBe(0);
    });
  });

  describe('CSV Export Safety', () => {
    test('should escape quotes in CSV', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        error: 'Error with "quotes" inside'
      });

      const csv = logger.exportCSV();
      expect(csv).toContain('""');
    });

    test('should handle commas in CSV values', () => {
      logger.logOperation({
        type: 'retrieve',
        success: true,
        error: 'Error with, comma'
      });

      const csv = logger.exportCSV();
      const lines = csv.split('\n');
      expect(lines.length).toBeGreaterThan(1);
    });
  });
});
