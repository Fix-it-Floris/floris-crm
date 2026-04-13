# Fix-it Floris — Lead CRM · Complete Setup Guide

This guide covers everything in one place, in the correct order.
Follow it top to bottom and you'll have the full system running in about 60 minutes.

---

## What you're building

| Component | What it does |
|---|---|
| **Notion database** | Your CRM — every lead, status, email draft, and note lives here |
| **GitHub Actions** | Runs three automated jobs on a schedule, for free |
| **Daily leads** (weekdays 09:00) | Finds 5 new European companies → adds to Notion → emails you a digest |
| **Follow-up checker** (weekdays 09:05) | Flags contacts with no reply after 14 days → drafts follow-up email |
| **Weekly digest** (Fridays 09:10) | Emails pipeline stats: response rate, success rate, breakdown |
| **GitHub Pages dashboard** | Live web dashboard at `your-username.github.io/floris-crm` |

**Tone learning:** Every time Claude drafts a cold email, it reads your 3 most recently
edited emails from Notion and matches your style. The more you edit, the better the drafts get.

---

## Files in this repository

```
floris-crm/
├── index.html                          # Live dashboard (hosted on GitHub Pages)
├── notion-proxy-worker.js              # Cloudflare Worker script (copy-paste once)
├── README.md                           # This file
├── scripts/
│   ├── notion_client.py                # Notion API helper (shared by all scripts)
│   ├── email_utils.py                  # Email sending helper (shared by all scripts)
│   ├── daily_leads.py                  # Job 1: lead finder
│   ├── followup_checker.py             # Job 2: follow-up flagging
│   └── weekly_digest.py               # Job 3: Friday summary
└── .github/
    └── workflows/
        └── crm.yml                     # GitHub Actions schedule
```

---

## Estimated costs

| Service | Cost |
|---|---|
| GitHub (repo + Actions + Pages) | Free |
| Notion | Free tier is sufficient |
| Anthropic API | ~€1.50–3 / month |
| Cloudflare Workers | Free (100,000 requests/day) |
| Gmail | Free |

---

## Step 1 — Create a GitHub account and repository

1. Go to https://github.com and sign up (free) if you don't have an account
2. Click the **+** icon (top right) → **New repository**
3. Name it `floris-crm` · Set visibility to **Private** · Click **Create repository**

**Upload the script files:**

4. In your new repository click **Add file → Upload files**
5. Before uploading, create the `scripts/` folder:
   - Click **Add file → Create new file**
   - Type `scripts/placeholder.txt` in the name field and add any text
   - Click **Commit new file** (you can delete this file later)
6. Now upload all five `.py` files into the `scripts/` folder

**Create the GitHub Actions workflow:**

7. Click **Add file → Create new file**
8. In the filename field type exactly: `.github/workflows/crm.yml`
   (GitHub will create the folders automatically as you type the slashes)
9. Paste the full contents of `crm.yml` into the editor
10. Click **Commit new file**

**Add the dashboard:**

11. Upload `index.html` to the root of the repository (not inside `scripts/`)

---

## Step 2 — Set up Notion

### 2a. Create the CRM database

1. In Notion, create a new page and choose **Table** as the content type
2. Name the database `Floris Lead CRM`
3. Add the following columns — the name and type must match exactly:

| Column name | Type | Notes |
|---|---|---|
| `Company` | Title | Already exists as the default first column |
| `Country` | Text | |
| `City` | Text | |
| `Sector` | Select | Add options: `Cleantech`, `Industrial automation`, `Consumer hardware` |
| `What they do` | Text | |
| `Why Floris fits` | Text | |
| `Contact role` | Text | |
| `LinkedIn tip` | Text | |
| `Fit tags` | Multi-select | Options are created automatically as leads are added |
| `Fit level` | Select | Add options: `Strong`, `Good`, `Interesting` |
| `Status` | Select | See options below — spelling matters |
| `Date suggested` | Date | |
| `Date contacted` | Date | You fill this in manually after sending an email |
| `Email draft` | Text | Claude's generated draft |
| `Email edited` | Text | Your edited version — this is what trains Claude's tone |
| `Follow-up draft` | Text | Auto-generated after 14 days of no reply |
| `Notes` | Text | Free text for anything you want to remember |

