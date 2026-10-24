/** Cloudflare cron trigger for the three Instagram Story workflows. */
export const JOBS = Object.freeze({
  '58 0 * * *': 'daily-story.yml', // 08:58 Asia/Taipei
  '58 3 * * *': 'ba-story.yml', // 11:58 Asia/Taipei
  '58 7 * * *': 'video-story.yml', // 15:58 Asia/Taipei
});

export async function dispatch(cron, token, fetcher = fetch) {
  const workflow = JOBS[cron];
  if (!workflow) throw new Error(`Unknown cron: ${cron}`);
  if (!token) throw new Error('Missing GITHUB_DISPATCH_TOKEN');
  const url = `https://api.github.com/repos/rayhuang199601-source/whitening-net-daily-story/actions/workflows/${workflow}/dispatches`;
  const inputs = workflow === 'video-story.yml' || workflow === 'ba-story.yml'
    ? { dry_run: false, scheduled_dispatch: true }
    : { scheduled_dispatch: true };
  const response = await fetcher(url, {
    method: 'POST',
    headers: {
      'Accept': 'application/vnd.github+json',
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'User-Agent': 'whitening-net-cloud-scheduler',
      'X-GitHub-Api-Version': '2026-03-10',
    },
    body: JSON.stringify({ ref: 'main', inputs }),
  });
  if (!response.ok) throw new Error(`GitHub dispatch failed: HTTP ${response.status}`);
  return workflow;
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(dispatch(event.cron, env.GITHUB_DISPATCH_TOKEN));
  },
  async fetch() {
    return new Response('Not found', { status: 404 });
  },
};
