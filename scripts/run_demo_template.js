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

async function addClickRipple(page) {
  await page.addInitScript(() => {
    window.addEventListener('click', (event) => {
      const ripple = document.createElement('div');
      ripple.style.cssText = `
        position: fixed; left: ${event.clientX - 16}px; top: ${event.clientY - 16}px;
        width: 32px; height: 32px; border-radius: 50%;
        background: rgba(59, 130, 246, 0.3); border: 2px solid #3b82f6;
        pointer-events: none; z-index: 2147483647;
        transition: transform 0.4s ease-out, opacity 0.4s ease-out;
        transform: scale(0.6); opacity: 1;
      `;
      document.body.appendChild(ripple);
      requestAnimationFrame(() => {
        ripple.style.transform = 'scale(2.2)';
        ripple.style.opacity = '0';
      });
      setTimeout(() => ripple.remove(), 400);
    }, true);
  });
}

function createPlaywrightCursor(page) {
  let currentPoint = { x: 0, y: 0 };
  return {
    async move(target) {
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
  await page.waitForTimeout(waitDuration(timings, 'cue_01'));
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
  await addClickRipple(page);
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
