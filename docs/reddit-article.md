# Reddit Article — Fantasy Matchup Predictor Introduction

> Drafted for r/fantasybaseball. Includes full math appendix for interested readers.

---

## I Built a Multi-Dimensional ELO Rating System for Fantasy Baseball -- Here's How It Works (and Why I Think It's Better Than Standard Projections)

Most fantasy baseball advice is backward-looking. You're reading about last week's hot hitters, last month's strikeout rates, or last year's statcast numbers. By the time that information reaches a rankings column, the player has already cooled off, gotten hurt, or changed their approach. You're reacting to history instead of reading the present.

I wanted something different. Something that updates in real time, game by game, plate appearance by plate appearance -- and weights recent performance more heavily than stale sample sizes. So I built a web app that rates every MLB player across multiple skill dimensions using an ELO rating system, the same framework that powers chess rankings. I'm calling it the Fantasy Matchup Predictor, and I'd love this community's feedback on it.

---

## What Is ELO and Why Does It Work for Baseball?

If you've never heard of ELO: it's a rating system originally designed for chess. Every player starts at 1500. When you beat a strong opponent, your rating goes up a lot. When you lose to a weak opponent, your rating drops a lot. The key insight is that your rating adjusts based on *expected* outcome -- so beating a 2000-rated player when you're rated 1400 is a massive signal, but expected outcomes barely move the needle.

Baseball translates surprisingly well. Instead of players playing each other, a batter is "playing" the distribution of outcomes from any given plate appearance, matched against the opposing pitcher's relevant dimension. Strikeout against a dominant closer? Small drop. Walk against an ace with great command? Meaningful signal.

The core update formula after every plate appearance is:

```
Delta = K x scale x |weight| x (actual - expected) x reliability
```

Where:
- **K** is the learning rate for that dimension
- **scale** is an amplitude multiplier
- **weight** is how much this event type matters (e.g. HR = +1.0 for Power, popup = -0.8)
- **actual** is 1.0 if the event was positive, 0.0 if negative
- **expected** is the classic ELO win probability: `1 / (1 + 10^((opponent_elo - player_elo) / divisor))`
- **reliability** ramps from 0.3 to 1.0 as sample size grows

That last term -- reliability -- is critical. Early in the season, a player has five plate appearances and his ratings are basically noise. The system ramps from 30% to full reliability over a dimension-specific threshold (e.g., 400 PAs for Contact, 200 for Power, 50 for Speed), so early-season volatility is appropriately dampened instead of sending ratings flying.

All ELO values are capped at **[500, 3000]**, baseline **1500**.

---

## The Dimensions

**Batters are rated across five dimensions:**

- **Contact** -- Singles and doubles. Are they making solid, consistent contact? Strikeouts are the dominant negative signal here (-1.0 weight).
- **Power** -- Home runs and extra-base hits. Raw thump. Power has the highest scale factor in the system, intentionally -- power is a high-signal trait even in small samples. GIDPs are punished hard (-0.7) because they're the anti-power outcome.
- **Discipline** -- Walks, avoiding strikeouts. Plate approach and pitch recognition. Only walks, HBP, IBB, and strikeouts move this metric -- hits and balls in play are ignored entirely.
- **Speed** -- Stolen bases, caught stealing, triples. More on this below.
- **Clutch** -- Performance specifically in high-leverage situations. RISP and two-out scenarios activate a multiplier that amplifies the weight of any outcome. GIDPs in clutch situations are punished especially hard.

**Pitchers are rated across four dimensions, grounded in DIPS theory** (the idea that pitchers primarily control strikeouts, walks, and home runs -- balls in play are mostly defense and luck):

- **Stuff** -- Raw strikeout power. Only strikeouts (+1.0) and home runs (-0.8) move this metric. Consistent with FIP-style thinking.
- **BIP Suppression** -- Limiting hard contact and batted ball damage. This dimension moves *slowly* by design (low K-factor of 4.0, low scale of 3.0) because BABIP is noisy and defense-dependent. Popups and GIDPs are positive signals; triples and doubles are punished.
- **Command** -- Walk avoidance and pitch control. Walks are the dominant negative signal (-1.0), HBP is punished hard (-0.8), and strikeouts provide a modest positive boost.
- **Clutch** -- Same leverage multiplier structure as batters. HR allowed is the most punished outcome (-0.8).

Each dimension is independent. A player can be a 1650 Power bat and a 1410 Discipline bat (looking at you, every free-swinger who hits 35 home runs and strikes out 175 times). That granularity is what makes this more useful than a single "ranking."

---

## Batter-Pitcher Matchups

Each dimension is matched against the corresponding pitcher dimension:

