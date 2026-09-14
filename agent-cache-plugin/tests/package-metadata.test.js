const fs = require('fs');
const path = require('path');

describe('package.json metadata', () => {
  let packageJson;

  beforeAll(() => {
    const packagePath = path.join(__dirname, '../package.json');
    const content = fs.readFileSync(packagePath, 'utf-8');
    packageJson = JSON.parse(content);
  });

  test('repository.url should contain github.com', () => {
    expect(packageJson.repository).toBeDefined();
    expect(packageJson.repository.url).toBeDefined();
    expect(typeof packageJson.repository.url).toBe('string');
    expect(packageJson.repository.url).toContain('github.com');
  });

  test('repository.url should not contain "anthropic"', () => {
    expect(packageJson.repository.url).not.toContain('anthropic');
  });

  test('repository.url should contain "renfordn"', () => {
    expect(packageJson.repository.url).toContain('renfordn');
  });

  test('repository.url should be an HTTPS URL', () => {
    expect(packageJson.repository.url).toMatch(/^https:\/\//);
  });

  test('author field should be present and non-empty', () => {
    expect(packageJson.author).toBeDefined();
    expect(typeof packageJson.author).toBe('string');
    expect(packageJson.author.length).toBeGreaterThan(0);
  });

  test('author should not be "Cowork Inc." or "Agent UX Team"', () => {
    expect(packageJson.author).not.toBe('Cowork Inc.');
    expect(packageJson.author).not.toBe('Agent UX Team');
  });

  test('author should contain "Jay Nelson" or "renfordn"', () => {
    const author = packageJson.author.toLowerCase();
    expect(
      author.includes('jay nelson') || author.includes('renfordn')
    ).toBe(true);
  });

  test('homepage field should be present and non-empty', () => {
    expect(packageJson.homepage).toBeDefined();
    expect(typeof packageJson.homepage).toBe('string');
    expect(packageJson.homepage.length).toBeGreaterThan(0);
  });

  test('homepage should be an HTTPS URL', () => {
    expect(packageJson.homepage).toMatch(/^https:\/\//);
  });

  test('homepage should match repository domain and contain renfordn', () => {
    expect(packageJson.homepage).toContain('github.com');
    expect(packageJson.homepage).toContain('renfordn');
  });

  test('homepage should not contain "anthropic"', () => {
    expect(packageJson.homepage).not.toContain('anthropic');
  });
});
