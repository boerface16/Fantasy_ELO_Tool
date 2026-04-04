# Update 4326 — Fantasy Model + 9D ELO Engine Improvements

## Overview
Two categories of changes:
- **Part A**: 9D ELO engine improvements (pipeline changes — affect how talent ELO accumulates going forward)
- **Part B**: Fantasy projection improvements (affect weekly point predictions — use existing ELO + new data sources)

Both parts are independent. Part A improves the accuracy of talent ELO over time; Part B improves how that ELO (and other data) is used in fantasy projections.

---

## Part A: 9D ELO Engine Changes

These changes affect `config/multi_elo_config.yaml`, `src/engine/multi_elo_engine.py`, `src/engine/talent_batch.py`, `src/etl/event_mapper.py`, and `src/etl/statcast_to_pa.py`.

---

### A1. Re-Enable Speed ELO (SB/CS Tracking)

**Current state**: Speed ELO exists but was completely disabled in V2.1. All speed weights are `0.0` in the config. SB/CS Statcast events (`stolen_base_2b`, `caught_stealing_2b`, etc.) are not in `EVENT_MAP` and fall through to the warning default.

**Important note on Statcast SB/CS rows**: These are pitch-level events tied to the active at-bat. The `batter` column = the current batter at the plate — **not the runner who stole**. The runner's player ID is stored in the base columns: for `stolen_base_2b`, the runner is in `on_1b` before the event; for `caught_stealing_2b`, same. `talent_batch.py` must use the runner's ID (not batter_id) for speed ELO updates.

**Changes:**

**`config/multi_elo_config.yaml`** — re-enable speed weights:
```yaml
baserunning_weights:
  SB:
    speed: 1.0         # re-enable (was 0.0)
    clutch_base: 0.3
  CS:
    speed: -3.0        # re-enable (was 0.0) — CS is 3x penalty (historical ratio)
    clutch_base: -0.7

composite_weights:
  batter:
    default:
      contact: 0.22
      power: 0.22
      discipline: 0.22
      speed: 0.10      # re-enable (was 0.00)
      clutch: 0.24
```

**`src/engine/multi_elo_config.py`** — add baserunning weight lookup:
```python
def get_baserunning_weights(self, event_type: str) -> dict[str, float]:
    weights = self._config.get("baserunning_weights", {}).get(event_type, {})
    result = {"speed": 0.0, "clutch_base": 0.0}
    result.update(weights)
    return result
```

**`src/etl/event_mapper.py`** — add SB/CS event types:
```python
VALID_RESULT_TYPES = {
    ...existing...,
    'SB', 'CS',
}

EVENT_MAP = {
    ...existing...,
    'stolen_base_2b': 'SB',
    'stolen_base_3b': 'SB',
    'stolen_base_home': 'SB',
    'caught_stealing_2b': 'CS',
    'caught_stealing_3b': 'CS',
    'caught_stealing_home': 'CS',
    'pickoff_caught_stealing_2b': 'CS',
    'pickoff_caught_stealing_3b': 'CS',
}
```

**`src/etl/statcast_to_pa.py`** — for SB/CS events, extract the runner ID:
Add a `runner_id` output column. For non-SB/CS events, `runner_id = None`. For SB/CS events:
- `stolen_base_2b`/`caught_stealing_2b`: runner_id = `on_1b` value (the player on first before the event)
- `stolen_base_3b`/`caught_stealing_3b`: runner_id = `on_2b` value

```python
def _get_runner_id(row) -> int | None:
    event = row.get('events', '')
    if event in ('stolen_base_2b', 'caught_stealing_2b', 'pickoff_caught_stealing_2b'):
        val = row.get('on_1b')
        return int(val) if pd.notna(val) else None
    if event in ('stolen_base_3b', 'caught_stealing_3b', 'pickoff_caught_stealing_3b'):
        val = row.get('on_2b')
        return int(val) if pd.notna(val) else None
    if event in ('stolen_base_home', 'caught_stealing_home'):
        val = row.get('on_3b')
        return int(val) if pd.notna(val) else None
    return None
```

