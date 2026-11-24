#!/usr/bin/env node
/**
 * Hands-Free YouTube Studio Short Uploader (Playwright + Persistent Desktop Chrome Profiles)
 *
 * Usage:
 *   node branding/upload_short.mjs --channel ch04 --video "<path/to/master.mp4>" --title "<Title>" --desc "<Description>" [--slug ep04]
 */

import { chromium } from 'playwright';
import path from 'path';
import fs from 'fs';

const ROOT = process.env.SIDEHUSTLES_ROOT || path.resolve(process.cwd());
const STATE_DIR = process.env.STATE_DIR || path.join(ROOT, 'state', 'branding_logs');

const CHANNELS = {
  ch01: {
    id: 'ch01_roblox',
    channelId: process.env.YT_CH01_ID || null,
    profileDir: process.env.YT_PROFILE_DIR || path.join(STATE_DIR, 'profile_ch01'),
    email: process.env.YT_CH01_EMAIL || process.env.YT_EMAIL || '',
    password: process.env.YT_PASS || '',
  },
  ch02: {
    id: 'ch02_sports',
    channelId: process.env.YT_CH02_ID || null,
    profileDir: process.env.YT_PROFILE_DIR || path.join(STATE_DIR, 'profile_ch02'),
    email: process.env.YT_CH02_EMAIL || process.env.YT_EMAIL || '',
    password: process.env.YT_PASS || '',
  },
  ch03: {
    id: 'ch03_whatif',
    channelId: process.env.YT_CH03_ID || null,
    profileDir: process.env.YT_PROFILE_DIR || path.join(STATE_DIR, 'profile_ch03'),
    email: process.env.YT_CH03_EMAIL || process.env.YT_EMAIL || '',
    password: process.env.YT_PASS || '',
  },
  ch04: {
    id: 'ch04_fivestack',
    channelId: process.env.YT_CHANNEL_ID || null,
    profileDir: process.env.YT_PROFILE_DIR || path.join(STATE_DIR, 'profile_ch04'),
    email: process.env.YT_EMAIL || '',
    password: process.env.YT_PASS || '',
  },
};

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--') && i + 1 < argv.length) {
      args[a.slice(2)] = argv[++i];
    }
  }
  return args;
}

function isStudioHost(urlStr) {
  try {
    return new URL(urlStr).hostname === 'studio.youtube.com';
  } catch {
    return false;
  }
}

async function handleReauthIfPresent(context, page, job) {
  const hasVerify = await page.evaluate(() => {
    const dlgs = [...document.querySelectorAll('tp-yt-paper-dialog')];
    return dlgs.some(d => (d.innerText || '').includes("Verify that it's you") && d.style.display !== 'none');
  });
  if (!hasVerify) return false;

  console.log(`[${job.id}] "Verify that it's you" detected! Clicking Next to open reauth popup...`);
  const [popup] = await Promise.all([
    context.waitForEvent('page', { timeout: 15000 }).catch(() => null),
    page.evaluate(() => {
      const dlgs = [...document.querySelectorAll('tp-yt-paper-dialog')];
      const v = dlgs.find(d => (d.innerText || '').includes("Verify that it's you"));
      const btn = v ? [...v.querySelectorAll('ytcp-button, button')].find(b => (b.innerText || '').includes('Next')) : null;
      if (btn) btn.click();
    }),
  ]);

  if (popup) {
    await popup.waitForLoadState('domcontentloaded').catch(() => {});
    await popup.waitForTimeout(2500);

    const passBox = popup.locator('input[type="password"], input[name="Passwd"]').first();
    if (await passBox.isVisible({ timeout: 5000 }).catch(() => false)) {
      await passBox.fill(job.password);
      await popup.keyboard.press('Enter');
    }

    for (let i = 0; i < 60; i++) {
      if (popup.isClosed()) break;
      const purl = popup.url();
      if (purl.includes('studio.youtube.com/reauth')) {
        const html = await popup.content().catch(() => '');
        const m = html.match(/postMessage\('([^']+)'/);
        if (m) {
          const rawMsg = m[1].replace(/\\x5b/g, '[').replace(/\\x5d/g, ']').replace(/\\x22/g, '"');
          await page.evaluate(msg => window.postMessage(msg, window.location.origin), rawMsg);
          await popup.close().catch(() => {});
          break;
        }
      }
      await page.waitForTimeout(2000);
    }
    await page.waitForTimeout(3000);
    return true;
  }
  return false;
}

