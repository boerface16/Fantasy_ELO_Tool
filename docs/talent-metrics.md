# Talent Metrics Reference

This document describes how each ELO-based talent metric is calculated. Every plate appearance (PA) is a binary matchup between batter and pitcher dimensions, updating both sides via an Elo rating system.

---

## Core ELO Update Formula

Each PA produces an ELO delta per dimension:

```
Δ = K × scale × |w| × (actual - E) × reliability
```

Where:

```
actual = 1.0  if w > 0
         0.0  if w ≤ 0

E = 1 / (1 + 10^((elo_opponent - elo_player) / divisor))

reliability = 0.3 + 0.7 × (n / threshold)   if n < threshold
              1.0                             if n ≥ threshold
```

| Symbol | Meaning |
|--------|---------|
| `K` | K-factor (learning rate) for the dimension |
| `scale` | Amplitude multiplier for the dimension |
| `w` | Event weight (e.g. HR = +1.0 for Power) |
| `E` | Expected score from ELO matchup |
| `divisor` | Average of player and opponent expected divisors |
| `n` | Event count for the player |
| `threshold` | Reliability sample threshold for the dimension |

All ELO values are bounded **[500, 3000]**, baseline **1500**.

---

## Batter Dimensions (5)

### Contact

Measures strikeout avoidance and ability to put the ball in play.

```
Δ_contact = 12.0 × 5.0 × |w_contact| × (actual - E_stuff) × reliability(n, 400)
```

| Event | w |
|-------|---|
| Single | +0.30 |
| Double | +0.30 |
| Triple | +0.30 |
| HR | +0.20 |
| SAC | +0.20 |
| E | +0.10 |
| Out | -0.15 |
| FC | -0.10 |
| GIDP | -0.10 |
| Groundout | -0.10 |
| Popup | -0.20 |
| **Strikeout** | **-1.00** |

**Matched against:** Pitcher Stuff

---

### Power

Measures extra-base hit and slugging ability.

```
Δ_power = 14.4 × 10.0 × |w_power| × (actual - E_bip_suppression) × reliability(n, 200)
```

| Event | w |
|-------|---|
| **HR** | **+1.00** |
| Double | +0.70 |
| Triple | +0.30 |
| Out | -0.20 |
| FC | -0.20 |
| Groundout | -0.40 |
| GIDP | -0.70 |
| **Popup** | **-0.80** |

Power has the highest scale (10.0) and lowest reliability threshold (200), making it the fastest-moving dimension — intentional, since power is a high-signal trait even in small samples.

**Matched against:** Pitcher BIP Suppression

---

### Discipline

Measures plate selectivity and walk rate.

```
Δ_discipline = 12.0 × 5.0 × |w_discipline| × (actual - E_command) × reliability(n, 400)
```

| Event | w |
|-------|---|
| **BB** | **+1.00** |
| HBP | +0.80 |
| IBB | +0.60 |
| Strikeout | -0.50 |
| All other events | 0.00 |

Only walks, HBP, IBB, and strikeouts carry weight — hits and BIP outcomes are ignored entirely.

**Matched against:** Pitcher Command

---

### Speed

Measures baserunning and stolen base ability.

```
Δ_speed = 36.0 × 4.0 × |w_speed| × (actual - 0.5) × reliability(n, 50)
```

| Event | w |
|-------|---|
| **SB** | **+1.00** |
| **CS** | **-3.00** |

Speed uses a **fixed expected value of 0.5** (no pitcher matchup). The CS penalty is 3× the SB reward, reflecting the run-expectancy cost of getting caught.

**No pitcher matchup.**

**Seasonal reset:** At the start of each season, `season_elo` resets to **1500** for all batters. Players who stole **more than 25 bases** in the prior season begin at **1550** instead, reflecting demonstrated above-average baserunning ability.

---

### Clutch (Batter)

Measures performance in high-leverage situations.

```
Δ_clutch = 18.0 × 6.0 × |w_clutch| × (actual - E_clutch_p) × reliability(n, 100)
```

The effective event weight is the base weight scaled by a situation multiplier. The engine supports a Leverage Index (LI) parameter, but **LI is not sourced from Statcast** and defaults to 1.0 for every PA. In practice, clutch is triggered entirely by RISP and 2-out situations:

```
m = 0.0

if RISP:       m = max(m, 0.5)
if outs == 2:  m = max(m, 0.5)
if event == GIDP:  m = min(2.0, m × 2.0)

w_clutch = base_weight × (1.0 + m)   if m > 0
           base_weight × 0.5         if m == 0
```

Base weights by event:

| Event | base_weight |
|-------|-------------|
| Triple | +0.70 |
| HR | +0.80 |
| Double | +0.60 |
| Single | +0.50 |
| BB | +0.40 |
| HBP | +0.30 |
| IBB | +0.20 |
| SAC | +0.30 |
| E | +0.20 |
| Out | -0.30 |
| Groundout | -0.30 |
| FC | -0.40 |
| Popup | -0.50 |
| Strikeout | -0.50 |
| **GIDP** | **-0.80** |

**Matched against:** Pitcher Clutch

---

## Pitcher Dimensions (4)

The pitcher model follows **DIPS theory**: pitchers primarily control strikeouts, walks, and home runs. Balls in play are tracked separately with dampened sensitivity.

### Stuff

Measures pure strikeout power.

```
Δ_stuff = 12.0 × 5.0 × |w_stuff| × (actual - E_contact) × reliability(n, 400)
```

| Event | w |
|-------|---|
| **Strikeout** | **+1.00** |
| **HR** | **-0.80** |
| All other events | 0.00 |

Only strikeouts and home runs move this metric, consistent with FIP-style DIPS thinking.

**Matched against:** Batter Contact

---

### BIP Suppression

Measures ability to suppress balls in play (BABIP defense).

```
Δ_bip = 4.0 × 3.0 × |w_bip| × (actual - E_power) × reliability(n, 400)
```

| Event | w |
|-------|---|
| **Popup** | **+0.60** |
| GIDP | +0.50 |
| Out | +0.40 |
| Groundout | +0.40 |
| FC | +0.30 |
| SAC | +0.20 |
| E | -0.10 |
| Single | -0.60 |
| Double | -0.80 |
| **Triple** | **-0.90** |

The low K-factor (4.0) and scale (3.0) are intentional — BABIP is noisy and partially driven by defense. This dimension moves slowly.

**Matched against:** Batter Power

---

### Command

Measures pitch control and walk prevention.

```
Δ_command = 12.0 × 5.0 × |w_command| × (actual - E_discipline) × reliability(n, 400)
```

| Event | w |
|-------|---|
| Strikeout | +0.30 |
| Out | +0.15 |
| GIDP | +0.15 |
| FC | +0.15 |
| Groundout | +0.15 |
| Popup | +0.15 |
| IBB | -0.30 |
| HBP | -0.80 |
| **BB** | **-1.00** |

**Matched against:** Batter Discipline

---

### Clutch (Pitcher)

Measures performance under pressure. Uses the same leverage multiplier formula as Batter Clutch.

```
Δ_clutch_p = 18.0 × 6.0 × |w_clutch_p| × (actual - E_clutch_b) × reliability(n, 100)
```

Base weights by event:

| Event | base_weight |
|-------|-------------|
| **GIDP** | **+0.80** |
| Popup | +0.40 |
| FC | +0.40 |
| Out | +0.30 |
| Groundout | +0.30 |
| Strikeout | +0.50 |
| IBB | -0.20 |
| SAC | -0.30 |
| E | -0.20 |
| HBP | -0.30 |
| Single | -0.50 |
| Strikeout (neg context) | — |
| Double | -0.60 |
| Triple | -0.70 |
| BB | -0.70 |
| **HR** | **-0.80** |

Situation multiplier logic is identical to Batter Clutch above (RISP and 2-outs only; LI defaults to 1.0).

**Matched against:** Batter Clutch

---

## Composite ELO

### Batter Composite

```
composite_b = 0.23 × contact + 0.23 × power + 0.22 × discipline + 0.10 × speed + 0.22 × clutch
```

### Pitcher Composite (Role-Based)

```
composite_p (starter)  = 0.25 × stuff + 0.20 × bip + 0.40 × command + 0.15 × clutch
composite_p (reliever) = 0.35 × stuff + 0.20 × bip + 0.30 × command + 0.15 × clutch
composite_p (closer)   = 0.35 × stuff + 0.25 × bip + 0.25 × command + 0.15 × clutch
```

---

## Season Reset

```
elo_regressed     = elo_final + (1/3) × (1500 - elo_final)
elo_new_season    = 0.67 × elo_projection + 0.33 × elo_regressed
```

Preseason projection converted to ELO scale:

```
elo_projection = 1500 + z_score × 100

z_score = (stat - μ) / σ
```

Projection-to-dimension mapping:

| Dimension | Stat |
|-----------|------|
| Contact | 1 − K% |
| Power | ISO |
| Discipline | BB% |
| Speed | 1500 baseline; 1550 if >25 SB prior season |
| Clutch | 1500 (no projection) |

---

## Fantasy-Specific Composites

Used by the weekly projection system, weighted for fantasy point correlation rather than true-talent:

```
composite_b (fantasy) = 0.30 × contact + 0.35 × power + 0.25 × discipline + 0.10 × speed
composite_p (fantasy) = 0.40 × stuff + 0.35 × command + 0.25 × bip_suppression
```

Clutch is excluded from fantasy composites.