Add `runner_id` to output columns. It is `None` for all non-baserunning PAs.

**`src/engine/talent_batch.py`** — handle SB/CS result types in processing loop:
```python
# For SB/CS rows, the actor is the runner, not the batter
result_type = row.get('result_type', 'OUT')
if result_type in ('SB', 'CS'):
    runner_id = row.get('runner_id')
    if not runner_id:
        continue  # can't attribute — skip
    # Get runner's speed ELO state
    runner_dual = self.state_mgr.get_or_create_batter(int(runner_id))
    br_weights = self.config.get_baserunning_weights(result_type)
    speed_idx = BATTER_DIM_NAMES.index('speed')
    clutch_idx = BATTER_DIM_NAMES.index('clutch')
    # Apply speed and clutch deltas directly (no pitcher matchup for speed)
    speed_weight = br_weights['speed']
    # delta = k * scale * |weight| * (actual - expected) * reliability
    actual = 1.0 if speed_weight > 0 else 0.0
    k = self.config.get_batter_k_factor('speed')
    scale = self.config.get_batter_scale('speed')
    reliability = self.calculate_reliability(int(runner_dual.season.event_counts[speed_idx]), 'speed')
    delta = k * scale * abs(speed_weight) * (actual - 0.5) * reliability
    # Apply directly to runner's speed ELO
    ...
    continue  # skip normal PA processing for baserunning rows
```
The pitcher does NOT get penalized for SB/CS (speed has no pitcher mapping).

---

### A2. Discipline − for Strikeouts

**Current state**: V2 explicitly removed the discipline penalty for strikeouts (`discipline: 0.0` with comment "K completely removed from Discipline!"). The rationale was DIPS purity, but the user wants discipline to reflect K avoidance.

**`config/multi_elo_config.yaml`** — add strikeout penalty to discipline:
```yaml
event_weights:
  StrikeOut:
    contact: -1.0
    power: 0.0
    discipline: -0.5    # re-add K penalty (was 0.0)
    speed: 0.0
    clutch_base: -0.5
```

No engine changes needed — the weight lookup handles this automatically.

---

### A3. Add bb_type to Schema — Enable POPUP / GROUNDOUT Event Types

**Current state**: All BIP outs map to the single `OUT` event type regardless of batted ball type (popup, ground ball, fly ball, line drive). Power gets a uniform `-0.2` penalty for all BIP outs.

**Statcast column**: `bb_type` values are `'ground_ball'`, `'fly_ball'`, `'popup'`, `'line_drive'`. This column is already returned by pybaseball's `statcast()` call but is not extracted in the current ETL.

**Changes:**

**Database schema** — add `bb_type VARCHAR(20)` column to `plate_appearances` table (nullable). Migration:
```sql
ALTER TABLE plate_appearances ADD COLUMN bb_type VARCHAR(20);
```

**`src/etl/statcast_to_pa.py`** — extract `bb_type` column:
```python
pa_df['bb_type'] = pa_df.get('bb_type')  # null for non-BIP events

output_columns = [
    ...existing...,
    'bb_type',   # add
]
```

Then modify `result_type` mapping to use `bb_type` when the Statcast event is a BIP out:
```python
def _refine_bip_out(result_type: str, bb_type: str | None) -> str:
    """Refine generic OUT to POPUP or GROUNDOUT when bb_type is available."""
    if result_type != 'OUT' or not bb_type:
        return result_type
    if bb_type == 'popup':
        return 'POPUP'
    if bb_type == 'ground_ball':
        return 'GROUNDOUT'
    return result_type   # fly_ball and line_drive stay as OUT

pa_df['result_type'] = pa_df.apply(
    lambda r: _refine_bip_out(r['result_type'], r.get('bb_type')), axis=1
)
```

**`src/etl/event_mapper.py`** — add to VALID_RESULT_TYPES:
```python
VALID_RESULT_TYPES = {
    ...existing...,
    'POPUP', 'GROUNDOUT',
}
```