async function waitForAllByteUploadsAndProcessing(page, job, maxSeconds = 600) {
  let lastProgress = '';
  const loops = Math.ceil(maxSeconds / 4);
  for (let i = 0; i < loops; i++) {
    const state = await page.evaluate(() => {
      const bodyTxt = document.body ? (document.body.innerText || '') : '';
      const pct1 = bodyTxt.match(/Uploading\s+(?!100%)\d+%[^\n]*/i);
      const pct2 = bodyTxt.match(/(?!100%\s*uploaded)\b\d{1,2}%\s*uploaded[^\n]*/i);
      const tray = bodyTxt.match(/Uploading\s+\d+\s+of\s+\d+[^\n]*/i);
      const keepOpen = /Keep this browser tab open until uploading is complete|Video uploading/i.test(bodyTxt);
      const stillUploading = Boolean(pct1 || pct2 || tray || keepOpen);
      const proc = bodyTxt.match(/Processing\s+(?:up\s+to\s+HD|HD|SD|\d+%)[^\n]*/i) || bodyTxt.match(/Checks\s+[^\n]*/i);
      const label = (pct1 && pct1[0]) || (pct2 && pct2[0]) || (tray && tray[0]) || (keepOpen ? 'Video uploading modal active' : (proc ? proc[0] : 'Upload 100% complete'));
      return { stillUploading, label: label.trim() };
    });
    if (state.label !== lastProgress) {
      console.log(`[${job.id}] Transfer status: ${state.label}`);
      lastProgress = state.label;
    }
    if (!state.stillUploading) {
      return;
    }
    await page.waitForTimeout(4000);
  }
  throw new Error(`[${job.id}] Timed out after ${maxSeconds}s waiting for byte upload to hit 100%`);
}