| Batter | vs. | Pitcher |
|--------|-----|---------|
| Contact | vs. | Stuff |
| Power | vs. | BIP Suppression |
| Discipline | vs. | Command |
| Clutch | vs. | Clutch |
| Speed | -- | (no matchup -- speed is batter-only) |

This means the update is not symmetric. A batter's Power ELO updates based on how much better or worse than expected he performed *against that pitcher's BIP Suppression rating*. If he homers off a pitcher with elite BIP Suppression (1680), his Power ELO jumps more than if he homers off a replacement-level pitcher (1480). Context-adjusted, always.

---

## The Composite ELO

The five batter dimensions collapse into a single composite for ranking and matchup purposes:

```
composite (batter) = 0.23 x contact + 0.23 x power + 0.22 x discipline + 0.10 x speed + 0.22 x clutch
```

For pitchers, the composite is role-aware:

```
composite (starter)  = 0.25 x stuff + 0.20 x bip + 0.40 x command + 0.15 x clutch
composite (reliever) = 0.35 x stuff + 0.20 x bip + 0.30 x command + 0.15 x clutch
composite (closer)   = 0.35 x stuff + 0.25 x bip + 0.25 x command + 0.15 x clutch
```

Starters are Command-weighted because over 6+ innings, walk rate compounds badly. Closers are Stuff-weighted because a 1-inning appearance lives and dies by swing-and-miss.

For **fantasy projections specifically**, the composites are re-weighted toward what actually produces fantasy points rather than true talent:

```
composite (batter, fantasy)  = 0.30 x contact + 0.35 x power + 0.25 x discipline + 0.10 x speed
composite (pitcher, fantasy) = 0.40 x stuff + 0.35 x command + 0.25 x bip_suppression
```

Clutch is excluded from fantasy composites because fantasy scoring doesn't reward clutch performance -- a strikeout is a strikeout regardless of leverage.

---

## Season Resets

At the start of each season, ELOs are not simply zeroed out. They go through a regression process:

```
elo_regressed  = elo_final + (1/3) x (1500 - elo_final)
elo_new_season = 0.67 x elo_projection + 0.33 x elo_regressed
```

The projection is anchored to a preseason stat (e.g. prior-year BB% for Discipline, ISO for Power), converted to ELO scale via z-score:

```
elo_projection = 1500 + z_score x 100
z_score = (stat - league_mean) / league_std
```

This means a player coming off a .280 ISO season doesn't start from scratch -- he starts with a meaningful head-start that decays toward 1500 as actual in-season results accumulate.

---

## Speed ELO: Why Caught Stealing Is Punished Harder

Speed ELO gets its own section because I made a deliberate design choice I want to hear pushback on.