**`config/multi_elo_config.yaml`** — add event weight entries:
```yaml
event_weights:
  POPUP:
    contact: -0.2
    power: -0.8        # pop up = worst power outcome
    discipline: 0.0
    speed: 0.0
    clutch_base: -0.5

  GROUNDOUT:
    contact: -0.1
    power: -0.4        # ground out = moderate power penalty
    discipline: 0.0
    speed: 0.0
    clutch_base: -0.3

# Also add to pitcher_event_weights:
pitcher_event_weights:
  POPUP:
    stuff: 0.0
    bip_suppression: 0.6   # popup = strong suppression success
    command: 0.15
    clutch_base: 0.4

  GROUNDOUT:
    stuff: 0.0
    bip_suppression: 0.4   # groundout = moderate suppression success
    command: 0.15
    clutch_base: 0.3
```

---

### A4. Add 2-Out Clutch Condition

**Current state**: Clutch multiplier is based only on leverage_index and RISP (`on_2b`/`on_3b`). Hits/Ks with 2 outs have no special treatment. `outs_when_up` is already stored in `plate_appearances` and passed through the PA dataframe.

**`src/engine/multi_elo_engine.py`** — add `outs_when_up` parameter:
```python
def process_plate_appearance(
    self,
    batter: BatterTalentState,
    pitcher: PitcherTalentState,
    result_type: str,
    leverage_index: float = 1.0,
    is_risp: bool = False,
    outs_when_up: int = 0,          # add this
) -> TalentUpdateResult:
    ...
    # After existing clutch_mult calculation:
    if outs_when_up == 2:
        clutch_mult = max(clutch_mult, 0.5)   # 2-out minimum clutch activation
```

**`src/engine/talent_batch.py`** — pass `outs_when_up` to engine call:
```python
result = self.engine.process_plate_appearance(
    batter, pitcher,
    result_type=result_type,
    is_risp=is_risp,
    outs_when_up=int(row.get('outs_when_up', 0)),  # add this
)
```

No config changes needed.

---

### A5. Pitcher Clutch — Amplify Walk Penalty in RISP Situations

**Current state**: `BB: clutch_base: -0.4`. With `is_risp=True`, the engine sets `clutch_mult = max(existing, 0.5)`, giving BB weight = `-0.4 × (1 + 0.5) = -0.6`. The user wants this to be significantly stronger ("--").

**`config/multi_elo_config.yaml`** — increase BB clutch base for pitchers:
```yaml
pitcher_event_weights:
  BB:
    stuff: 0.0
    bip_suppression: 0.0
    command: -1.0
    clutch_base: -0.7    # increase from -0.4 → -0.7 (RISP multiplier makes this -1.05+)
```

With RISP and outs_when_up=2 both active (e.g. bases loaded, 2 outs), `clutch_mult` can reach up to 1.0+, making BB clutch penalty = `-0.7 × 2.0 = -1.4` — strongly punishing walks in high-leverage situations.

---

## Part B: Fantasy Projection Changes

These changes affect the fantasy prediction modules and API layer. They do not change ELO calculation — they change how ELO and external stats are used to project weekly fantasy points.

---

### B1. Fix Player ELO Lookups (Core Bug Fix)

**Current bug**: `project_week()` always calls `elo_lookup.get_batter_elo(0)` and `get_pitcher_elo(0)` — ID 0 never exists, so every projection uses default 1500 ELO regardless of player.

**Root cause**: `parse_roster_text()` doesn't do DB lookups, so `RosterEntry.player_id` is always `None`. The `/weekly-projection` API endpoint passes roster straight to `project_week()` without enriching player IDs.

**`src/api/routers/fantasy.py`** — enrich roster entries with player IDs after parsing:
```python
roster = parse_roster_text(req.roster_text)
sb = get_supabase()
for entry in roster:
    resp = (sb.table("players")
              .select("player_id, position")
              .ilike("full_name", f"%{entry.name}%")
              .limit(1).execute())
    if resp.data:
        entry.player_id = resp.data[0]["player_id"]
        entry.position = resp.data[0]["position"]

# Pre-load ELO for all roster players + schedule pitchers
roster_ids = [e.player_id for e in roster if e.player_id]
pitcher_ids = [g.away_pitcher_id for g in schedule if g.away_pitcher_id] \
            + [g.home_pitcher_id for g in schedule if g.home_pitcher_id]
elo_lookup.load_batch(list(set(roster_ids + pitcher_ids)))
```

