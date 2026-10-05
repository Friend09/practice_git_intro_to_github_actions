'use strict';
// Dependency-free JavaScript action: reads inputs from INPUT_* variables and writes
// outputs and state through the files named by GITHUB_OUTPUT and GITHUB_STATE.
const fs = require('node:fs');

/** Build the greeting, optionally upper-cased. */
function greet(name, shout) {
  const text = `hello, ${name}`;
  return shout ? text.toUpperCase() : text;
}

/** Read an input the way the runner exposes it: INPUT_<UPPERCASED NAME>, spaces to _. */
function getInput(name, env = process.env) {
  return (env[`INPUT_${name.replace(/ /g, '_').toUpperCase()}`] || '').trim();
}

/** Append name=value to the file named by an environment variable. */
function appendFile(envVar, name, value, env = process.env) {
  fs.appendFileSync(env[envVar], `${name}=${value}\n`);
}

/** Run the action. */
function run(env = process.env) {
  const who = getInput('who-to-greet', env);
  if (!who) {
    process.stdout.write('::error title=Missing input::who-to-greet is required\n');
    process.exitCode = 1;
    return;
  }
  const greeting = greet(who, getInput('shout', env) === 'true');
  const names = Object.keys(env).filter((k) => k.startsWith('INPUT_')).sort();
  appendFile('GITHUB_OUTPUT', 'greeting', greeting, env);
  appendFile('GITHUB_OUTPUT', 'input-env-names', names.join(','), env);
  appendFile('GITHUB_OUTPUT', 'node-version', process.version, env);
  appendFile('GITHUB_STATE', 'started', String(Date.now()), env);
  process.stdout.write(`${greeting}\n`);
}

module.exports = { greet, getInput, run };
if (require.main === module) run();
