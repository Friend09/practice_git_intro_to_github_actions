'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { greet, getInput } = require('../main.js');

test('greet', () => {
  assert.equal(greet('Tally', false), 'hello, Tally');
  assert.equal(greet('Tally', true), 'HELLO, TALLY');
});

test('inputs keep their hyphens and uppercase the name', () => {
  assert.equal(getInput('who-to-greet', { 'INPUT_WHO-TO-GREET': ' Tally ' }), 'Tally');
  assert.equal(getInput('two words', { INPUT_TWO_WORDS: 'x' }), 'x');
  assert.equal(getInput('absent', {}), '');
});