**`src/fantasy/elo_lookup.py`** — add `"speed"` to batter ELO fetch:
```python
DEFAULT_BATTER_ELO = {"contact": 1500.0, "power": 1500.0, "discipline": 1500.0, "speed": 1500.0}
BATTER_TALENTS = ["contact", "power", "discipline", "speed"]
```

**`src/fantasy/weekly_projection.py`** — use actual player IDs:
```python
# Batters: use actual player ID
batter_elo = elo_lookup.get_batter_elo(m.player_id or 0)
speed_elo = batter_elo.pop("speed", 1500.0)  # separate — not used in matchup predictor

# SP pitchers: use roster pitcher's own ID (not opponent pitcher ID)
pitcher_own_elo = elo_lookup.get_pitcher_elo(m.player_id or 0)
```

---

### B2. Relief Pitcher Projection

**Current bug**: RPs are in `PITCHER_SLOTS` but the opponent resolver only creates matchup slots when a pitcher appears in the probable-starter data. RPs never appear there → 0 matchup slots → $0 projected points.

**`src/fantasy/opponent_resolver.py`** — add `is_start: bool` field and RP slot handling:
```python
@dataclass
class MatchupSlot:
    ...
    is_start: bool = True   # False for RP appearances

# In resolve_opponents():
if entry.slot == "RP":
    # Include ALL team games as potential appearance slots
    for game in games:
        is_home = game.home_team == entry.team
        m = _make_matchup(entry, game, is_home)
        m.is_start = False
        matchups.append(m)
elif entry.slot in PITCHER_SLOTS:  # SP or P
    # Current probable-starter matching logic (unchanged)
    ...
```

**`src/fantasy/fangraphs_enricher.py`** — add G, SV, HLD to pitcher columns:
```python
PITCHER_COLS = ["Name", "Team", "G", "IP", "ERA", "FIP", "WHIP", "K/9", "BB/9", "ERA-", "SV", "HLD"]
```

**`src/fantasy/fantasy_calculator.py`** — add `estimate_reliever_points()`:
```python
def estimate_reliever_points(probs, scoring, appearances, sv_per_app=0.0,
                              hld_per_app=0.0, ip_per_app=1.0):
    rules = scoring["pitcher"]
    total_ip = appearances * ip_per_app
    bf = total_ip * AVG_BF_PER_INNING
    e_k = probs.get("K", 0.22) * bf
    e_bb = probs.get("BB", 0.09) * bf
    e_hits = sum(probs.get(k, 0) for k in ["1B", "2B", "3B", "HR"]) * bf
    e_er = (e_hits + e_bb) * 0.30
    e_sv = sv_per_app * appearances
    e_hld = hld_per_app * appearances
    return float(
        total_ip * rules.get("IP", 3)
        + e_k * rules.get("K", 1)
        + e_hits * rules.get("H", -1)
        + e_er * rules.get("ER", -2)
        + e_bb * rules.get("BB", -1)
        + e_sv * rules.get("SV", 5)
        + e_hld * rules.get("HD", 2)
    )
```

