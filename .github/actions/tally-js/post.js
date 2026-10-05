'use strict';
// Runs in the post phase, even if the job failed (post-if defaults to always()).
const started = Number(process.env.STATE_started || 0);
const elapsed = started ? Date.now() - started : -1;
process.stdout.write(`REPORT js_post_ran=yes state_started_present=${started > 0 ? 'yes' : 'no'} elapsed_ms_ge_0=${elapsed >= 0 ? 'yes' : 'no'}\n`);
