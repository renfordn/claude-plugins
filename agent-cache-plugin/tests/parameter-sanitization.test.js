/**
 * Test Suite: Parameter Sanitization
 *
 * Validates regex-based credential detection and redaction.
 * Tests against current substring-based implementation to ensure upgrade to robust pattern matching.
 */

describe('sanitizeParameters', () => {
  let sanitizeParameters;

  beforeEach(() => {
    // Import sanitizeParameters from shared utils module
    const credentialSanitizer = require('../utils/credential-sanitizer');
    sanitizeParameters = credentialSanitizer.sanitizeParameters;
  });

  describe('Suite 1: Credential Detection (Diverse Patterns)', () => {
    test('should redact api_key (lowercase with underscore)', () => {
      const result = sanitizeParameters({ api_key: 'sk-1234567890' });
      expect(result.api_key).toBe('[REDACTED]');
    });

    test('should redact apikey (no underscore)', () => {
      const result = sanitizeParameters({ apikey: 'mykey123' });
      expect(result.apikey).toBe('[REDACTED]');
    });

    test('should redact AWS_ACCESS_KEY_ID', () => {
      const result = sanitizeParameters({ AWS_ACCESS_KEY_ID: 'AKIA2E45Z7VRWKBVJQ2X' });
      expect(result.AWS_ACCESS_KEY_ID).toBe('[REDACTED]');
    });

    test('should redact AWS_SECRET_ACCESS_KEY', () => {
      const result = sanitizeParameters({ AWS_SECRET_ACCESS_KEY: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY' });
      expect(result.AWS_SECRET_ACCESS_KEY).toBe('[REDACTED]');
    });

    test('should redact OPENAI_API_KEY', () => {
      const result = sanitizeParameters({ OPENAI_API_KEY: 'sk-proj-abc123def456' });
      expect(result.OPENAI_API_KEY).toBe('[REDACTED]');
    });

    test('should redact openai_api_key (lowercase)', () => {
      const result = sanitizeParameters({ openai_api_key: 'sk-proj-123456' });
      expect(result.openai_api_key).toBe('[REDACTED]');
    });

    test('should redact secret_key', () => {
      const result = sanitizeParameters({ secret_key: 'mysecret123' });
      expect(result.secret_key).toBe('[REDACTED]');
    });

    test('should redact secret_token', () => {
      const result = sanitizeParameters({ secret_token: 'token123xyz' });
      expect(result.secret_token).toBe('[REDACTED]');
    });

    test('should redact password field', () => {
      const result = sanitizeParameters({ password: 'pass123!' });
      expect(result.password).toBe('[REDACTED]');
    });

    test('should redact passwd (abbreviated)', () => {
      const result = sanitizeParameters({ passwd: 'mypasswd' });
      expect(result.passwd).toBe('[REDACTED]');
    });

    test('should redact pwd field', () => {
      const result = sanitizeParameters({ pwd: 'secret123' });
      expect(result.pwd).toBe('[REDACTED]');
    });

    test('should redact access_token', () => {
      const result = sanitizeParameters({ access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' });
      expect(result.access_token).toBe('[REDACTED]');
    });

    test('should redact refresh_token', () => {
      const result = sanitizeParameters({ refresh_token: 'refresh-abc123' });
      expect(result.refresh_token).toBe('[REDACTED]');
    });

    test('should redact auth_token', () => {
      const result = sanitizeParameters({ auth_token: 'auth123xyz' });
      expect(result.auth_token).toBe('[REDACTED]');
    });

    test('should redact credential field', () => {
      const result = sanitizeParameters({ credential: 'cred123' });
      expect(result.credential).toBe('[REDACTED]');
    });

    test('should redact authorization header with Bearer token', () => {
      const result = sanitizeParameters({ Authorization: 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9' });
      expect(result.Authorization).toBe('[REDACTED]');
    });

    test('should redact authorization header (lowercase)', () => {
      const result = sanitizeParameters({ authorization: 'Bearer token123' });
      expect(result.authorization).toBe('[REDACTED]');
    });
  });

  describe('Suite 2: Case Insensitivity', () => {
    test('should redact API_KEY (uppercase)', () => {
      const result = sanitizeParameters({ API_KEY: 'key123' });
      expect(result.API_KEY).toBe('[REDACTED]');
    });

    test('should redact Api_Key (mixed case)', () => {
      const result = sanitizeParameters({ Api_Key: 'key456' });
      expect(result.Api_Key).toBe('[REDACTED]');
    });

    test('should redact TOKEN (uppercase)', () => {
      const result = sanitizeParameters({ TOKEN: 'tok789' });
      expect(result.TOKEN).toBe('[REDACTED]');
    });

    test('should redact Secret (title case)', () => {
      const result = sanitizeParameters({ Secret: 'secret999' });
      expect(result.Secret).toBe('[REDACTED]');
    });

    test('should redact PASSWORD (all caps)', () => {
      const result = sanitizeParameters({ PASSWORD: 'pass123' });
      expect(result.PASSWORD).toBe('[REDACTED]');
    });
  });

  describe('Suite 3: False Positive Prevention (Non-Credential Fields)', () => {
    test('should NOT redact api_version', () => {
      const result = sanitizeParameters({ api_version: '2024-01-01' });
      expect(result.api_version).toBe('2024-01-01');
    });

    test('should NOT redact auth_method', () => {
      const result = sanitizeParameters({ auth_method: 'oauth2' });
      expect(result.auth_method).toBe('oauth2');
    });

    test('should NOT redact key_size (integer)', () => {
      const result = sanitizeParameters({ key_size: 2048 });
      expect(result.key_size).toBe(2048);
    });

    test('should NOT redact api_docs_url', () => {
      const result = sanitizeParameters({ api_docs_url: 'https://api.example.com/docs' });
      expect(result.api_docs_url).toBe('https://api.example.com/docs');
    });

    test('should NOT redact token_type', () => {
      const result = sanitizeParameters({ token_type: 'Bearer' });
      expect(result.token_type).toBe('Bearer');
    });

    test('should NOT redact secret_answer (non-credential)', () => {
      const result = sanitizeParameters({ secret_answer: 'blue' });
      expect(result.secret_answer).toBe('blue');
    });

    test('should NOT redact key_rotation_days', () => {
      const result = sanitizeParameters({ key_rotation_days: 90 });
      expect(result.key_rotation_days).toBe(90);
    });

    test('should NOT redact password_policy (config, not secret)', () => {
      const result = sanitizeParameters({ password_policy: 'strong' });
      expect(result.password_policy).toBe('strong');
    });
  });

  describe('Suite 4: Realistic Credential Payloads', () => {
    test('should sanitize AWS environment variables object', () => {
      const awsEnv = {
        AWS_ACCESS_KEY_ID: 'AKIA2E45Z7VRWKBVJQ2X',
        AWS_SECRET_ACCESS_KEY: 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        AWS_REGION: 'us-east-1',
        AWS_DEFAULT_REGION: 'us-west-2'
      };
      const result = sanitizeParameters(awsEnv);
      expect(result.AWS_ACCESS_KEY_ID).toBe('[REDACTED]');
      expect(result.AWS_SECRET_ACCESS_KEY).toBe('[REDACTED]');
      expect(result.AWS_REGION).toBe('us-east-1');
      expect(result.AWS_DEFAULT_REGION).toBe('us-west-2');
    });

    test('should sanitize OpenAI API configuration object', () => {
      const openaiConfig = {
        openai_api_key: 'sk-proj-abc123def456',
        openai_org_id: 'org-123456',
        api_version: '2024-02-01',
        model: 'gpt-4',
        temperature: 0.7
      };
      const result = sanitizeParameters(openaiConfig);
      expect(result.openai_api_key).toBe('[REDACTED]');
      expect(result.openai_org_id).toBe('org-123456');
      expect(result.api_version).toBe('2024-02-01');
      expect(result.model).toBe('gpt-4');
      expect(result.temperature).toBe(0.7);
    });

    test('should sanitize authorization headers object', () => {
      const headers = {
        'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9',
        'X-API-Key': 'sk-12345',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      };
      const result = sanitizeParameters(headers);
      expect(result.Authorization).toBe('[REDACTED]');
      expect(result['X-API-Key']).toBe('[REDACTED]');
      expect(result['Content-Type']).toBe('application/json');
      expect(result.Accept).toBe('application/json');
    });
  });

  describe('Suite 5: Edge Cases', () => {
    test('should handle empty object', () => {
      const result = sanitizeParameters({});
      expect(result).toEqual({});
    });

    test('should handle object with no credentials', () => {
      const params = {
        name: 'test',
        age: 30,
        email: 'user@example.com',
        taskType: 'analysis'
      };
      const result = sanitizeParameters(params);
      expect(result).toEqual(params);
    });

    test('should handle null input', () => {
      const result = sanitizeParameters(null);
      expect(result).toEqual({});
    });

    test('should handle undefined input', () => {
      const result = sanitizeParameters(undefined);
      expect(result).toEqual({});
    });

    test('should handle mixed credentials and non-credentials in same object', () => {
      const mixed = {
        username: 'john_doe',
        password: 'secret123!',
        email: 'john@example.com',
        api_key: 'sk-abc123',
        taskType: 'processing',
        token: 'xyz789',
        iterations: 5
      };
      const result = sanitizeParameters(mixed);
      expect(result.username).toBe('john_doe');
      expect(result.password).toBe('[REDACTED]');
      expect(result.email).toBe('john@example.com');
      expect(result.api_key).toBe('[REDACTED]');
      expect(result.taskType).toBe('processing');
      expect(result.token).toBe('[REDACTED]');
      expect(result.iterations).toBe(5);
    });

    test('should preserve non-string credential values that are not secrets', () => {
      const params = {
        api_version_number: 1,
        key_size: 2048,
        token_count: 100
      };
      const result = sanitizeParameters(params);
      expect(result.api_version_number).toBe(1);
      expect(result.key_size).toBe(2048);
      expect(result.token_count).toBe(100);
    });

    test('should handle deeply mixed credential patterns', () => {
      const complex = {
        app_name: 'MyApp',
        secret: 'mysecret',
        secretariat: 'office',
        password: 'pass123',
        authorization_code: 'auth123',
        auth_method: 'oauth',
        credentials: 'cred123'
      };
      const result = sanitizeParameters(complex);
      expect(result.app_name).toBe('MyApp');
      expect(result.secret).toBe('[REDACTED]');
      expect(result.secretariat).toBe('office'); // 'secretariat' is not a credential
      expect(result.password).toBe('[REDACTED]');
      expect(result.authorization_code).toBe('[REDACTED]');
      expect(result.auth_method).toBe('oauth'); // 'auth_method' is config, not secret
      expect(result.credentials).toBe('[REDACTED]');
    });
  });
});