**`src/fantasy/weekly_projection.py`** — add Fangraphs fetch and RP branch:
```python
from src.fantasy.fangraphs_enricher import get_pitcher_stats

# In project_week(), fetch once:
pitcher_fg = get_pitcher_stats(week_start.year)
fg_by_name = {row["Name"].lower(): row for _, row in pitcher_fg.iterrows()}

# In pitcher projection loop:
rp_slots = [m for m in player_matchups if not m.is_start]
sp_starts = [m for m in player_matchups if m.is_start]

if rp_slots:
    fg = fg_by_name.get(name.lower(), {})
    season_g = float(fg.get("G") or 0) or 30.0
    season_ip = float(fg.get("IP") or 0) or season_g
    season_sv = float(fg.get("SV") or 0)
    season_hld = float(fg.get("HLD") or 0)

    SEASON_GAMES = 162.0
    appearance_rate = min(season_g / SEASON_GAMES, 0.85)
    ip_per_app = max(0.5, min(2.0, season_ip / season_g)) if season_g > 0 else 1.0
    sv_per_app = season_sv / season_g if season_g > 0 else 0.0
    hld_per_app = season_hld / season_g if season_g > 0 else 0.0

    team_games = len(rp_slots)
    weekly_appearances = team_games * appearance_rate

    pitcher_own_elo = elo_lookup.get_pitcher_elo(rp_slots[0].player_id or 0)
    avg_batter = {"contact": 1504.5, "power": 1468.6, "discipline": 1700.3}
    pitcher_pred = predict_plate_appearance(avg_batter, pitcher_own_elo)

    pts = estimate_reliever_points(
        pitcher_pred["probabilities"], scoring,
        appearances=weekly_appearances,
        sv_per_app=sv_per_app, hld_per_app=hld_per_app,
        ip_per_app=ip_per_app,
    )
    # Append one GameMatchup entry representing the full week's RP contribution
```

---

### B3. SP Win/Loss Probability

**Current state**: W (+2) and L (−2) are in the scoring config but never projected. Starters win ~28% of starts on average.

**`src/fantasy/fantasy_calculator.py`** — add W/L params to `estimate_pitcher_points()`:
```python
def estimate_pitcher_points(probs, scoring, innings=6.0, win_prob=0.0, loss_prob=0.0):
    ...
    pts += win_prob * rules.get("W", 2)
    pts += loss_prob * rules.get("L", -2)
```

**`src/fantasy/weekly_projection.py`** — estimate W/L probability from pitcher quality:
```python
from src.fantasy.matchup_predictor import LEAGUE_AVG_WOBA

# After getting pitcher_pred:
woba_diff = LEAGUE_AVG_WOBA - pitcher_pred["expected_woba"]  # positive = pitcher better than avg
win_prob = max(0.10, min(0.55, 0.28 + woba_diff * 0.5))
loss_prob = max(0.05, min(0.40, 0.18 - woba_diff * 0.3))

pts = estimate_pitcher_points(
    pitcher_pred["probabilities"], scoring,
    innings=6.0, win_prob=win_prob, loss_prob=loss_prob
)
```

---

### B4. SB — 3-Factor Model

**Current state**: Flat 2% stolen base rate per time on base, regardless of player speed, opponent pitcher, or opponent catcher.

**Factors:**
1. **Batter speed ELO** — player's historical SB/CS record (tracked in 9D ELO, re-enabled in A1)
2. **Opponent pitcher SB-allow rate** — pitchers with slow deliveries allow more SBs. Add `SB` and `CS` to Fangraphs pitcher columns, compute rate vs league average.
3. **Opponent catcher CS rate** — catchers with strong arms suppress SBs. Requires secondary lookup since only probable pitcher (not catcher) is in schedule data.

**`src/fantasy/fangraphs_enricher.py`** — add SB/CS to pitcher columns (in addition to G/SV/HLD from B2):
```python
PITCHER_COLS = ["Name", "Team", "G", "IP", "ERA", "FIP", "WHIP", "K/9", "BB/9",
                "ERA-", "SV", "HLD", "SB", "CS"]
# Note: "SB" here = stolen bases allowed, "CS" = caught stealing by pitcher
```

**`src/fantasy/fantasy_calculator.py`** — update `estimate_batter_points()`:
```python
def estimate_batter_points(probs, scoring, pas=1, speed_elo=1500.0,
                            pitcher_sb_factor=1.0):
    # Speed ELO scaling
    SPEED_MEAN, SPEED_STD = 1500.0, 50.0
    speed_z = (speed_elo - SPEED_MEAN) / SPEED_STD
    speed_factor = max(0.1, 1.0 + speed_z * 0.6)

    # SB rate = base × speed × pitcher permissiveness
    sb_rate = 0.02 * speed_factor * pitcher_sb_factor
    e_sb = (probs.get("1B", 0) + probs.get("BB", 0)) * sb_rate
    ...
```

