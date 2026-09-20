'use strict';
const { sanitizeDeep } = require('../utils/sanitize-deep');

describe('sanitizeDeep', () => {
  test('passes through primitives', () => {
    expect(sanitizeDeep('hello')).toBe('hello');
    expect(sanitizeDeep(42)).toBe(42);
    expect(sanitizeDeep(null)).toBeNull();
  });

  test('redacts credential key at top level', () => {
    const result = sanitizeDeep({ api_key: 'secret', taskType: 'research' });
    expect(result.api_key).toBe('[REDACTED]');
    expect(result.taskType).toBe('research');
  });

  test('redacts credential key nested one level deep', () => {
    const result = sanitizeDeep({ config: { token: 'abc123', name: 'test' } });
    expect(result.config.token).toBe('[REDACTED]');
    expect(result.config.name).toBe('test');
  });

  test('redacts credential key nested two levels deep', () => {
    const result = sanitizeDeep({ a: { b: { password: 'p@ss' } } });
    expect(result.a.b.password).toBe('[REDACTED]');
  });

  test('handles arrays', () => {
    const result = sanitizeDeep([{ api_key: 'x' }, { name: 'y' }]);
    expect(result[0].api_key).toBe('[REDACTED]');
    expect(result[1].name).toBe('y');
  });

  test('handles mixed nesting with arrays', () => {
    const result = sanitizeDeep({ items: [{ secret: 'leak' }, { ok: 1 }] });
    expect(result.items[0].secret).toBe('[REDACTED]');
    expect(result.items[1].ok).toBe(1);
  });
});
