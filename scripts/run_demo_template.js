const { chromium } = require('playwright');
const { path: ghostPath } = require('ghost-cursor');
const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const outputDir = path.join(rootDir, 'output');
const recordingsDir = path.join(outputDir, 'recordings');
const manifestCandidates = [
  path.join(outputDir, 'timing_manifest.json'),
  path.join(outputDir, 'audio', 'timing_manifest.json'),
];

function readTimings() {
  const manifestPath = manifestCandidates.find((candidate) => fs.existsSync(candidate));
  if (!manifestPath) {
    throw new Error(`Timing manifest not found. Checked: ${manifestCandidates.join(', ')}`);
  }
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
}

function waitDuration(timings, cueId, paddingSec = 0.5) {
  const item = timings[cueId];
  return item ? (item.duration_sec + paddingSec) * 1000 : 2000;
}

function readDemoActions() {
  const raw = process.env.DEMO_ACTIONS;
  if (!raw) {
    return [];
  }
  let actions;
  try {
    actions = JSON.parse(raw);
  } catch (error) {
    throw new Error(`DEMO_ACTIONS must be valid JSON: ${error.message}`);
  }
  if (!Array.isArray(actions) || actions.some((action) => !action || typeof action.selector !== 'string')) {
    throw new Error('DEMO_ACTIONS must be an array of objects with a selector string');
  }
  return actions;
}

async function addDemoEnhancements(page) {
  await page.addInitScript(() => {
    const install = () => {
    const root = document.documentElement;
    const cursor = document.createElement('div');
    cursor.id = '__auto-demo-cursor';
    cursor.style.cssText = `
      position: fixed; left: 0; top: 0; width: 24px; height: 30px;
      pointer-events: none; z-index: 2147483647;
      filter: drop-shadow(0 2px 3px rgba(15, 23, 42, 0.45));
      transition: filter 100ms ease-out;
      will-change: transform;
    `;
    cursor.innerHTML = `
      <svg width="24" height="30" viewBox="0 0 24 30" aria-hidden="true">
        <path d="M2 2L20 15.5L11.5 16.5L7 27L2 2Z" fill="#ffffff" stroke="#0f172a" stroke-width="1.5" stroke-linejoin="round"/>
        <circle cx="6" cy="6" r="2.2" fill="#2563eb" stroke="#ffffff" stroke-width="1"/>
      </svg>
    `;
    root.appendChild(cursor);

    let x = window.innerWidth / 2;
    let y = window.innerHeight / 2;
    let frame;
    const renderCursor = () => {
      frame = undefined;
      cursor.style.transform = `translate3d(${x - 2}px, ${y - 2}px, 0)`;
    };
    window.addEventListener('mousemove', (event) => {
      x = event.clientX;
      y = event.clientY;
      if (!frame) {
        frame = requestAnimationFrame(renderCursor);
      }
    }, { passive: true });
    window.addEventListener('mousedown', () => {
      cursor.style.filter = 'drop-shadow(0 2px 3px rgba(37, 99, 235, 0.8))';
    }, true);
    window.addEventListener('mouseup', () => {
      cursor.style.filter = 'drop-shadow(0 2px 3px rgba(15, 23, 42, 0.45))';
    }, true);
    renderCursor();

    window.addEventListener('click', (event) => {
      const ripple = document.createElement('div');
      ripple.style.cssText = `
        position: fixed; left: ${event.clientX - 18}px; top: ${event.clientY - 18}px;
        width: 36px; height: 36px; border-radius: 50%;
        background: rgba(37, 99, 235, 0.18); border: 2px solid rgba(37, 99, 235, 0.9);
        box-shadow: 0 0 0 8px rgba(37, 99, 235, 0.12);
        pointer-events: none; z-index: 2147483646;
        transition: transform 420ms ease-out, opacity 420ms ease-out;
        transform: scale(0.55); opacity: 1;
      `;
      root.appendChild(ripple);
      requestAnimationFrame(() => {
        ripple.style.transform = 'scale(1.65)';
        ripple.style.opacity = '0';
      });
      setTimeout(() => ripple.remove(), 440);
    }, true);
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', install, { once: true });
    } else {
      install();
    }
  });
}

async function smoothScrollTo(page, target) {
  await target.evaluate((element) => {
    element.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' });
  });
  await page.waitForTimeout(650);
}

function createPlaywrightCursor(page) {
  let currentPoint = { x: 0, y: 0 };
  return {
    async move(target) {
      await smoothScrollTo(page, target);
      const box = await target.boundingBox();
      if (!box) {
        throw new Error('Unable to resolve the target bounding box');
      }
      const destination = {
        x: box.x + (box.width / 2),
        y: box.y + (box.height / 2),
      };
      for (const point of ghostPath(currentPoint, destination)) {
        await page.mouse.move(point.x, point.y);
      }
      currentPoint = destination;
    },
    async click(target) {
      await this.move(target);
      await page.mouse.down();
      await page.mouse.up();
    },
  };
}

async function runProductWorkflow(page, timings, cursor) {
  const demoUrl = process.env.DEMO_URL;
  if (!demoUrl) {
    throw new Error('Set DEMO_URL before running this template, or replace runProductWorkflow with your workflow.');
  }
  await page.goto(demoUrl, { waitUntil: 'domcontentloaded' });
  const actions = readDemoActions();
  if (actions.length === 0) {
    await page.waitForTimeout(waitDuration(timings, 'cue_01'));
    return;
  }
  for (const action of actions) {
    const target = page.locator(action.selector).first();
    await target.waitFor({ state: 'visible' });
    await cursor.click(target);
    if (action.cue) {
      await page.waitForTimeout(waitDuration(timings, action.cue));
    }
  }
}

async function runDemo() {
  const timings = readTimings();
  fs.mkdirSync(recordingsDir, { recursive: true });
  const browser = await chromium.launch({
    headless: process.env.DEMO_HEADLESS === '1',
  });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: {
      dir: recordingsDir,
      size: { width: 1920, height: 1080 },
    },
  });
  const page = await context.newPage();
  const video = page.video();
  const cursor = createPlaywrightCursor(page);
  await addDemoEnhancements(page);
  let workflowError;

  try {
    await runProductWorkflow(page, timings, cursor);
  } catch (error) {
    workflowError = error;
  } finally {
    await context.close();
    await browser.close();
  }

  if (video) {
    const sourcePath = await video.path();
    const pointerPath = path.join(recordingsDir, 'latest_recording.txt');
    fs.writeFileSync(pointerPath, `${sourcePath}\n`, 'utf8');
    console.log(`Recording saved: ${sourcePath}`);
  }
  if (workflowError) {
    throw workflowError;
  }
}

runDemo().catch((error) => {
  console.error('Execution failed:', error);
  process.exit(1);
});
