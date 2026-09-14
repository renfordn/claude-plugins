/**
 * Shared utility: stdin JSON reader
 *
 * Provides common stdin reading logic for all hooks.
 * Handles JSON parsing with error handling.
 */

/**
 * Read stdin and parse JSON
 * @returns {Promise<Object>} Parsed JSON from stdin
 * @throws {Error} If JSON parsing fails
 */
async function readStdinJSON() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf-8');

    process.stdin.on('data', chunk => {
      data += chunk;
    });

    process.stdin.on('end', () => {
      try {
        const parsed = JSON.parse(data);
        resolve(parsed);
      } catch (err) {
        reject(new Error(`Invalid JSON input: ${err.message}`));
      }
    });
  });
}

module.exports = { readStdinJSON };
