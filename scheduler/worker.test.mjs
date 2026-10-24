import assert from 'node:assert/strict';
import test from 'node:test';
import { dispatch } from './worker.mjs';

for (const [cron, expected] of [
  ['58 0 * * *', 'daily-story.yml'],
  ['58 3 * * *', 'ba-story.yml'],
  ['58 7 * * *', 'video-story.yml'],
]) {
  test(`dispatches ${expected} with safe inputs`, async () => {
    let request;
    const fetcher = async (url, options) => {
      request = { url, options };
      return { ok: true, status: 200 };
    };
    assert.equal(await dispatch(cron, 'test-token', fetcher), expected);
    assert.equal(request.options.method, 'POST');
    assert.match(request.url, new RegExp(`${expected.replace('.', '\\.')}\\/dispatches$`));
    const body = JSON.parse(request.options.body);
    assert.equal(body.ref, 'main');
    assert.equal(body.inputs.scheduled_dispatch, true);
    if (expected === 'video-story.yml' || expected === 'ba-story.yml') assert.equal(body.inputs.dry_run, false);
  });
}

test('rejects unexpected cron without calling GitHub', async () => {
  await assert.rejects(dispatch('0 0 * * *', 'test-token', () => { throw new Error('called'); }), /Unknown cron/);
});

test('rejects missing token and GitHub failure', async () => {
  await assert.rejects(dispatch('58 0 * * *', '', () => {}), /Missing GITHUB_DISPATCH_TOKEN/);
  await assert.rejects(dispatch('58 0 * * *', 'test-token', async () => ({ ok: false, status: 403 })), /HTTP 403/);
});
