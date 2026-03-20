/**
 * Suno Producer Bridge — Popup UI
 */

const statusDiv = document.getElementById('status');
const testBtn = document.getElementById('testBtn');
const logDiv = document.getElementById('log');

function log(msg) {
  const div = document.createElement('div');
  div.textContent = `${new Date().toLocaleTimeString()} ${msg}`;
  logDiv.prepend(div);
  // Keep log short
  while (logDiv.children.length > 20) {
    logDiv.lastChild.remove();
  }
}

async function checkStatus() {
  try {
    // Check if content script is active on any Suno tab
    const tabs = await chrome.tabs.query({
      url: ['https://suno.com/*', 'https://app.suno.ai/*']
    });

    if (tabs.length === 0) {
      statusDiv.className = 'status disconnected';
      statusDiv.textContent = 'No Suno tab open. Open suno.com first.';
      log('No Suno tab found');
      return;
    }

    // Ping the background to check content script readiness
    chrome.runtime.sendMessage({ action: 'ping' }, (response) => {
      if (response?.contentScriptReady) {
        statusDiv.className = 'status connected';
        statusDiv.textContent = `Connected to Suno (tab ${response.sunoTabId})`;
        log('Content script ready');
      } else {
        statusDiv.className = 'status disconnected';
        statusDiv.textContent = 'Suno tab found but content script not ready. Try refreshing.';
        log('Content script not ready');
      }
    });
  } catch (err) {
    statusDiv.className = 'status disconnected';
    statusDiv.textContent = `Error: ${err.message}`;
    log(`Error: ${err.message}`);
  }
}

testBtn.addEventListener('click', async () => {
  testBtn.disabled = true;
  testBtn.textContent = 'Testing...';
  log('Testing connection...');

  try {
    // Test bridge server
    const resp = await fetch('http://localhost:7862/health', {
      method: 'GET',
      signal: AbortSignal.timeout(3000),
    });
    if (resp.ok) {
      log('Bridge server: OK');
    } else {
      log(`Bridge server: HTTP ${resp.status}`);
    }
  } catch (err) {
    log(`Bridge server: not reachable (${err.message})`);
  }

  await checkStatus();

  testBtn.disabled = false;
  testBtn.textContent = 'Test Connection';
});

// Check on popup open
checkStatus();