**`src/fantasy/weekly_projection.py`** — compute pitcher SB factor from Fangraphs:
```python
# For each batter matchup, compute pitcher_sb_factor:
fg_pitcher = fg_by_name.get((m.opponent_pitcher_name or "").lower(), {})
season_sb_allowed = float(fg_pitcher.get("SB") or 0)
season_cs_by_pitcher = float(fg_pitcher.get("CS") or 0)
season_g_pitcher = float(fg_pitcher.get("G") or 0) or 30.0

MLB_AVG_SB_PER_GAME = 0.14   # league average ~23 SB allowed per starter per 162G
pitcher_sb_rate = season_sb_allowed / season_g_pitcher if season_g_pitcher > 0 else MLB_AVG_SB_PER_GAME
pitcher_sb_factor = pitcher_sb_rate / MLB_AVG_SB_PER_GAME   # >1.0 = easy to steal on

pts = estimate_batter_points(
    pred["probabilities"], scoring,
    pas=AVG_PA_PER_GAME,
    speed_elo=speed_elo,
    pitcher_sb_factor=pitcher_sb_factor,
)
```

**Catcher factor** (stretch goal — deferred): Catcher CS% requires a secondary lookup to identify the likely starting catcher for the opponent team. This data is available via pybaseball's catcher framing/fielding stats but requires team-to-catcher mapping not currently in the system. Implement separately once pitcher factor is validated.

---

### B5. Batter vs Team History Blend

**Current state**: Fantasy projections use only talent ELO × opponent pitcher ELO with no historical matchup context. Some batters consistently mash certain teams; others consistently struggle.

**Approach**: Query the batter's historical PA outcomes against pitchers from the opponent team, then blend with the ELO-based prediction. Weight of historical data scales with sample size.

**Blend formula**:
- `N` = historical PAs vs opponent team pitchers
- `alpha = min(0.30, N / 333)` — reaches max blend weight of 30% at 100 PAs (333 is the divisor to smooth the ramp)
- `blended_probs = alpha × historical_probs + (1 − alpha) × elo_probs`

**New function in `src/fantasy/weekly_projection.py`** (or separate `src/fantasy/history_lookup.py`):
```python
def get_historical_probs(supabase, batter_id: int, opponent_team: str) -> tuple[dict, int]:
    """Query batter's historical PA outcomes vs opponent team pitchers.

    Returns (prob_dict, sample_size). prob_dict is None if no history found.
    """
    # Step 1: Get pitcher IDs currently on opponent team
    resp = supabase.table("players").select("player_id").eq("team", opponent_team).execute()
    opponent_pitcher_ids = [r["player_id"] for r in (resp.data or [])]
    if not opponent_pitcher_ids:
        return {}, 0

    # Step 2: Query historical PAs for this batter vs those pitchers
    resp = (supabase.table("plate_appearances")
            .select("result_type")
            .eq("batter_id", batter_id)
            .in_("pitcher_id", opponent_pitcher_ids[:100])  # Supabase IN limit
            .execute())
    rows = resp.data or []
    if not rows:
        return {}, 0

    # Step 3: Compute outcome probabilities from historical sample
    counts = {}
    for row in rows:
        rt = row["result_type"]
        counts[rt] = counts.get(rt, 0) + 1
    n = len(rows)
    RESULT_TO_PROB_KEY = {
        "Single": "1B", "Double": "2B", "Triple": "3B", "HR": "HR",
        "BB": "BB", "IBB": "BB", "HBP": "BB",
        "StrikeOut": "K",
        "OUT": "OUT", "FC": "OUT", "GIDP": "OUT", "POPUP": "OUT", "GROUNDOUT": "OUT",
    }
    probs = {"BB": 0.0, "K": 0.0, "OUT": 0.0, "1B": 0.0, "2B": 0.0, "3B": 0.0, "HR": 0.0}
    for rt, cnt in counts.items():
        key = RESULT_TO_PROB_KEY.get(rt)
        if key:
            probs[key] = probs.get(key, 0.0) + cnt / n
    return probs, n


def blend_probs(elo_probs: dict, hist_probs: dict, n: int) -> dict:
    """Blend ELO-based probs with historical probs using sample-size weight."""
    if n < 10 or not hist_probs:
        return elo_probs
    alpha = min(0.30, n / 333)
    return {k: (1 - alpha) * elo_probs.get(k, 0) + alpha * hist_probs.get(k, 0)
            for k in elo_probs}
```