Speed is derived from three event types with no pitcher matchup (it's a pure batter skill):

```
Delta_speed = 36.0 x 4.0 x |weight| x (actual - 0.5) x reliability(n, 50)
```

| Event | Weight |
|-------|--------|
| Stolen base | +1.00 |
| Caught stealing | -1.25 |
| Triple | +0.50 |

Wait -- that table says CS weight is -1.25, but the formula applies `|weight| x (actual - 0.5)` where actual = 0.0 for a negative event. So the effective penalty is:

```
CS delta = 36.0 x 4.0 x 1.25 x (0.0 - 0.5) x reliability = -90 x reliability (max)
SB delta = 36.0 x 4.0 x 1.00 x (1.0 - 0.5) x reliability = +72 x reliability (max)
```

The CS penalty at full reliability is ~25% larger than the SB reward. This is intentional. In RE24 terms, getting caught stealing in a neutral situation is worth roughly -0.45 runs, while a successful steal is worth roughly +0.17 runs. The math says you need to succeed on about 72-75% of attempts just to break even. A player who is 10-for-20 on steal attempts is not a good baserunner, and his Speed ELO should reflect that.

Triples get half weight because they are heavily park- and luck-dependent. A Coors Field triple is not the same signal as a Petco triple.

The reliability threshold for Speed is just 50 events -- much lower than the 400-PA threshold for Contact. This is because speed events are rare. An elite base-stealer might have 40 SB attempts in a full season. The system doesn't have the luxury of waiting for a large sample.

**Season resets for Speed:** Players who stole more than 25 bases in the prior season begin the new season at ELO 1550 instead of 1500. This is a prior -- we know these guys have speed, and pretending otherwise on April 1 just introduces several weeks of ramp-up noise.

---

## How Fantasy Points Are Actually Calculated

The Fantasy tab takes your weekly matchup roster and projects fantasy points using a three-stage decision tree per plate appearance.

**Stage 1 -- What kind of PA is this?**

Each PA is resolved into three outcomes -- walk, strikeout, or ball in play -- using the batter's Discipline ELO vs. the pitcher's Command ELO (walk probability) and the pitcher's Stuff ELO vs. the batter's Contact ELO (strikeout probability). These go through a three-way softmax anchored to 2025 MLB league averages:

```
Walk rate baseline:        9.5%
Strikeout rate baseline:  22.2%
Ball in play baseline:    68.3%
```

**Stage 2 -- If it's a ball in play, hit or out?**

```
P(Hit | BIP) via logistic function, centered on MLB average hit rate (32.1%)
z = z(batter.contact) - z(pitcher.bip_suppression)
```

**Stage 3 -- If it's a hit, single or extra bases?**

```
P(XBH | Hit) via logistic, centered on 34.9%
XBH split: 2B = 55.2%, 3B = 4.5%, HR = 40.3%
z = z(batter.power)   [pitcher has no effect at this stage]
```

From those probabilities, expected wOBA is:

```
wOBA = 0.69 x P(BB) + 0.88 x P(1B) + 1.24 x P(2B) + 1.56 x P(3B) + 2.00 x P(HR)
```

**Fantasy points per batter** (assuming 3.9 PA per game, ESPN standard scoring):

| Stat | How it's calculated | Points |
|------|---------------------|--------|
| Total Bases | P(1B)x1 + P(2B)x2 + P(3B)x3 + P(HR)x4 | +1 per TB |
| Runs | ~40% of expected TB (MLB proxy) | +1 |
| RBI | ~45% of expected TB (MLB proxy) | +1 |
| Walks | P(BB) | +1 |
| Strikeouts | P(K) | -1 |
| Stolen Bases | ~2% of on-base events | +1 |

**Fantasy points per starter** (assuming 6.0 IP per start):

| Stat | How it's calculated | Points |
|------|---------------------|--------|
| Innings Pitched | 6.0 fixed | +3/IP |
| Strikeouts | P(K) x 25.8 BF | +1 |
| Hits Allowed | P(hit) x 25.8 | -1 |
| Earned Runs | ~30% of (hits + BB) | -2 |
| Walks | P(BB) x 25.8 | -1 |

The output is a projected weekly point total with a range -- not just a single number. If your range overlaps heavily with your opponent's, it's telling you the matchup is genuinely close, not a lock.

---

## The Talent Leaderboard

The leaderboard ranks all players by a specific dimension. Top 30 Speed batters. Top 30 Stuff pitchers. Top 30 Clutch hitters.

The use case I find most valuable: identifying **undervalued or streaking players** who aren't yet showing up in box scores or waiver wire buzz. If a guy's Contact ELO has climbed 80 points over the last three weeks but his batting average is still .240 because BABIP is suppressing it, the leaderboard surfaces him before the stats do.

Each player also has an OHLC chart (open/high/low/close -- same format as a stock price chart) for each talent dimension, showing how the ELO moved day by day throughout the season. A 30-point climb in Power ELO over two weeks is a much stronger signal than a single good game.

---

## Honest Caveats

A few things to know before you dive in:

**Early season noise is real.** The reliability ramp helps, but in April you're working with limited samples. Treat ratings with appropriate skepticism until late May when sample sizes are meaningful.

**Reliever projections are a known gap.** The MLB Stats API almost never lists relievers as probable pitchers, so RPs currently receive zero projected points. Closers in save situations are completely missing. This is on the roadmap.

**Runs and RBI are rough proxies.** They're estimated from expected total bases using MLB-average run correlation coefficients, not from lineup context. A cleanup hitter and a #8 hitter get the same run/RBI multiplier right now.

**The backend is running on a free tier right now, so it is slow.** API calls can be sluggish -- sometimes noticeably. I'm aware of it and it will get better. Please be patient with load times. It's not frozen, it's just thinking.

**This is still in development.** There are dimensions I haven't built yet, edge cases I haven't handled, and probably some methodology I've gotten wrong. I'm sharing it at this stage specifically because I want the community's eyes on it.

---

## What I'm Looking For From This Community

A few honest questions:

- **What dimensions am I missing?** Batter defense? Park-adjusted ratings? Handedness splits? Sprint speed from Statcast? I've thought about all of these and haven't pulled the trigger -- curious where you'd prioritize.
- **Is the Speed asymmetry right?** The CS penalty being 25% larger than the SB reward is grounded in RE24, but if you think the weighting is off I want to hear the argument.
- **What would make the Fantasy tab more useful?** Opponent pitcher matchup ratings? Streaming recommendations? Schedule-weighted projections (accounting for number of games played)?
- **What's broken?** Seriously, if something looks wrong, tell me. I'd rather know than not.

The tool is live and free to use. Given the backend situation, I'd ask that you poke around and give it a real test rather than a quick load and bounce -- some of the most interesting stuff is in the OHLC trajectory charts and the leaderboard filtering.

Happy to answer methodology questions in the comments. Thanks for reading this far.
