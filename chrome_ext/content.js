/**
 * Suno Producer Bridge — Content Script
 *
 * Injected into suno.com pages. Automates the Suno UI:
 * - Fills in prompt text
 * - Clicks generate
 * - Monitors for completion
 * - Extracts audio URLs
 *
 * Note: Suno's UI changes frequently. The selectors here are best-effort
 * and may need updating. The script uses multiple fallback strategies.
 */

// ── Notify background we're ready ──────────────────────────────────

chrome.runtime.sendMessage({ type: 'CONTENT_READY' });

// ── Selector strategies (updated as Suno UI changes) ───────────────

const SELECTORS = {
  // Prompt input — try multiple selectors
  promptInput: [
    'textarea[placeholder*="song"]',
    'textarea[placeholder*="prompt"]',
    'textarea[placeholder*="describe"]',
    'textarea[data-testid="prompt-input"]',
    '.prompt-input textarea',
    'textarea',
  ],

  // Generate/Create button
  generateButton: [
    'button[data-testid="generate-button"]',
    'button[aria-label*="Create"]',
    'button[aria-label*="Generate"]',
    'button:has(svg):has(span)',
  ],

  // Audio player / track elements (for detecting completion)
  audioElement: [
    'audio[src]',
    'audio source[src]',
    '[data-testid="audio-player"]',
  ],

  // Track list items
  trackItem: [
    '[data-testid="track-item"]',
    '.track-item',
    '[class*="track"]',
  ],
};

// ── Helper: find element with fallback selectors ───────────────────

function findElement(selectorList) {
  for (const selector of selectorList) {
    try {
      const el = document.querySelector(selector);
      if (el) return el;
    } catch (e) {
      // Invalid selector, skip
    }
  }
  return null;
}

function findAllElements(selectorList) {
  for (const selector of selectorList) {
    try {
      const els = document.querySelectorAll(selector);
      if (els.length > 0) return Array.from(els);
    } catch (e) {
      // Invalid selector, skip
    }
  }
  return [];
}

// ── Helper: set input value with React compatibility ───────────────

function setInputValue(element, value) {
  // React overrides value setter, so we need to use the native one
  const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype, 'value'
  )?.set || Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
  )?.set;

  if (nativeInputValueSetter) {
    nativeInputValueSetter.call(element, value);
  } else {
    element.value = value;
  }

  // Dispatch events React listens for
  element.dispatchEvent(new Event('input', { bubbles: true }));
  element.dispatchEvent(new Event('change', { bubbles: true }));
}

// ── Helper: wait for element to appear ─────────────────────────────

function waitForElement(selectorList, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const el = findElement(selectorList);
    if (el) return resolve(el);

    const observer = new MutationObserver(() => {
      const el = findElement(selectorList);
      if (el) {
        observer.disconnect();
        resolve(el);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    setTimeout(() => {
      observer.disconnect();
      reject(new Error('Element not found within timeout'));
    }, timeoutMs);
  });
}

// ── Helper: detect new audio appearing ─────────────────────────────

function waitForNewAudio(existingUrls, timeoutMs = 300000) {
  return new Promise((resolve, reject) => {
    const check = () => {
      const audios = document.querySelectorAll('audio[src], audio source[src]');
      for (const audio of audios) {
        const src = audio.src || audio.getAttribute('src');
        if (src && !existingUrls.has(src)) {
          return src;
        }
      }
      return null;
    };

    // Check immediately
    const immediate = check();
    if (immediate) return resolve(immediate);

    // Observe for changes
    const observer = new MutationObserver(() => {
      const found = check();
      if (found) {
        observer.disconnect();
        resolve(found);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['src'],
    });

    setTimeout(() => {
      observer.disconnect();
      reject(new Error('No new audio detected within timeout'));
    }, timeoutMs);
  });
}

// ── Get current audio URLs on page ─────────────────────────────────

function getCurrentAudioUrls() {
  const urls = new Set();
  document.querySelectorAll('audio[src], audio source[src]').forEach(el => {
    const src = el.src || el.getAttribute('src');
    if (src) urls.add(src);
  });
  return urls;
}

// ── Message handling from background ───────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GENERATE') {
    handleGenerate(message.jobId, message.prompt, message.options)
      .catch(err => {
        chrome.runtime.sendMessage({
          type: 'GENERATION_STATUS',
          jobId: message.jobId,
          status: 'error',
          error: err.message,
        });
      });
    sendResponse({ ok: true });
    return;
  }
});

// ── Main generation flow ───────────────────────────────────────────

async function handleGenerate(jobId, prompt, options = {}) {
  // Notify: starting
  chrome.runtime.sendMessage({
    type: 'GENERATION_STATUS',
    jobId,
    status: 'filling_prompt',
  });

  // 1. Find and fill prompt input
  const input = await waitForElement(SELECTORS.promptInput);
  if (!input) throw new Error('Could not find prompt input');

  input.focus();
  setInputValue(input, prompt);

  // Small delay for UI to update
  await new Promise(r => setTimeout(r, 500));

  // 2. Snapshot existing audio
  const existingAudio = getCurrentAudioUrls();

  // 3. Click generate
  chrome.runtime.sendMessage({
    type: 'GENERATION_STATUS',
    jobId,
    status: 'clicking_generate',
  });

  const button = findElement(SELECTORS.generateButton);
  if (!button) throw new Error('Could not find generate button');

  button.click();

  // 4. Wait for generation
  chrome.runtime.sendMessage({
    type: 'GENERATION_STATUS',
    jobId,
    status: 'generating',
  });

  const audioUrl = await waitForNewAudio(existingAudio, options.timeout || 300000);

  // 5. Report completion
  chrome.runtime.sendMessage({
    type: 'AUDIO_READY',
    jobId,
    audioUrl,
    title: prompt.slice(0, 50),
    duration: null,  // Can't reliably extract from UI
  });
}
