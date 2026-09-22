'use strict';
const fs = require('fs');
const { TEST_DATA_ROOT } = require('./test-data-root');

module.exports = () => {
  fs.rmSync(TEST_DATA_ROOT, { recursive: true, force: true });
};
