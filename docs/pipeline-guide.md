# Beer's Fantasy Baseball Tool — How It Works

This guide explains what you personally need to do, what runs on its own, and what you never have to touch.

---

## Quick Reference

| | What | How often |
|---|---|---|
| **You do this** | Load historical data | Once (or when data looks wrong) |
| **Automatic** | Daily stats update | Every day at 8am EST |
| **Just use it** | The website | Whenever you want |

---

## Part 1: The Website

**Live URL:** https://beers-baseball-tool-fantasy.vercel.app

### What each tab does

| Tab | What it shows |
|-----|--------------|
| **Daily** | Today's hottest and coldest players by ELO change |
| **Leaderboard** | All batters and pitchers ranked by ELO |
| **Talent** | 9-dimension talent ratings with radar charts |
| **Team ELO** | All 30 MLB teams ranked by team strength (click any team for ELO chart + game log) |
| **Matchup** | Search any batter vs pitcher — see predicted outcome |
| **Fantasy** | Your roster is pre-loaded — pick a week and click Project Week |
| **Export** | Download a PDF report of your weekly projections |
| **Guide** | Explanation of how the ELO system works |

### Using the Fantasy tab

1. Go to the **Fantasy** tab
2. Your roster is pre-loaded — if your team has changed, paste the new roster and click **Parse Roster**
3. Select the week you want to project
4. Click **Project Week**

**Roster format** — full player names, dash-separated:

```
Hunter Goodman - Col - (C/DH)
Aaron Judge - NYY - (OF)
Zack Wheeler - PHI - (SP)
Edwin Diaz - NYM - (RP)
BENCH
Mike Trout - LAA - (DH/OF)
```

- Team names are not case-sensitive (`NYY`, `nyy`, `Nyy` all work)
- Positions go in parentheses — multiple positions separated by `/`
- Section headers (`BATTERS`, `PITCHERS`, `BENCH`, `IL`) are automatically skipped
- Your last-used roster is remembered across browser sessions (saved in localStorage)

---

## Part 2: Loading Historical Data (you run this)

This is the only command you ever need to run yourself. You do it once to populate the database, and again if data ever looks wrong or missing.

### When to run it

- First time setting up
- After the 2025→2026 season reset (to reload all history clean)
- If player charts start at the wrong ELO (e.g. 1600 instead of 1500)

### How to run it

Open **PowerShell** (search for it in the Start menu), navigate to the project folder, and run:

```powershell
cd C:\Users\Jake\Documents\Python\Baseball\fantasy-matchup-predictor

# Step 1: Load full 2025 season
C:\python314\python.exe -m scripts.bulk_load --end-date 2025-09-28 --fresh

# Step 2: Load 2026 season from opening day onward
C:\python314\python.exe -m scripts.bulk_load --start-date 2026-03-18

# Step 3: Rebuild team ELO from scratch
C:\python314\python.exe -m scripts.backfill_team_elo --fresh
```

> **The `--fresh` flag** wipes any existing data and starts clean. Always use it for the 2025 season load — running without it when data already exists can corrupt player charts.
>
> **The `--start-date` flag** lets you resume from a specific date without wiping existing data — use this for the 2026 season load so you don't have to re-download 2025.

### What it does

- Downloads every MLB plate appearance from Statcast (via Baseball Reference)
- Calculates each player's ELO rating, game by game
- Computes daily chart data (open/high/low/close ELO per player)
- Saves everything to the database

### How long it takes

About **5–15 minutes** depending on your internet speed. You'll see progress in the terminal:

```
10:12:01 Fetching Statcast: 2025-03-27 → 2025-03-31
10:12:15   48,291 regular season pitches
10:12:15 Fetching Statcast: 2025-04-01 → 2025-04-30
...
10:18:43 BULK LOAD COMPLETE
  Total PAs in DB: 183,092
  Latest date: 2025-09-28
  Players with ELO: 1,469
```