**Status select options — add these exactly (copy-paste to avoid typos):**
- `Suggested`
- `Contacted`
- `Follow-up needed`
- `Interested`
- `Not interested`
- `Rejected – do not contact`
- `Archived`

### 2b. Add filtered views to your database (free alternative to a dashboard page)

Instead of a separate dashboard page (which requires Notion paid), add multiple views
directly to your database. Each view is a tab across the top — free on all plans.

1. In your database, click the **+** icon next to the existing view tab
2. Add these views one by one:

| View name | Type | Filter |
|---|---|---|
| All leads | Table | No filter |
| To contact | Table | Status = `Suggested` |
| Active | Table | Status = `Contacted` OR `Follow-up needed` |
| Follow-up | Table | Status = `Follow-up needed` |
| Interested | Table | Status = `Interested` |
| Closed | Table | Status = `Not interested` OR `Rejected – do not contact` |

### 2c. Create a Notion integration token

1. Go to https://www.notion.so/my-integrations
2. Click **+ New integration**
3. Name it `Floris CRM Bot` · Select your workspace · Click **Submit**
4. Copy the **Internal Integration Token** — it starts with `secret_...`
   (save this somewhere safe, you'll need it in Steps 5 and 6)
5. Go back to your `Floris Lead CRM` database
6. Click the **...** menu (top right of the database) → **Add connections**
7. Select `Floris CRM Bot` and confirm

### 2d. Find your Database ID

1. Open your `Floris Lead CRM` database in Notion
2. Look at the URL in your browser — it looks like:
   `https://www.notion.so/yourworkspace/XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX?v=...`
3. The 32-character string between the last `/` and `?v=` is your Database ID
   (save this, you'll need it in Steps 5 and 6)

---

## Step 3 — Get a Gmail App Password

The scripts send emails from your Gmail account. Gmail requires an App Password
(separate from your regular password) for automated tools.

1. Go to https://myaccount.google.com
2. Click **Security** in the left menu
3. Under "How you sign in to Google", enable **2-Step Verification** if not already on
4. In the search bar at the top, search for **App passwords**
5. Create a new app password, name it `Floris CRM`
6. Google shows you a 16-character password — copy it immediately
   (it's only shown once)

---

## Step 4 — Get an Anthropic API key

1. Go to https://console.anthropic.com and sign up or log in
2. Click **API Keys** in the left menu → **Create Key**
3. Copy the key — it starts with `sk-ant-...`
4. Click **Billing** and add a small amount of credit (€5–10 is plenty for months of use)

---

## Step 5 — Add secrets to GitHub

Secrets are how GitHub Actions accesses your credentials without storing them in code.

1. In your `floris-crm` repository, click **Settings** (top menu)
2. In the left sidebar click **Secrets and variables → Actions**
3. Click **New repository secret** for each of the following:

| Secret name | Value to paste |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic key (`sk-ant-...`) |
| `NOTION_TOKEN` | Your Notion integration token (`secret_...`) |
| `NOTION_DATABASE_ID` | Your 32-character database ID |
| `EMAIL_SENDER` | Your Gmail address (e.g. `you@gmail.com`) |
| `EMAIL_PASSWORD` | The 16-character Gmail App Password |
| `EMAIL_RECIPIENT` | Where to send emails (can be the same Gmail address) |
| `STOP_SERVICE` | `false` |

---

## Step 6 — Set up the live dashboard

The dashboard is a webpage hosted for free on GitHub Pages.
Because browsers can't call the Notion API directly (a security restriction called CORS),
you need a free Cloudflare Worker that acts as a middleman.

### 6a. Deploy the Cloudflare Worker proxy

1. Go to https://workers.cloudflare.com and sign up free
2. Click **Create a Worker**
3. Delete all default code in the editor
4. Paste the full contents of `notion-proxy-worker.js`
5. Click **Save and deploy**
6. Go to your Worker's **Settings → Variables**
7. Click **Add variable**:
   - Variable name: `NOTION_TOKEN`
   - Value: your Notion integration token (`secret_...`)
   - Click **Encrypt** → **Save**
8. Copy your Worker's URL — it looks like:
   `https://your-worker-name.your-subdomain.workers.dev`

### 6b. Configure the dashboard file

Open `index.html` in a text editor and find the CONFIG section near the bottom
of the file (search for `YOUR_NOTION_TOKEN_HERE`):

```javascript
const NOTION_TOKEN = "YOUR_NOTION_TOKEN_HERE";
const DATABASE_ID  = "YOUR_DATABASE_ID_HERE";
```

Replace the values:
- `NOTION_TOKEN`: paste your Notion token (`secret_...`) directly here
  *(this is fine for a personal private tool — alternatively leave it blank
  and route all calls through the Worker instead)*
- `DATABASE_ID`: your 32-character database ID

Save the file and re-upload it to your GitHub repository (replacing the old version).

### 6c. Enable GitHub Pages

1. In your `floris-crm` repository, click **Settings**
2. In the left sidebar click **Pages**
3. Under **Source**, select **Deploy from a branch**
4. Set branch to `main` and folder to `/ (root)`
5. Click **Save**
6. Wait about 60 seconds, then your dashboard is live at:
   `https://YOUR-GITHUB-USERNAME.github.io/floris-crm`

Bookmark this URL — it's your live pipeline dashboard.

**Privacy note:** GitHub Pages on a free account is publicly accessible.
The URL is not guessable, so for personal use this is fine. If you want a
password, open `index.html`, find the `init()` function, and add this at the top:

```javascript
const pwd = localStorage.getItem("crm_auth");
if (pwd !== "your-chosen-password") {
  const input = prompt("Password:");
  if (input !== "your-chosen-password") {
    document.body.innerHTML = "<p style='padding:40px'>Access denied.</p>";
    return;
  }
  localStorage.setItem("crm_auth", input);
}
```

---

## Step 7 — Test everything manually

Run each job once before waiting for the schedule to kick in.

1. In your repository click the **Actions** tab
2. Click **Floris CRM Automation** in the left list
3. Click **Run workflow** (top right) → select a job → **Run workflow**

**Test in this order:**

| Job to run | Expected result |
|---|---|
| `daily_leads` | 5 companies appear in your Notion database + email arrives |
| `followup_checker` | Prints "No follow-ups needed" (database is brand new) |
| `weekly_digest` | Weekly summary email arrives with stats |

If any job shows a red ✗, click into it to see the error log.
Most errors are a mistyped secret or a wrong Notion column name.

After `daily_leads` runs successfully, open your GitHub Pages dashboard URL
and confirm the leads appear.

---

## Your daily workflow

Once everything is running, your routine is:

1. **09:00 — email arrives** with 5 new leads
2. **Open each lead in Notion** via the link in the email
3. **Read the cold email draft** in the `Email draft` field
4. **Edit it** in the `Email edited` field to match your voice
   *(this trains Claude — the more you edit, the better future drafts get)*
5. **Copy the edited version** → paste into Gmail → send
6. **Set `Status` to `Contacted`** and fill in `Date contacted`
7. When they reply → update `Status` to `Interested`, `Not interested`, or `Rejected – do not contact`
8. After 14 days with no reply → follow-up alert arrives automatically with a draft

---

## Stopping and restarting

**To stop all automation:**
Go to GitHub → your repository → **Settings → Secrets and variables → Actions**
→ click `STOP_SERVICE` → **Update** → change value to `true` → Save

**To restart:**
Change `STOP_SERVICE` back to `false`

The scripts check this value every time they run. No need to delete anything.

---

## Adjusting the follow-up window

Default is 14 days. To change it, open `.github/workflows/crm.yml` in your
repository, find this line under the `followup-checker` job, and update the number:

```yaml
FOLLOWUP_DAYS: "14"
```

---

## Timezone note

The schedule runs at 07:00 UTC:
- **Summer (CEST, UTC+2, late March – late October):** arrives at 09:00 Amsterdam ✓
- **Winter (CET, UTC+1, late October – late March):** arrives at 08:00 Amsterdam

For exact 09:00 in winter, open `crm.yml` and change the three cron lines from
`0 7`, `5 7`, `10 7` to `0 8`, `5 8`, `10 8` for the winter months.
Change them back in spring.