async function uploadShort(job) {
  if (!fs.existsSync(job.videoPath)) {
    throw new Error(`Video file does not exist: ${job.videoPath}`);
  }
  fs.mkdirSync(STATE_DIR, { recursive: true });

  console.log(`\n=== Starting Upload for ${job.id} (${job.videoTitle}) ===`);
  const context = await chromium.launchPersistentContext(job.profileDir, {
    executablePath: process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: false,
    ignoreDefaultArgs: ['--enable-automation'],
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run',
      '--no-default-browser-check',
    ],
    viewport: { width: 1440, height: 920 },
  });

  try {
    const page = context.pages()[0] || await context.newPage();
    const startUrl = job.channelId
      ? `https://studio.youtube.com/channel/${job.channelId}/videos/upload?d=ud`
      : 'https://studio.youtube.com';
    await page.goto(startUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(4500);
    console.log(`[${job.id}] Initial URL: ${page.url()}`);

    if (!isStudioHost(page.url())) {
      console.log(`[${job.id}] Google sign-in required for ${job.email}...`);
      const emailBox = page.locator('#identifierId, input[type="email"]').first();
      if (await emailBox.isVisible({ timeout: 8000 }).catch(() => false)) {
        await emailBox.fill(job.email);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(2500);
      }
      const passBox = page.locator('input[type="password"], input[name="Passwd"]').first();
      if (await passBox.isVisible({ timeout: 12000 }).catch(() => false)) {
        await passBox.fill(job.password);
        await page.keyboard.press('Enter');
      }
      console.log(`[${job.id}] Waiting for studio.youtube.com (approve 2-Step Verification tap on device if prompted)...`);
      await page.waitForURL(u => isStudioHost(u.toString()), { timeout: 180000 });
      await page.waitForTimeout(5000);
    }

    await handleReauthIfPresent(context, page, job);

    // Ensure upload modal is open
    if ((await page.locator('input[type="file"]').count()) === 0) {
      const chMatch = page.url().match(/channel\/(UC[a-zA-Z0-9_-]+)/);
      const cid = job.channelId || (chMatch ? chMatch[1] : null);
      if (cid) {
        await page.goto(`https://studio.youtube.com/channel/${cid}/videos/upload?d=ud`, {
          waitUntil: 'domcontentloaded',
          timeout: 45000,
        });
        await page.waitForTimeout(5000);
        await handleReauthIfPresent(context, page, job);
      }
    }

    if ((await page.locator('input[type="file"]').count()) === 0) {
      await page.evaluate(() => {
        const btn = document.querySelector('#upload-icon, #upload-button, #create-icon');
        if (btn) btn.click();
      });
      await page.waitForTimeout(2000);
      await page.evaluate(() => {
        const item = document.querySelector('#text-item-0') || [...document.querySelectorAll('tp-yt-paper-item')].find(el => (el.innerText || '').includes('Upload'));
        if (item) item.click();
      });
      await page.waitForTimeout(3000);
      await handleReauthIfPresent(context, page, job);
    }

    const uploadInput = page.locator('ytcp-uploads-file-picker input[type="file"], input[type="file"]').first();
    await uploadInput.setInputFiles(job.videoPath);
    console.log(`[${job.id}] Attached ${path.basename(job.videoPath)} (${(fs.statSync(job.videoPath).size / 1048576).toFixed(2)} MB)!`);
    await page.waitForTimeout(5000);
    await handleReauthIfPresent(context, page, job);

    const titleBox = page.locator('ytcp-video-title #textbox[contenteditable="true"], #title-textarea #textbox[contenteditable="true"]').first();
    await titleBox.waitFor({ state: 'visible', timeout: 45000 });
    await page.waitForTimeout(1500);
    await titleBox.fill(job.videoTitle);
    await page.waitForTimeout(800);

    const descInput = page.locator('ytcp-video-description #textbox[contenteditable="true"], #description-textarea #textbox[contenteditable="true"]').first();
    if (await descInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await descInput.fill(job.videoDesc);
      await page.waitForTimeout(800);
    }

    await page.evaluate(() => {
      const r = document.querySelector('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]');
      if (r) {
        r.scrollIntoView({ block: 'center' });
        r.click();
      }
    });
    await page.waitForTimeout(1500);

    // Check if we are in the wizard modal (#next-button) or resumed Video details page (#save)
    const isWizard = await page.evaluate(() => Boolean(document.querySelector('#next-button')?.offsetParent));
    if (isWizard) {
      for (let i = 0; i < 3; i++) {
        await page.evaluate(() => document.querySelector('#next-button')?.click());
        await page.waitForTimeout(2000);
      }
      await page.evaluate(() => {
        const p = document.querySelector('tp-yt-paper-radio-button[name="PUBLIC"]');
        if (p) p.click();
      });
      await page.waitForTimeout(2000);
    } else {
      // Resumed Video details page: click Save if enabled, and ensure Visibility is Public/Pending-Public
      await page.evaluate(() => {
        const saveBtn = document.querySelector('#save');
        if (saveBtn && saveBtn.getAttribute('aria-disabled') !== 'true') saveBtn.click();
      });
      await page.waitForTimeout(2000);
    }

    let shortLink = null;
    for (let attempt = 0; attempt < 20; attempt++) {
      await handleReauthIfPresent(context, page, job);
      shortLink = await page.evaluate(() => {
        const a = [...document.querySelectorAll('a')].find(el => (el.href || '').includes('youtube.com/shorts/') || (el.href || '').includes('youtu.be/'));
        if (a) return a.href;
        const m = location.href.match(/\/video\/([a-zA-Z0-9_-]+)\//);
        return m ? `https://youtube.com/shorts/${m[1]}` : null;
      });
      if (shortLink) break;
      await page.waitForTimeout(1500);
    }
    console.log(`[${job.id}] Short Link: ${shortLink}`);

    // If wizard #done-button is present, click Publish first or wait for byte upload
    if (isWizard) {
      for (let attempt = 0; attempt < 40; attempt++) {
        await handleReauthIfPresent(context, page, job);
        const clicked = await page.evaluate(() => {
          const d = document.querySelector('#done-button');
          if (d && d.getAttribute('aria-disabled') !== 'true') {
            d.click();
            return true;
          }
          return false;
        });
        if (clicked) {
          console.log(`[${job.id}] Clicked Publish (#done-button)!`);
          break;
        }
        await page.waitForTimeout(1500);
      }
      await page.waitForTimeout(3000);
      await page.evaluate(() => {
        const btn = [...document.querySelectorAll('ytcp-button, button')].find(b => (b.innerText || '').includes('Publish anyway'));
        if (btn) btn.click();
      });
    }

    // CRITICAL: Hold browser open until BOTH wizard modal AND bottom-right multi-progress tray finish 100% byte upload!
    await waitForAllByteUploadsAndProcessing(page, job, 600);

    // Navigate to Channel Shorts tab to confirm Public/Processing status on the row
    if (job.channelId) {
      await page.goto(`https://studio.youtube.com/channel/${job.channelId}/videos/short`, {
        waitUntil: 'domcontentloaded',
        timeout: 45000,
      });
      await page.waitForTimeout(6000);
    }

    const shotFile = path.join(STATE_DIR, `${job.id}_${job.slug}_published.png`);
    await page.screenshot({ path: shotFile }).catch(() => {});
    console.log(`[${job.id}] Screenshot saved: ${shotFile}`);
    console.log(`[${job.id}] DONE! Published Short URL: ${shortLink}`);
    return shortLink;
  } finally {
    await context.close();
  }
}

async function main() {
  const args = parseArgs(process.argv);
  const chKey = args.channel || 'ch04';
  const base = CHANNELS[chKey];
  if (!base) {
    throw new Error(`Unknown --channel "${chKey}". Choose one of: ${Object.keys(CHANNELS).join(', ')}`);
  }
  if (!args.video || !args.title) {
    throw new Error('Required arguments: --channel <ch01..ch04> --video <path> --title "<Title>" [--desc "<Desc>"] [--slug <epXX>]');
  }
  const job = {
    ...base,
    videoPath: path.resolve(args.video),
    videoTitle: args.title,
    videoDesc: args.desc || '',
    slug: args.slug || path.basename(path.dirname(path.resolve(args.video))),
  };
  await uploadShort(job);
  process.exit(0);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
