import fs from "fs";
import path from "path";
import readline from "readline";
import { fileURLToPath } from "url";
import puppeteer from "puppeteer";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const authPath =
  process.env.INVESTOPEDIA_AUTH_FILE || path.join(__dirname, "auth.json");

const email = process.argv[2] || process.env.INVESTOPEDIA_EMAIL;
if (!email) {
  console.error("Usage: node auth.js <email>");
  console.error("Or set INVESTOPEDIA_EMAIL.");
  process.exit(2);
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const ask = (question) =>
  new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    rl.question(question, (answer) => {
      rl.close();
      resolve(answer.trim());
    });
  });

let authData = null;
let fallbackAccessToken = null;

const saveAuth = (data) => {
  const output = {
    ...data,
    obtained_at: Math.floor(Date.now() / 1000),
  };
  fs.writeFileSync(authPath, `${JSON.stringify(output, null, 2)}\n`);
  authData = output;
};

const launchArgs = [];
if (process.env.PUPPETEER_NO_SANDBOX === "1") {
  launchArgs.push("--no-sandbox", "--disable-setuid-sandbox");
}
if (process.env.PUPPETEER_DISABLE_DEV_SHM === "1") {
  launchArgs.push("--disable-dev-shm-usage");
}

const browser = await puppeteer.launch({
  headless: process.env.INVESTOPEDIA_HEADFUL !== "1",
  args: launchArgs,
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1366, height: 900 });

  page.on("response", async (response) => {
    if (!response.url().includes("/protocol/openid-connect/token")) {
      return;
    }

    try {
      const data = await response.json();
      if (data?.access_token) {
        saveAuth(data);
      }
    } catch {
      // Ignore non-JSON responses from unrelated auth requests.
    }
  });

  page.on("request", (request) => {
    if (!request.url().includes("/simulator/graphql")) {
      return;
    }

    const authorization = request.headers().authorization;
    if (authorization?.toLowerCase().startsWith("bearer ")) {
      fallbackAccessToken = authorization.slice(7).trim();
    }
  });

  await page.goto("https://www.investopedia.com/simulator/portfolio", {
    waitUntil: "domcontentloaded",
    timeout: 30000,
  });

  // In the current Keycloak flow the initial page can be registration-oriented
  // and expose a "Sign In Now" link. Prefer that before filling an email field.
  const signInCandidates = await page.$$("a, button");
  for (const candidate of signInCandidates) {
    const label = await candidate.evaluate((element) =>
      (element.innerText || element.textContent || "").trim().toLowerCase()
    );
    if (label === "sign in now" || label === "sign in" || label === "log in") {
      await candidate.click();
      await sleep(500);
      break;
    }
  }

  const emailSelector =
    'input#username, input[name="username"], input[type="email"]';
  const emailField = await page.waitForSelector(emailSelector, {
    timeout: 15000,
  });

  await emailField.click({ clickCount: 3 });
  await emailField.type(email);

  const submitSelector =
    'button[type="submit"], input[type="submit"], input#login, button#login';
  const submit = await page.$(submitSelector);
  if (submit) {
    await submit.click();
  } else {
    await emailField.press("Enter");
  }

  await sleep(1500);

  console.log("");
  console.log(`Investopedia sent a passwordless sign-in email to ${email}.`);
  console.log("Paste the COMPLETE sign-in link from that email below.");
  console.log("Chromium remains headless; this manual step is only needed for fresh auth.");
  console.log("");

  const magicLink =
    process.env.INVESTOPEDIA_MAGIC_LINK || (await ask("Magic link: "));

  if (!/^https?:\/\//i.test(magicLink)) {
    throw new Error("The supplied magic link is not an http(s) URL.");
  }

  await page.goto(magicLink, {
    waitUntil: "networkidle2",
    timeout: 45000,
  });

  // Make sure the simulator app initializes after the email-link callback.
  if (!page.url().includes("/simulator")) {
    await page.goto("https://www.investopedia.com/simulator/portfolio", {
      waitUntil: "networkidle2",
      timeout: 45000,
    });
  }

  for (let i = 0; i < 40 && !authData; i += 1) {
    await sleep(500);
  }

  if (!authData && fallbackAccessToken) {
    saveAuth({ access_token: fallbackAccessToken });
    console.warn(
      "Captured an access token but no refresh token. The Python client will " +
        "work until the access token expires; re-run auth.js when necessary."
    );
  }

  if (!authData) {
    throw new Error(
      "Login completed without exposing an Investopedia OIDC/bearer token."
    );
  }

  console.log(`Authentication saved to ${authPath}.`);
  if (authData.refresh_token) {
    console.log("Refresh token captured; later runs can refresh headlessly.");
  }
} finally {
  await browser.close();
}