**Integration in `weekly_projection.py`** batter loop:
```python
pred = predict_plate_appearance(batter_elo, pitcher_elo)
hist_probs, hist_n = get_historical_probs(supabase, m.player_id, m.opponent_team)
final_probs = blend_probs(pred["probabilities"], hist_probs, hist_n)
pts = estimate_batter_points(final_probs, scoring, pas=AVG_PA_PER_GAME,
                              speed_elo=speed_elo, pitcher_sb_factor=pitcher_sb_factor)
```

Note: `project_week()` needs `supabase` passed as a parameter (currently it doesn't take it).

---

## File Change Summary

| File | Part | Change |
|------|------|--------|
| `config/multi_elo_config.yaml` | A1 | Re-enable speed weights (SB: 1.0, CS: -3.0), update composite |
| `config/multi_elo_config.yaml` | A2 | StrikeOut discipline: -0.5 |
| `config/multi_elo_config.yaml` | A3 | Add POPUP, GROUNDOUT event weights (batter + pitcher) |
| `config/multi_elo_config.yaml` | A5 | Pitcher BB clutch_base: -0.4 → -0.7 |
| `src/engine/multi_elo_config.py` | A1 | Add `get_baserunning_weights()` method |
| `src/engine/multi_elo_engine.py` | A4 | Add `outs_when_up` param, 2-out clutch condition |
| `src/engine/talent_batch.py` | A1, A4 | Handle SB/CS rows with runner_id; pass outs_when_up |
| `src/etl/event_mapper.py` | A1, A3 | Add SB/CS/POPUP/GROUNDOUT to EVENT_MAP |
| `src/etl/statcast_to_pa.py` | A1, A3 | Extract runner_id for SB/CS; extract bb_type; refine BIP outs |
| Database | A3 | `ALTER TABLE plate_appearances ADD COLUMN bb_type VARCHAR(20)` |
| `src/fantasy/fangraphs_enricher.py` | B2, B4 | Add G, SV, HLD, SB, CS to PITCHER_COLS |
| `src/fantasy/elo_lookup.py` | B1 | Add speed to BATTER_TALENTS |
| `src/fantasy/opponent_resolver.py` | B2 | Add is_start field; RP → all team games |
| `src/fantasy/fantasy_calculator.py` | B2, B3, B4 | estimate_reliever_points(); W/L params; speed+pitcher SB factor |
| `src/fantasy/weekly_projection.py` | B1–B5 | Fix ELO lookups, RP branch, Fangraphs fetch, history blend |
| `src/api/routers/fantasy.py` | B1 | Enrich roster with player IDs before projection |

---

## Verification

### Part A (Engine)
- Run full season backfill after changes, check `talent_player_current` — speed ELO should now vary meaningfully (not all 1500)
- Fast runners (e.g. Elly De La Cruz, Jose Caballero) should have speed ELO > 1600
- Slow power hitters should have speed ELO < 1450
- Check `talent_pa_detail` has records with `talent_type = 'speed'` and `delta != 0`

### Part B (Fantasy)
1. Run dev server: `uvicorn src.api.main:app --reload`
2. POST `/api/fantasy/weekly-projection` with a mixed SP/RP/batter roster
3. Verify batter projected points differ by player (not all identical — confirms ELO lookup fix)
4. Verify RP players have non-zero `totalPoints`
5. Verify a confirmed closer (e.g. Emanuel Clase) projects higher than a middle reliever
6. Verify a known speedster projects meaningfully higher SB contribution vs a slow slugger
7. Spot-check history blend: Aaron Judge vs NYM should have different projection than a player with no NYM history