### After it finishes

The website will automatically show the new data — no other steps needed.

---

## Part 3: Daily Updates (automatic — nothing to do)

Every day at **8:00 AM EST**, GitHub automatically runs the daily update. You don't need to do anything.

### What it updates

- Player ELO ratings (based on last night's games)
- Team ELO ratings
- Weekly schedule and probable pitchers
- Player stat projections from FanGraphs
- Speed ELO ratings (SB/CS totals from MLB Stats API; resets to 1500 each season, or 1550 for players with >25 SB the prior season)

### How to check if it ran

1. Go to your GitHub repo: https://github.com/boerface16/Fantasy_ELO_Tool
2. Click the **Actions** tab at the top
3. You'll see a list of recent runs — a green checkmark means it succeeded

### If it failed (red X)

1. Click the failed run to see what went wrong
2. Most failures are temporary (Baseball Reference or MLB API was down)
3. To re-run it manually: click **"Re-run all jobs"** button on that page

### Manually trigger for a specific date

If a day was missed, you can run it for any past date:

1. Go to the **Actions** tab on GitHub
2. Click **"Daily ELO Update"** in the left sidebar
3. Click **"Run workflow"**
4. Enter the date (e.g. `2025-09-15`) and click the green **"Run workflow"** button

---

## Part 4: The Website Stays Live Automatically

The website has two parts, both of which run 24/7 without you doing anything.

### Frontend (Vercel)
- The website pages you see at `beers-baseball-tool-fantasy.vercel.app`
- Auto-updates whenever code is pushed to GitHub
- Free tier, no maintenance needed

### Backend (Render)
- The server that fetches data from the database and sends it to the website
- Auto-updates whenever code is pushed to GitHub
- **Note:** Render may take 30–60 seconds to respond after being idle — this is normal on the free tier

### If the website is down

1. Check **Render**: go to your Render dashboard and look for the `fantasy-matchup-api` service — it should say "Live"
2. Check **Vercel**: go to your Vercel dashboard — deployments should show "Ready"
3. Both platforms send email alerts if something goes down

---

## Part 5: Troubleshooting

### Website shows no data / blank pages

**Most likely:** Render is starting up (takes up to 60 seconds on first request after being idle). Wait a minute and refresh.

**If still blank:** Check the Render dashboard to make sure the service is running.

### Data looks stale or outdated

The daily update runs at 8am EST. If it's past 9am and data hasn't updated:

1. Check the GitHub Actions tab for a failed run
2. Manually trigger the workflow (see Part 3)

### Player chart starts at 1600 instead of 1500

This means the historical data was loaded twice and got corrupted. Fix it by re-running both loads from scratch:

```powershell
C:\python314\python.exe -m scripts.bulk_load --end-date 2025-09-28 --fresh
C:\python314\python.exe -m scripts.bulk_load --start-date 2026-03-18
C:\python314\python.exe -m scripts.backfill_team_elo --fresh
```

### Roster not parsing correctly

Make sure your roster format uses dashes and parentheses:
```
Player Name - TEAM - (POSITION)
```

Team abbreviations must be standard MLB codes (`NYY`, `LAD`, `BOS`, etc.) — case doesn't matter.

### Error: "No module named X"

Run this once to install all dependencies on Python 3.14:

```powershell
C:\python314\python.exe -m pip install -r requirements.txt
```

### bulk_load fails with "connection refused" or database error

Check that your `.env` file in the project folder has these three lines filled in:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
DATABASE_URL=postgresql://postgres.xxxxx:PASSWORD@host:5432/postgres
```

If you're not sure where to find these, check the Supabase dashboard under **Settings → API** (for `SUPABASE_URL` and `SUPABASE_KEY`) and **Settings → Database → Connection string** (for `DATABASE_URL`).

To check website changes!
2 terminals
uvicorn src.api.main:app --reload --port 8000
npm run dev
