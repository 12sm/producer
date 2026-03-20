/**
 * Suno Producer Bridge — Background Service Worker
 *
 * Manages the bridge between the local HTTP server (which Claude Code
 * talks to) and the Suno web UI (via content script).
 *
 * Architecture:
 *   Claude Code → HTTP POST to localhost:7862 → background.js → content.js → Suno UI
 *   Suno UI → content.js → background.js → HTTP response → Claude Code
 */

// ── State ──────────────────────────────────────────────────────────

let pendingJobs = new Map();  // jobId → { resolve, reject, status, result }
let contentScriptReady = false;
let sunoTabId = null;

// ── Message handling from content script ───────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'CONTENT_READY') {
    contentScriptReady = true;
    sunoTabId = sender.tab?.id;
    console.log('[Bridge] Content script ready on tab', sunoTabId);
    sendResponse({ ok: true });
    return;
  }

  if (message.type === 'GENERATION_STATUS') {
    const job = pendingJobs.get(message.jobId);
    if (job) {
      job.status = message.status;
      if (message.status === 'complete') {
        job.result = message.result;
      } else if (message.status === 'error') {
        job.error = message.error;
      }
    }
    sendResponse({ ok: true });
    return;
  }

  if (message.type === 'AUDIO_READY') {
    const job = pendingJobs.get(message.jobId);
    if (job) {
      job.result = {
        audioUrl: message.audioUrl,
        title: message.title,
        duration: message.duration,
      };
      job.status = 'complete';
    }
    sendResponse({ ok: true });
    return;
  }
});

// ── External message handling (from local server / native messaging) ──

chrome.runtime.onMessageExternal.addListener(
  (message, sender, sendResponse) => {
    if (message.action === 'generate') {
      handleGenerate(message).then(sendResponse);
      return true;  // async response
    }

    if (message.action === 'status') {
      const job = pendingJobs.get(message.jobId);
      sendResponse(job ? { status: job.status, result: job.result } : { error: 'Unknown job' });
      return;
    }

    if (message.action === 'ping') {
      sendResponse({ ok: true, contentScriptReady, sunoTabId });
      return;
    }
  }
);

// ── Generate handler ───────────────────────────────────────────────

async function handleGenerate(message) {
  if (!contentScriptReady || !sunoTabId) {
    return { error: 'Suno tab not ready. Open suno.com first.' };
  }

  const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

  pendingJobs.set(jobId, {
    status: 'submitted',
    result: null,
    error: null,
    prompt: message.prompt,
    createdAt: Date.now(),
  });

  // Send to content script
  try {
    await chrome.tabs.sendMessage(sunoTabId, {
      type: 'GENERATE',
      jobId: jobId,
      prompt: message.prompt,
      options: message.options || {},
    });
  } catch (err) {
    pendingJobs.delete(jobId);
    return { error: `Failed to reach Suno tab: ${err.message}` };
  }

  // Poll for completion
  const timeout = message.timeout || 300000;  // 5 min default
  const pollInterval = 3000;
  const start = Date.now();

  while (Date.now() - start < timeout) {
    const job = pendingJobs.get(jobId);
    if (!job) break;

    if (job.status === 'complete') {
      pendingJobs.delete(jobId);
      return { jobId, status: 'complete', result: job.result };
    }
    if (job.status === 'error') {
      const error = job.error;
      pendingJobs.delete(jobId);
      return { jobId, status: 'error', error };
    }

    await new Promise(r => setTimeout(r, pollInterval));
  }

  pendingJobs.delete(jobId);
  return { jobId, status: 'timeout', error: 'Generation timed out' };
}

// ── Cleanup old jobs ───────────────────────────────────────────────

setInterval(() => {
  const cutoff = Date.now() - 600000;  // 10 min
  for (const [id, job] of pendingJobs) {
    if (job.createdAt < cutoff) {
      pendingJobs.delete(id);
    }
  }
}, 60000);
