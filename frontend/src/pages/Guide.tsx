import { useState } from 'react';
import { BookOpen, Code, Info, ChevronDown, ChevronUp, Sparkles, Crosshair } from 'lucide-react';
import { useSeasonMeta } from '../hooks/useElo';

type Tab = 'overview' | 'general' | 'talent' | 'matchup' | 'developer';

function Accordion({ title, children, defaultOpen = false }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-5 py-4 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <span className="font-semibold text-gray-900">{title}</span>
        {isOpen ? (
          <ChevronUp className="w-5 h-5 text-gray-500" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-500" />
        )}
      </button>
      {isOpen && (
        <div className="px-5 py-4 space-y-3 text-gray-700 leading-relaxed">
          {children}
        </div>
      )}
    </div>
  );
}

function OverviewTab() {
  return (
    <div className="space-y-6 text-gray-700 leading-relaxed">
      {/* Abstract */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">Abstract</h3>
        <p>
          Traditional baseball statistics evaluate players in isolation. Batting average, ERA, and OPS
          measure outcomes but ignore context: who was pitching, what was the base-out state, and how
          does the ballpark affect scoring?
        </p>
        <p className="mt-2">
          This project applies an <strong>ELO rating system</strong> — originally designed for chess — to
          MLB plate appearances. Each PA is a head-to-head contest between batter and pitcher. The batter's
          gain is exactly the pitcher's loss (<strong>zero-sum</strong>). The result is a unified scale where
          1,500 is league average, elite batters climb above 2,000, and dominant pitchers approach 1,900.
        </p>
        <p className="mt-2">Three adjustments ensure fairness:</p>
        <ul className="list-disc pl-5 space-y-1 mt-1">
          <li><strong>Park factor</strong> — Coors Field inflates run values; Petco Park suppresses them. We normalize.</li>
          <li><strong>State normalization</strong> — A single with bases loaded has higher raw run value than with bases empty. We subtract the expected run value for each base-out state so only <em>above-average</em> outcomes raise ELO.</li>
          <li><strong>Field error handling</strong> — Batters don't earn ELO credit for reaching base on fielding errors.</li>
        </ul>
      </section>

      {/* Methodology */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">Methodology</h3>
        <p className="font-semibold text-gray-900">ELO Formula (V5.3 Zero-Sum)</p>
        <p className="mt-1">Every player starts at <strong>1,500</strong> (league average). After each plate appearance:</p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1 mt-2">
          <p className="text-gray-500"># Step 1: Park factor adjustment</p>
          <p>adjusted_rv = delta_run_exp - (park_factor - 1.0) × 0.1</p>
          <p className="text-gray-500 mt-2"># Step 2: State normalization</p>
          <p>rv_diff = adjusted_rv - mean_rv[base_out_state]</p>
          <p className="text-gray-500 mt-2"># Step 3: Zero-sum ELO update</p>
          <p>batter_delta  = K × rv_diff</p>
          <p>pitcher_delta = -batter_delta</p>
        </div>
        <div className="overflow-x-auto mt-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Parameter</th>
                <th className="px-3 py-2 text-left font-semibold">Value</th>
                <th className="px-3 py-2 text-left font-semibold">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-mono">K_FACTOR</td>
                <td className="px-3 py-2">12.0</td>
                <td className="px-3 py-2">ELO sensitivity per plate appearance</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">INITIAL_ELO</td>
                <td className="px-3 py-2">1500.0</td>
                <td className="px-3 py-2">Starting ELO for all players</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">MIN_ELO</td>
                <td className="px-3 py-2">500.0</td>
                <td className="px-3 py-2">Floor (ELO cannot drop below)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">ADJUSTMENT_SCALE</td>
                <td className="px-3 py-2">0.1</td>
                <td className="px-3 py-2">Park factor scaling constant</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Data Source */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">Data Source</h3>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>MLB Statcast</strong> via Baseball Savant</li>
          <li><strong>711,897 pitches</strong> aggregated into <strong>183,092 plate appearances</strong></li>
          <li><strong>2,428 games</strong> across the current season</li>
          <li><strong>1,469 players</strong> (batters and pitchers)</li>
        </ul>
        <p className="mt-3 font-semibold text-gray-900">Key Metric: delta_run_exp</p>
        <p className="mt-1">
          The core input is <strong>delta run expectancy</strong> — how much a plate appearance outcome
          changed the expected runs scored in that inning.
        </p>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Outcome</th>
                <th className="px-3 py-2 text-left font-semibold">Typical delta_run_exp</th>
                <th className="px-3 py-2 text-left font-semibold">ELO Impact (K=12)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2">Home run</td>
                <td className="px-3 py-2">+1.4</td>
                <td className="px-3 py-2">~+17 ELO</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Walk</td>
                <td className="px-3 py-2">+0.3</td>
                <td className="px-3 py-2">~+4 ELO</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Strikeout</td>
                <td className="px-3 py-2">-0.3</td>
                <td className="px-3 py-2">~-4 ELO</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Double play</td>
                <td className="px-3 py-2">-0.8</td>
                <td className="px-3 py-2">~-10 ELO</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* State Normalization & Park Factor */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">Adjustments</h3>
        <p className="font-semibold text-gray-900">State Normalization</p>
        <p className="mt-1">
          The 24 base-out states (8 base configurations × 3 out counts) each have different average run values.
          A hit with runners in scoring position carries higher raw delta_run_exp than with bases empty —
          but it's also the <em>expected</em> outcome in that situation. We subtract the mean delta_run_exp
          for each state so ELO only rewards performance <em>above</em> the situational average.
        </p>
        <p className="font-semibold text-gray-900 mt-4">Park Factor</p>
        <p className="mt-1">MLB's 30 stadiums have different scoring environments:</p>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Stadium</th>
                <th className="px-3 py-2 text-left font-semibold">Park Factor</th>
                <th className="px-3 py-2 text-left font-semibold">Effect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2">Coors Field (COL)</td>
                <td className="px-3 py-2">1.13</td>
                <td className="px-3 py-2">Batter-friendly — positive outcomes adjusted down</td>
              </tr>
              <tr>
                <td className="px-3 py-2">T-Mobile Park (SEA)</td>
                <td className="px-3 py-2">0.91</td>
                <td className="px-3 py-2">Pitcher-friendly — positive outcomes adjusted up</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Yankee Stadium (NYY)</td>
                <td className="px-3 py-2">1.00</td>
                <td className="px-3 py-2">Neutral — no adjustment</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-sm text-gray-500">
          Over a season of ~250 home PAs, park factor shifts ELO by ±40 points for extreme parks.
        </p>
      </section>

      {/* ELO Tiers */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">ELO Tiers</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Tier</th>
                <th className="px-3 py-2 text-left font-semibold">ELO Range</th>
                <th className="px-3 py-2 text-left font-semibold">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-bold text-elo-elite">Elite</td>
                <td className="px-3 py-2">1,800+</td>
                <td className="px-3 py-2">MVP-caliber performance</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-high">High</td>
                <td className="px-3 py-2">1,650 – 1,799</td>
                <td className="px-3 py-2">All-Star level</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-above">Above Avg</td>
                <td className="px-3 py-2">1,550 – 1,649</td>
                <td className="px-3 py-2">Above-average starter</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-average">Average</td>
                <td className="px-3 py-2">1,450 – 1,549</td>
                <td className="px-3 py-2">League average</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-below">Below Avg</td>
                <td className="px-3 py-2">1,350 – 1,449</td>
                <td className="px-3 py-2">Below-average performance</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-low">Low</td>
                <td className="px-3 py-2">1,200 – 1,349</td>
                <td className="px-3 py-2">Struggling performance</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-cold">Cold</td>
                <td className="px-3 py-2">&lt; 1,200</td>
                <td className="px-3 py-2">Significant slump</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Two-Way Players */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">Two-Way Players</h3>
        <p>
          Players who both bat and pitch — such as <strong>Shohei Ohtani</strong> — present
          a unique challenge. A single ELO number blends two fundamentally different skill sets,
          making it impossible to evaluate their hitting and pitching independently.
        </p>
        <p className="mt-2">
          Our system tracks <strong>separate Batting ELO and Pitching ELO</strong> for every player.
          When a player steps into the batter's box, only their Batting ELO is at stake. When they
          take the mound, only their Pitching ELO moves. This separation ensures:
        </p>
        <ul className="list-disc pl-5 space-y-1 mt-2">
          <li>A dominant outing on the mound doesn't inflate a player's batting rating</li>
          <li>A slump at the plate doesn't drag down their pitching rating</li>
          <li>The leaderboard ranks two-way players in <strong>both</strong> the Batter and Pitcher tabs using the correct role-specific ELO</li>
        </ul>
        <p className="mt-2">
          Two-way players are marked with a{' '}
          <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">TWP</span>{' '}
          badge throughout the site. Their profile page features <strong>Batting / Pitching tabs</strong> with
          independent OHLC charts and statistics for each role.
        </p>
        <div className="overflow-x-auto mt-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Field</th>
                <th className="px-3 py-2 text-left font-semibold">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-mono">batting_elo</td>
                <td className="px-3 py-2">ELO earned exclusively from plate appearances as a batter</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">pitching_elo</td>
                <td className="px-3 py-2">ELO earned exclusively from batters faced as a pitcher</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">composite_elo</td>
                <td className="px-3 py-2">PA-weighted average of batting and pitching ELO</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Architecture */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">System Architecture</h3>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm overflow-x-auto">
          <p>[Statcast Parquet] → ETL → [Supabase plate_appearances] → ELO Engine → [player_elo / daily_ohlc]</p>
          <p className="ml-56 text-gray-500">↑ RE24 Baseline + Park Factors</p>
        </div>
        <ol className="list-decimal pl-5 space-y-1 mt-3">
          <li><strong>Raw Data</strong> — Statcast pitch-level parquet (711K rows, 118 columns)</li>
          <li><strong>ETL</strong> — Aggregate to plate appearance level, extract delta_run_exp, base-out state, venue</li>
          <li><strong>ELO Engine (V5.3)</strong> — Process PAs chronologically with park factor + state normalization</li>
          <li><strong>Output</strong> — Per-PA ELO detail records + daily OHLC candlestick aggregation</li>
          <li><strong>Frontend</strong> — React SPA reading directly from Supabase</li>
        </ol>
      </section>

      {/* Database */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">Database</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Table</th>
                <th className="px-3 py-2 text-left font-semibold">Rows</th>
                <th className="px-3 py-2 text-left font-semibold">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-mono">players</td>
                <td className="px-3 py-2">1,469</td>
                <td className="px-3 py-2">Player metadata (name, team, position)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">plate_appearances</td>
                <td className="px-3 py-2">183,092</td>
                <td className="px-3 py-2">All PAs with delta_run_exp and context</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">player_elo</td>
                <td className="px-3 py-2">1,469</td>
                <td className="px-3 py-2">Current ELO + PA count per player</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">elo_pa_detail</td>
                <td className="px-3 py-2">183,092</td>
                <td className="px-3 py-2">Per-PA ELO change records</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">daily_ohlc</td>
                <td className="px-3 py-2">69,125</td>
                <td className="px-3 py-2">Daily OHLC candlestick data</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      {/* Tech Stack */}
      <section>
        <h3 className="text-xl font-bold text-gray-900 mb-3">Tech Stack</h3>
        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <p className="font-semibold text-gray-900 mb-2">Engine (Python)</p>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              <li>pandas — data processing</li>
              <li>Supabase Python SDK — database I/O</li>
              <li>pytest — test suite (72 tests)</li>
            </ul>
          </div>
          <div>
            <p className="font-semibold text-gray-900 mb-2">Frontend (TypeScript)</p>
            <ul className="list-disc pl-5 space-y-1 text-sm">
              <li>Vite + React + TypeScript</li>
              <li>Tailwind CSS</li>
              <li>TanStack React Query</li>
              <li>Lightweight Charts (OHLC)</li>
              <li>Supabase JS SDK (read-only)</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Disclaimer */}
      <section className="text-sm text-gray-500 border-t border-gray-200 pt-4">
        <p>
          This project is for demonstration and analytical purposes. ELO ratings represent one approach
          to player evaluation and do not capture defense, baserunning, or game context beyond run expectancy.
          Data sourced from MLB Statcast via Baseball Savant.
        </p>
      </section>
    </div>
  );
}

function GeneralTab() {
  return (
    <div className="space-y-4">
      <Accordion title="What is ELO?" defaultOpen>
        <p>
          The <strong>ELO Rating System</strong> is a method originally designed to calculate
          the relative skill levels of chess players. We adapt this system to evaluate
          MLB players based on their <strong>plate appearance (PA) outcomes</strong>.
        </p>
        <p>
          Every player starts the season at <strong>1,500</strong> (league average).
          After each plate appearance, the batter and pitcher exchange ELO points
          based on the outcome — if the batter performs above expectation, they gain
          points while the pitcher loses the same amount, and vice versa.
        </p>
        <p>
          Over the course of a season, elite performers rise above 1,800 while
          struggling players may fall below 1,200. The system provides a single,
          intuitive number that captures a player's cumulative performance trajectory.
        </p>
      </Accordion>

      <Accordion title="Zero-Sum Principle">
        <p>
          Our ELO system follows a strict <strong>zero-sum</strong> design.
          For every plate appearance, the ELO points gained by one side are exactly
          equal to the points lost by the other:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1">
          <p>adjusted_rv  = delta_run_exp − park_adjustment</p>
          <p>rv_diff      = adjusted_rv − expected_rv[state]</p>
          <p>batter_delta = K × rv_diff</p>
          <p>pitcher_delta = −batter_delta</p>
        </div>
        <p>
          This means the league-wide average ELO always stays near 1,500.
          A player's rating only rises by outperforming opponents, not through
          inflation. Park factor and base-out state adjustments ensure fair
          comparison across stadiums and game situations.
        </p>
      </Accordion>

      <Accordion title="K-Factor & Run Value">
        <p>
          The <strong>K-Factor</strong> controls how much a single plate appearance
          can shift a player's ELO. We use <strong>K = 12</strong>.
        </p>
        <p>
          The key input is <strong>delta_run_exp</strong> (delta run expectancy),
          derived from MLB Statcast data. This measures how much a plate appearance
          outcome changed the expected runs scored. Before computing ELO, the raw
          value is adjusted for <strong>park factor</strong> (venue scoring environment)
          and <strong>state normalization</strong> (base-out situation average).
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>A home run might have delta_run_exp ≈ +1.4 → batter gains ~17 ELO</li>
          <li>A strikeout might have delta_run_exp ≈ −0.3 → batter loses ~4 ELO</li>
          <li>A walk might have delta_run_exp ≈ +0.3 → batter gains ~4 ELO</li>
          <li>At Coors Field (park factor 1.13), positive outcomes are adjusted down to account for the hitter-friendly park</li>
        </ul>
        <p>
          Higher-impact outcomes produce larger ELO swings, making the system
          responsive to both quality and frequency of plate appearances.
        </p>
      </Accordion>

      <Accordion title="ELO Tier Table">
        <p>
          Players are classified into tiers based on their current ELO rating:
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Tier</th>
                <th className="px-3 py-2 text-left font-semibold">ELO Range</th>
                <th className="px-3 py-2 text-left font-semibold">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-bold text-elo-elite">Elite</td>
                <td className="px-3 py-2">1,800+</td>
                <td className="px-3 py-2">MVP-caliber performance</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-high">High</td>
                <td className="px-3 py-2">1,650 – 1,799</td>
                <td className="px-3 py-2">All-Star level</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-above">Above Avg</td>
                <td className="px-3 py-2">1,550 – 1,649</td>
                <td className="px-3 py-2">Above-average starter</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-average">Average</td>
                <td className="px-3 py-2">1,450 – 1,549</td>
                <td className="px-3 py-2">League average</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-below">Below Avg</td>
                <td className="px-3 py-2">1,350 – 1,449</td>
                <td className="px-3 py-2">Below-average performance</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-low">Low</td>
                <td className="px-3 py-2">1,200 – 1,349</td>
                <td className="px-3 py-2">Struggling performance</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-bold text-elo-cold">Cold</td>
                <td className="px-3 py-2">&lt; 1,200</td>
                <td className="px-3 py-2">Significant slump</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Accordion>

      <Accordion title="Pitcher-Batter Balance">
        <p>
          The zero-sum design ensures a natural balance between pitchers and batters.
          When a batter gains ELO, the opposing pitcher loses the same amount.
        </p>
        <p>
          This creates an intuitive interpretation: a pitcher with high ELO has
          consistently limited batter production, while a batter with high ELO has
          consistently produced against pitchers. Both sides are measured on the
          same scale using the same Statcast-derived run values.
        </p>
        <p>
          The <strong>delta_run_exp</strong> metric from Statcast naturally captures
          this duality — it measures the run value change from the batter's perspective,
          and the pitcher's delta is simply the negative of that value.
        </p>
      </Accordion>

      <Accordion title="Why Pitchers Have Lower Ratings Than Batters">
        <p>
          You may notice that top batters reach ELO ratings above 2,500, while even the
          best pitchers rarely exceed 1,650. This is <strong>not an engine flaw</strong> — it
          is a structural consequence of the zero-sum system combined with the player pool sizes
          in MLB.
        </p>
        <p className="font-semibold text-gray-900 mt-3">The Math</p>
        <p className="mt-1">
          In a zero-sum system, the total ELO gained by all batters equals the total ELO
          lost by all pitchers:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1 mt-2">
          <p>&Sigma; (batting_elo &minus; 1500) + &Sigma; (pitching_elo &minus; 1500) = 0</p>
        </div>
        <p className="mt-2">
          Verified from 2025 season data:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1 mt-2">
          <p>Batter pool:  673 players &times; (+107.3 avg) = <strong>+72,232</strong> total ELO gained</p>
          <p>Pitcher pool: 873 players &times; (&minus;82.7 avg) = <strong>&minus;72,232</strong> total ELO lost</p>
          <p className="text-gray-500 mt-1">Net = 0.0 (zero-sum verified)</p>
        </div>
        <p className="mt-3">
          The same total ELO transfer (+72,232 points) is shared among a <strong>different
          number of players</strong> on each side:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1 mt-2">
          <p>Avg batter gain  = +72,232 / 673 = <strong>+107.3</strong> per batter</p>
          <p>Avg pitcher loss = &minus;72,232 / 873 = <strong>&minus;82.7</strong> per pitcher</p>
        </div>
        <p className="mt-3">
          Because there are <strong>30% more pitchers than batters</strong>, each pitcher absorbs
          a smaller share of the loss, while each batter gets a larger share of the gain. This
          pushes the batter distribution upward and compresses the pitcher distribution downward.
        </p>
        <div className="overflow-x-auto mt-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Pool</th>
                <th className="px-3 py-2 text-left font-semibold">Players</th>
                <th className="px-3 py-2 text-left font-semibold">Mean ELO</th>
                <th className="px-3 py-2 text-left font-semibold">Min</th>
                <th className="px-3 py-2 text-left font-semibold">Max</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-semibold">Batters</td>
                <td className="px-3 py-2">673</td>
                <td className="px-3 py-2">1,607</td>
                <td className="px-3 py-2">1,324</td>
                <td className="px-3 py-2">2,689</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-semibold">Pitchers</td>
                <td className="px-3 py-2">873</td>
                <td className="px-3 py-2">1,417</td>
                <td className="px-3 py-2">876</td>
                <td className="px-3 py-2">1,650</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="font-semibold text-gray-900 mt-4">Why More Pitchers?</p>
        <p className="mt-1">
          MLB rosters carry 13 pitchers (5 starters + 8 relievers) versus 13 position players,
          but the total number of <strong>unique pitchers used across a season</strong> far exceeds
          unique batters. This is driven by:
        </p>
        <ul className="list-disc pl-5 space-y-1 mt-2">
          <li>
            <strong>Frequent minor league shuttling</strong> — Pitchers are optioned to and
            recalled from the minors far more frequently than position players. A reliever
            might appear for a few innings, get optioned, and be replaced by another arm.
          </li>
          <li>
            <strong>Bullpen specialization</strong> — Modern bullpen usage creates demand for
            many short-stint relievers, each contributing a small number of batters faced.
          </li>
          <li>
            <strong>Injury replacement</strong> — Pitcher injuries lead to frequent roster
            churn that doesn't equally affect position players.
          </li>
        </ul>
        <p className="mt-3">
          These short-stint pitchers typically exit the data near ELO 1,500 with a small negative
          offset, contributing to the lower pitcher pool average. Meanwhile, position players hold
          roster spots more stably, accumulating PAs that let skill differentiation compound in
          the ELO.
        </p>
        <p className="font-semibold text-gray-900 mt-4">Key Takeaway</p>
        <p className="mt-1">
          When comparing players across roles, <strong>use role-relative rankings</strong> (percentile
          within batters or within pitchers) rather than raw ELO values. A pitcher at 1,620 ELO is
          elite within the pitching pool, even though that number would be merely above-average
          for a batter. The ELO tier badges on this site reflect absolute thresholds, but the
          leaderboard rankings are always within-role.
        </p>
      </Accordion>

      <Accordion title="Two-Way Players">
        <p>
          Players who both bat and pitch (e.g., Shohei Ohtani) have <strong>two independent ELO
          ratings</strong> — one for batting and one for pitching. Each rating only changes when
          the player acts in that role:
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Batting ELO</strong> updates when the player is at bat. Pitching ELO is unaffected.</li>
          <li><strong>Pitching ELO</strong> updates when the player is on the mound. Batting ELO is unaffected.</li>
          <li>The <strong>Composite ELO</strong> shown on the leaderboard is a weighted average based on PA count in each role.</li>
        </ul>
        <p>
          On a two-way player's profile page, you can switch between{' '}
          <strong>Batting</strong> and <strong>Pitching</strong> tabs to see separate OHLC
          charts and statistics for each role. Two-way players appear in{' '}
          <strong>both</strong> the Batter and Pitcher leaderboard tabs, ranked by their
          role-specific ELO.
        </p>
        <p>
          Look for the{' '}
          <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">TWP</span>{' '}
          badge in search results and leaderboards to identify two-way players.
        </p>
      </Accordion>

      <Accordion title="Reading the OHLC Chart">
        <p>
          Each player's profile includes an <strong>OHLC (Open-High-Low-Close)</strong> chart,
          similar to stock market candlestick charts:
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Open</strong>: ELO at the start of the day (first PA)</li>
          <li><strong>High</strong>: Highest ELO reached during the day</li>
          <li><strong>Low</strong>: Lowest ELO reached during the day</li>
          <li><strong>Close</strong>: ELO at the end of the day (last PA)</li>
        </ul>
        <p>
          <span className="text-green-600 font-semibold">Green candles</span> indicate
          the player's ELO rose that day (close &gt; open), while{' '}
          <span className="text-red-600 font-semibold">red candles</span> indicate
          a decline (close &lt; open). The "wick" shows the intraday range.
        </p>
        <p>
          Moving averages (MA5 and MA15) smooth out daily noise to reveal
          longer-term trends.
        </p>
      </Accordion>

      <Accordion title="Disclaimer">
        <p>
          This demo is based on <strong>MLB Statcast data</strong> covering
          approximately <strong>183,000 plate appearances</strong> across the current season.
        </p>
        <p>
          The ELO ratings shown here are for demonstration and analytical purposes only.
          They represent one possible approach to player evaluation and should not be
          considered definitive assessments of player skill. Many factors (defense,
          baserunning, game context beyond run expectancy) are not captured by this model.
        </p>
        <p>
          Data sourced from MLB Statcast via Baseball Savant.
        </p>
      </Accordion>
    </div>
  );
}

function TalentTab() {
  return (
    <div className="space-y-4">
      <Accordion title="What is Talent ELO?" defaultOpen>
        <p>
          While the main ELO rating captures a player's <strong>overall</strong> performance,
          Talent ELO decomposes that into <strong>specific skill dimensions</strong>. Each
          dimension is tracked independently using a binary matchup model — batter vs. pitcher
          in each skill category.
        </p>
        <p>
          <strong>Batter dimensions (4):</strong> Contact, Power, Discipline, Clutch
        </p>
        <p>
          <strong>Pitcher dimensions (4):</strong> Stuff, BIP Suppression, Command, Clutch
        </p>
        <p>
          There is no composite talent score — each dimension stands on its own. A player
          might be Elite in Power but Average in Contact, giving you a much richer picture
          of their skill profile.
        </p>
      </Accordion>

      <Accordion title="Batting Dimensions">
        <p>Each batting dimension tracks a specific offensive skill:</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Dimension</th>
                <th className="px-3 py-2 text-left font-semibold">What it measures</th>
                <th className="px-3 py-2 text-left font-semibold">Key events (+)</th>
                <th className="px-3 py-2 text-left font-semibold">Key events (-)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-semibold">Contact</td>
                <td className="px-3 py-2">Ability to avoid strikeouts and make contact</td>
                <td className="px-3 py-2">Single, Double, Triple</td>
                <td className="px-3 py-2">Strikeout, Out</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-semibold">Power</td>
                <td className="px-3 py-2">Extra-base hit and home run ability</td>
                <td className="px-3 py-2">HR (1.0), Double (0.7)</td>
                <td className="px-3 py-2">GIDP (-0.7), Out (-0.2)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-semibold">Discipline</td>
                <td className="px-3 py-2">Plate discipline and walk rate</td>
                <td className="px-3 py-2">BB (1.0), HBP (0.8)</td>
                <td className="px-3 py-2">&mdash;</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-semibold">Clutch</td>
                <td className="px-3 py-2">Performance in high-leverage situations (RISP)</td>
                <td className="px-3 py-2">Hits with runners on 2B/3B</td>
                <td className="px-3 py-2">Outs/K with runners on 2B/3B</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Accordion>

      <Accordion title="Pitching Dimensions">
        <p>Each pitching dimension tracks a specific mound skill:</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Dimension</th>
                <th className="px-3 py-2 text-left font-semibold">What it measures</th>
                <th className="px-3 py-2 text-left font-semibold">Key events (+)</th>
                <th className="px-3 py-2 text-left font-semibold">Key events (-)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-semibold">Stuff</td>
                <td className="px-3 py-2">Strikeout-inducing ability (FIP-based)</td>
                <td className="px-3 py-2">Strikeout (1.0)</td>
                <td className="px-3 py-2">HR (-0.8)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-semibold">BIP Supp.</td>
                <td className="px-3 py-2">Batted-ball suppression (BABIP)</td>
                <td className="px-3 py-2">Out (0.4), GIDP (0.5)</td>
                <td className="px-3 py-2">Single (-0.6), Double (-0.8), Triple (-0.9)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-semibold">Command</td>
                <td className="px-3 py-2">Walk prevention and control</td>
                <td className="px-3 py-2">Strikeout (0.3), Out (0.15)</td>
                <td className="px-3 py-2">BB (-1.0), HBP (-0.8)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-semibold">Clutch</td>
                <td className="px-3 py-2">Clutch pitching with runners on base</td>
                <td className="px-3 py-2">Same events, amplified in RISP</td>
                <td className="px-3 py-2">Same events, amplified in RISP</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Accordion>

      <Accordion title="How Talent ELO is Calculated">
        <p>
          Talent ELO uses a <strong>binary matchup model</strong>: each plate appearance pits
          the batter's skill dimension against the pitcher's corresponding dimension
          (e.g., Contact vs. Stuff).
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            Each PA outcome triggers updates to the relevant dimensions based on the result type
            (e.g., a home run updates Power for the batter and Stuff for the pitcher).
          </li>
          <li>
            The ELO expected score uses the difference between the batter's and pitcher's
            dimension ratings to determine the expected outcome.
          </li>
          <li>
            <strong>Reliability</strong> scales from 0.3 to 1.0 as a player accumulates
            qualifying events in each dimension. New players start with dampened updates that
            become full-strength as the sample grows.
          </li>
          <li>
            Each dimension is updated independently — there is no composite talent score.
            A player's skill profile is the full set of dimension ratings.
          </li>
        </ul>
      </Accordion>

      <Accordion title="Important Notes">
        <ul className="list-disc pl-5 space-y-2">
          <li>
            Talent ELO uses the <strong>same tier system</strong> as the main ELO
            (Elite 1,800+, High 1,650+, etc.).
          </li>
          <li>
            Dimensions are <strong>independent</strong> — a player can be Elite in Power but
            Average in Contact. This is by design.
          </li>
          <li>
            Batter Clutch and Pitcher Clutch are <strong>separate ratings</strong> using
            RISP (Runners in Scoring Position) as a proxy for high-leverage situations.
          </li>
          <li>
            BIP Suppression has intentionally <strong>low sensitivity</strong> to suppress
            BABIP noise, consistent with DIPS (Defense Independent Pitching Statistics) theory.
          </li>
          <li>
            Speed dimension is currently <strong>disabled</strong> due to insufficient
            Statcast stolen base data for reliable ELO convergence.
          </li>
        </ul>
      </Accordion>
    </div>
  );
}

function MatchupEngineTab() {
  return (
    <div className="space-y-4">
      <Accordion title="What is the Matchup Predictor?" defaultOpen>
        <p>
          The <strong>Matchup Predictor</strong> forecasts the outcome distribution of a single
          plate appearance between a specific batter and pitcher. Rather than using historical
          head-to-head data (which is sparse), it combines each player's <strong>Talent ELO
          dimensions</strong> to model the interaction from first principles.
        </p>
        <p>
          The prediction runs entirely in the browser — no backend calls needed beyond fetching
          each player's current talent ELO ratings from the database. The algorithm is a direct
          port of the V2.1 z-score matchup predictor.
        </p>
        <p>
          The output is a 7-outcome probability distribution: <strong>BB, K, OUT, 1B, 2B, 3B, HR</strong>,
          plus derived metrics like expected wOBA, on-base percentage, and expected slugging.
        </p>
      </Accordion>

      <Accordion title="Architecture: Browser-Side Prediction">
        <p>
          The entire prediction pipeline runs client-side:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1 overflow-x-auto">
          <p>[User selects Batter + Pitcher]</p>
          <p>{'  '}&rarr; Supabase: fetch talent_player_current for both (2 parallel queries)</p>
          <p>{'  '}&rarr; predictPlateAppearance() &mdash; pure TypeScript math</p>
          <p>{'  '}&rarr; Render: FinalPrediction + MatchupBar + StageResults</p>
        </div>
        <p className="mt-2">
          The <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">predictPlateAppearance()</code> function
          is a <strong>pure function</strong> — no side effects, no network calls, deterministic output.
          Given the same talent ELO inputs, it always produces the same probability distribution.
        </p>
      </Accordion>

      <Accordion title="Input: Talent ELO Dimensions">
        <p>
          The predictor uses <strong>6 talent dimensions</strong> — 3 from the batter and 3 from the pitcher:
        </p>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Role</th>
                <th className="px-3 py-2 text-left font-semibold">Dimension</th>
                <th className="px-3 py-2 text-left font-semibold">What it captures</th>
                <th className="px-3 py-2 text-left font-semibold">Used in</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2">Batter</td>
                <td className="px-3 py-2 font-semibold">Discipline</td>
                <td className="px-3 py-2">Plate discipline, walk rate</td>
                <td className="px-3 py-2">Stage 1 (BB)</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Batter</td>
                <td className="px-3 py-2 font-semibold">Contact</td>
                <td className="px-3 py-2">Ability to make contact, avoid strikeouts</td>
                <td className="px-3 py-2">Stage 1 (K), Stage 2 (Hit)</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Batter</td>
                <td className="px-3 py-2 font-semibold">Power</td>
                <td className="px-3 py-2">Extra-base hit and HR ability</td>
                <td className="px-3 py-2">Stage 3 (XBH)</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Pitcher</td>
                <td className="px-3 py-2 font-semibold">Command</td>
                <td className="px-3 py-2">Walk prevention, control</td>
                <td className="px-3 py-2">Stage 1 (BB)</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Pitcher</td>
                <td className="px-3 py-2 font-semibold">Stuff</td>
                <td className="px-3 py-2">Strikeout-inducing ability</td>
                <td className="px-3 py-2">Stage 1 (K)</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Pitcher</td>
                <td className="px-3 py-2 font-semibold">BIP Suppression</td>
                <td className="px-3 py-2">Batted-ball suppression (BABIP)</td>
                <td className="px-3 py-2">Stage 2 (Hit)</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-sm text-gray-500">
          Clutch dimensions are not used in the predictor — the prediction models a
          context-neutral plate appearance.
        </p>
      </Accordion>

      <Accordion title="Z-Score Normalization">
        <p>
          Raw ELO values are on different scales across dimensions — Discipline ELOs
          have a much wider spread (std ~139) than BIP Suppression (std ~18). Directly
          comparing them would overweight some dimensions.
        </p>
        <p>
          The predictor converts every ELO to a <strong>z-score</strong> using the
          dimension-specific distribution from the 2025 season:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm mt-2">
          z = (ELO &minus; mean) / std
        </div>
        <p className="mt-2">
          After normalization, a z-score of +1.0 means "one standard deviation above average"
          regardless of the dimension. A top-10% batter in Discipline and a top-10% pitcher
          in Command produce the same z-magnitude, creating fair matchup comparisons.
        </p>
        <div className="overflow-x-auto mt-3">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Dimension</th>
                <th className="px-3 py-2 text-left font-semibold">Mean</th>
                <th className="px-3 py-2 text-left font-semibold">Std Dev</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-mono">BATTER_CONTACT</td>
                <td className="px-3 py-2">1504.5</td>
                <td className="px-3 py-2">33.9</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">BATTER_POWER</td>
                <td className="px-3 py-2">1468.6</td>
                <td className="px-3 py-2">61.6</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">BATTER_DISCIPLINE</td>
                <td className="px-3 py-2">1700.3</td>
                <td className="px-3 py-2">139.0</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">PITCHER_STUFF</td>
                <td className="px-3 py-2">1587.3</td>
                <td className="px-3 py-2">56.6</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">PITCHER_BIP_SUPPRESSION</td>
                <td className="px-3 py-2">1513.3</td>
                <td className="px-3 py-2">18.2</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">PITCHER_COMMAND</td>
                <td className="px-3 py-2">1681.1</td>
                <td className="px-3 py-2">126.5</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-sm text-gray-500">
          Values computed from 2025 MLB season talent_player_current table (673 batters, 873 pitchers).
        </p>
      </Accordion>

      <Accordion title="The 3-Stage Decision Tree">
        <p>
          The prediction follows a <strong>sequential 3-stage decision tree</strong> that
          mirrors the natural structure of a plate appearance:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-2 overflow-x-auto mt-2">
          <p className="font-bold">Stage 1: What happens? (3-way Softmax)</p>
          <p>{'  '}P(BB), P(K), P(BIP) &larr; z(Discipline)-z(Command), z(Stuff)-z(Contact)</p>
          <p className="font-bold mt-3">Stage 2: If ball in play, hit or out? (Logistic)</p>
          <p>{'  '}P(Hit|BIP), P(Out|BIP) &larr; z(Contact)-z(BIP_Suppression)</p>
          <p className="font-bold mt-3">Stage 3: If hit, single or extra-base? (Logistic)</p>
          <p>{'  '}P(XBH|Hit), P(1B|Hit) &larr; z(Power)</p>
          <p>{'  '}XBH &rarr; 2B/3B/HR split by league ratios</p>
        </div>
        <p className="mt-3">
          This structure ensures probabilities are properly conditional and always sum to 100%.
          Each stage narrows down from the previous one, producing a complete 7-outcome distribution.
        </p>
      </Accordion>

      <Accordion title="Stage 1: BB / K / BIP (Softmax)">
        <p>
          Stage 1 determines the three top-level outcomes using a <strong>3-way softmax</strong> function.
          The reference category is BIP (ball in play).
        </p>
        <p className="font-semibold mt-2">Z-score diffs:</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>z_disc_cmd</strong> = z(Discipline) &minus; z(Command)
            — positive means the batter has a discipline edge &rarr; more walks
          </li>
          <li>
            <strong>z_stuff_contact</strong> = z(Stuff) &minus; z(Contact)
            — positive means the pitcher has a stuff edge &rarr; more strikeouts
          </li>
        </ul>
        <p className="font-semibold mt-3">Formula:</p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1 overflow-x-auto">
          <p>base_logit_BB = ln(league_bb_rate / league_bip_rate)</p>
          <p>base_logit_K{'  '} = ln(league_k_rate / league_bip_rate)</p>
          <p className="mt-2">logit_BB = base_logit_BB + z_disc_cmd / 3.5</p>
          <p>logit_K{'  '} = base_logit_K + z_stuff_contact / 3.5</p>
          <p className="mt-2">exp_BB = e^logit_BB, {'  '}exp_K = e^logit_K</p>
          <p>Z = exp_BB + exp_K + 1.0</p>
          <p className="mt-2">P(BB) = exp_BB / Z</p>
          <p>P(K){'  '} = exp_K / Z</p>
          <p>P(BIP) = 1.0 / Z</p>
        </div>
        <p className="mt-2">
          The <strong>divisor of 3.5</strong> controls sensitivity: a z-diff of 3.5 (very extreme matchup)
          shifts the logit by 1.0, which roughly doubles/halves the odds ratio. This keeps predictions
          within realistic bounds even for extreme matchups.
        </p>
        <p className="mt-2">
          At league average (z-diffs = 0), the softmax recovers the base rates:
          BB ~9.5%, K ~22.2%, BIP ~68.3%.
        </p>
      </Accordion>

      <Accordion title="Stage 2: Hit / Out given BIP (Logistic)">
        <p>
          Given the ball is in play, Stage 2 determines whether it's a hit or an out
          using a <strong>base-rate logistic</strong> function.
        </p>
        <p className="font-semibold mt-2">Z-score diff:</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>z_contact_bip</strong> = z(Contact) &minus; z(BIP_Suppression)
            — positive means the batter has a contact edge &rarr; higher BABIP
          </li>
        </ul>
        <p className="font-semibold mt-3">Formula:</p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1 overflow-x-auto">
          <p>base_logit = ln(BABIP / (1 &minus; BABIP))</p>
          <p>logit = base_logit + z_contact_bip / 5.0</p>
          <p>P(Hit|BIP) = 1 / (1 + e^(&minus;logit))</p>
          <p className="mt-2">P(Hit) = P(BIP) &times; P(Hit|BIP)</p>
          <p>P(Out) = P(BIP) &times; (1 &minus; P(Hit|BIP))</p>
        </div>
        <p className="mt-2">
          The league average BABIP is <strong>.321</strong>. The divisor of 5.0 makes this stage
          less sensitive than Stage 1, reflecting the high noise inherent in batted-ball outcomes
          (consistent with DIPS theory).
        </p>
      </Accordion>

      <Accordion title="Stage 3: XBH / Single given Hit (Logistic)">
        <p>
          Given a hit, Stage 3 determines whether it's a single or an extra-base hit.
          This stage uses <strong>only the batter's Power z-score</strong> — the pitcher
          has minimal control over hit quality once contact is made.
        </p>
        <p className="font-semibold mt-2">Z-score:</p>
        <ul className="list-disc pl-5 space-y-1">
          <li>
            <strong>z_power</strong> = z(Power)
            — positive means above-average power &rarr; more extra-base hits
          </li>
        </ul>
        <p className="font-semibold mt-3">Formula:</p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1 overflow-x-auto">
          <p>base_logit = ln(xbh_rate / (1 &minus; xbh_rate))</p>
          <p>logit = base_logit + z_power / 5.0</p>
          <p>P(XBH|Hit) = 1 / (1 + e^(&minus;logit))</p>
          <p className="mt-2">P(1B) = P(Hit) &times; (1 &minus; P(XBH|Hit))</p>
          <p>P(XBH) = P(Hit) &times; P(XBH|Hit)</p>
          <p className="mt-2 text-gray-500"># XBH split by league ratios:</p>
          <p>P(2B) = P(XBH) &times; 0.552</p>
          <p>P(3B) = P(XBH) &times; 0.045</p>
          <p>P(HR) = P(XBH) &times; 0.403</p>
        </div>
        <p className="mt-2">
          The XBH-to-hit ratio (2B/3B/HR split) uses fixed league averages because
          the relative distribution of extra-base hit types is remarkably stable across
          player skill levels.
        </p>
      </Accordion>

      <Accordion title="League Average Base Rates (2025 MLB)">
        <p>
          All base rates are computed from 183,092 plate appearances in the 2025 MLB season:
        </p>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Rate</th>
                <th className="px-3 py-2 text-left font-semibold">Value</th>
                <th className="px-3 py-2 text-left font-semibold">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-mono">bb_rate</td>
                <td className="px-3 py-2">9.49%</td>
                <td className="px-3 py-2">Walk rate (BB + IBB + HBP)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">k_rate</td>
                <td className="px-3 py-2">22.18%</td>
                <td className="px-3 py-2">Strikeout rate</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">bip_rate</td>
                <td className="px-3 py-2">68.34%</td>
                <td className="px-3 py-2">Ball in play rate (1 &minus; BB &minus; K)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">BABIP</td>
                <td className="px-3 py-2">.321</td>
                <td className="px-3 py-2">Hit rate on balls in play</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">xbh_rate</td>
                <td className="px-3 py-2">34.93%</td>
                <td className="px-3 py-2">Extra-base hit rate given any hit</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">2B ratio</td>
                <td className="px-3 py-2">55.2%</td>
                <td className="px-3 py-2">Doubles as % of XBH</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">3B ratio</td>
                <td className="px-3 py-2">4.5%</td>
                <td className="px-3 py-2">Triples as % of XBH</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">HR ratio</td>
                <td className="px-3 py-2">40.3%</td>
                <td className="px-3 py-2">Home runs as % of XBH</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Accordion>

      <Accordion title="Output: Expected wOBA and Derived Stats">
        <p>
          The 7-outcome distribution is converted to <strong>expected wOBA</strong> using
          standard linear weights:
        </p>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Outcome</th>
                <th className="px-3 py-2 text-left font-semibold">wOBA Weight</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2">BB</td>
                <td className="px-3 py-2">0.69</td>
              </tr>
              <tr>
                <td className="px-3 py-2">K / OUT</td>
                <td className="px-3 py-2">0.00</td>
              </tr>
              <tr>
                <td className="px-3 py-2">1B</td>
                <td className="px-3 py-2">0.88</td>
              </tr>
              <tr>
                <td className="px-3 py-2">2B</td>
                <td className="px-3 py-2">1.24</td>
              </tr>
              <tr>
                <td className="px-3 py-2">3B</td>
                <td className="px-3 py-2">1.56</td>
              </tr>
              <tr>
                <td className="px-3 py-2">HR</td>
                <td className="px-3 py-2">2.00</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm mt-3">
          expected_wOBA = &Sigma; P(outcome) &times; wOBA_weight(outcome)
        </div>
        <p className="mt-2">Additional derived statistics:</p>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>On-Base %</strong> = P(BB) + P(1B) + P(2B) + P(3B) + P(HR)</li>
          <li><strong>xSLG</strong> = P(1B)&times;1 + P(2B)&times;2 + P(3B)&times;3 + P(HR)&times;4 (expected total bases per PA)</li>
        </ul>
        <p className="mt-2">
          The "<strong>vs avg</strong>" indicator shows how the predicted wOBA compares to the league
          average wOBA (computed from base rates). Positive values favor the batter; negative values
          favor the pitcher.
        </p>
      </Accordion>

      <Accordion title="Sensitivity & Divisor Constants">
        <p>
          The <strong>divisor constants</strong> control how strongly z-score differences shift
          probabilities away from base rates. Smaller divisors = more sensitive:
        </p>
        <div className="overflow-x-auto mt-2">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Stage</th>
                <th className="px-3 py-2 text-left font-semibold">Divisor</th>
                <th className="px-3 py-2 text-left font-semibold">Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2">Stage 1 (BB)</td>
                <td className="px-3 py-2 font-mono">3.5</td>
                <td className="px-3 py-2">Moderate — walks are a controlled outcome</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Stage 1 (K)</td>
                <td className="px-3 py-2 font-mono">3.5</td>
                <td className="px-3 py-2">Moderate — strikeouts are a controlled outcome</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Stage 2 (Hit|BIP)</td>
                <td className="px-3 py-2 font-mono">5.0</td>
                <td className="px-3 py-2">Low sensitivity — BABIP is noisy (DIPS theory)</td>
              </tr>
              <tr>
                <td className="px-3 py-2">Stage 3 (XBH|Hit)</td>
                <td className="px-3 py-2 font-mono">5.0</td>
                <td className="px-3 py-2">Low sensitivity — hit type depends heavily on luck</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-2">
          With these divisors, a z-diff of ±2.0 (roughly top-5% vs bottom-5%) shifts a logit
          by ±0.57 for Stage 1, or ±0.40 for Stages 2-3. This means even extreme matchups
          stay within realistic outcome ranges — a great hitter facing a weak pitcher still
          strikes out sometimes.
        </p>
      </Accordion>

      <Accordion title="Interpreting the Results">
        <p>Here's how to read the Matchup Predictor output:</p>
        <ul className="list-disc pl-5 space-y-2">
          <li>
            <strong>Expected wOBA</strong> is the single best summary stat. League average
            is around .310. Above .350 is a strong batter advantage; below .280 favors the pitcher.
          </li>
          <li>
            <strong>The outcome bar</strong> shows how the 100% probability mass is distributed.
            Look for unusually large blue (BB) or red (K) segments to see where the matchup is
            most lopsided.
          </li>
          <li>
            <strong>Stage cards</strong> show exactly which skill matchups drive the prediction.
            The z-score diffs tell you <em>why</em> — e.g., "Disc-Cmd +1.2" means the batter has
            a 1.2 standard deviation discipline advantage, leading to elevated walk probability.
          </li>
          <li>
            <strong>Average vs. average</strong> should recover league base rates (BB ~9.5%, K ~22%).
            If it doesn't, there's a calibration issue.
          </li>
          <li>
            The model is <strong>context-neutral</strong> — it doesn't account for base-out state,
            game leverage, platoon splits (L/R), or park factors. It models a "generic" PA between
            the two players.
          </li>
        </ul>
      </Accordion>

      <Accordion title="Limitations">
        <ul className="list-disc pl-5 space-y-2">
          <li>
            <strong>No platoon splits</strong> — The model doesn't distinguish left-handed vs
            right-handed matchups, which significantly affect real outcomes.
          </li>
          <li>
            <strong>No situational context</strong> — Base-out state, inning, score, and game
            leverage are not modeled.
          </li>
          <li>
            <strong>Static talent ELO</strong> — The prediction uses current season-end talent
            ratings. It doesn't account for recent form, fatigue, or injury.
          </li>
          <li>
            <strong>No batted-ball quality</strong> — Stage 2 uses aggregate BABIP adjustment but
            doesn't model launch angle, exit velocity, or spray direction.
          </li>
          <li>
            <strong>Fixed XBH split</strong> — The 2B/3B/HR distribution uses league averages
            rather than player-specific power profiles.
          </li>
          <li>
            <strong>Calibration assumes normality</strong> — Z-score normalization works well
            for dimensions with bell-shaped distributions but may distort dimensions with
            skewed or heavy-tailed ELO distributions.
          </li>
        </ul>
      </Accordion>
    </div>
  );
}

function DeveloperTab() {
  return (
    <div className="space-y-4">
      <Accordion title="System Architecture" defaultOpen>
        <p>
          The MLB ELO system follows a simple pipeline architecture:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm overflow-x-auto">
          <p>[Statcast Parquet] → ETL → [Supabase plate_appearances] → ELO Engine → [Supabase player_elo / daily_ohlc]</p>
        </div>
        <p>
          The system uses a <strong>V5.3 Zero-Sum</strong> ELO engine, ported from a KBO
          implementation with full feature parity:
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li>Single-dimension ELO (no separate talent/skill component)</li>
          <li>Single season — no year-over-year normalization</li>
          <li><strong>State normalization</strong> — adjusts for base-out situation (24 states)</li>
          <li><strong>Park factor</strong> — adjusts for venue scoring environment (30 stadiums)</li>
          <li><strong>Field error handling</strong> — prevents unearned ELO credit on errors</li>
          <li>Statcast delta_run_exp as the input metric</li>
        </ul>
      </Accordion>

      <Accordion title="ELO Calculation Formula (V5.3)">
        <p>
          For each plate appearance, the ELO update follows three steps:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-2">
          <p className="text-gray-500"># Step 1: Park factor adjustment</p>
          <p><strong>adjusted_rv</strong> = delta_run_exp − (park_factor − 1.0) × 0.1</p>
          <p className="text-gray-500 mt-2"># Step 2: State normalization</p>
          <p><strong>rv_diff</strong> = adjusted_rv − mean_rv[base_out_state]</p>
          <p className="text-gray-500 mt-2"># Step 3: ELO update (zero-sum)</p>
          <p><strong>batter_delta</strong> = K × rv_diff</p>
          <p><strong>pitcher_delta</strong> = −batter_delta</p>
        </div>
        <p>Parameters:</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Parameter</th>
                <th className="px-3 py-2 text-left font-semibold">Value</th>
                <th className="px-3 py-2 text-left font-semibold">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-mono">K_FACTOR</td>
                <td className="px-3 py-2">12.0</td>
                <td className="px-3 py-2">Sensitivity — higher K means larger swings per PA</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">INITIAL_ELO</td>
                <td className="px-3 py-2">1500.0</td>
                <td className="px-3 py-2">Starting ELO for all players at season start</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">MIN_ELO</td>
                <td className="px-3 py-2">500.0</td>
                <td className="px-3 py-2">Floor — ELO cannot drop below this value</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">ADJUSTMENT_SCALE</td>
                <td className="px-3 py-2">0.1</td>
                <td className="px-3 py-2">Park factor RV adjustment scale</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-2">
          <strong>State normalization</strong> removes systematic bias from base-out
          situations (24 states: 8 base configurations × 3 out states). For example,
          a hit with runners in scoring position carries a higher raw run value than
          with bases empty — the normalization ensures only above-average outcomes
          increase ELO.
        </p>
        <p>
          <strong>Field error handling</strong>: When the result is a fielding error,
          any favorable ELO gain for the batter is zeroed out to prevent unearned credit.
        </p>
      </Accordion>

      <Accordion title="Data Pipeline">
        <p>
          The data flows through three stages:
        </p>
        <h4 className="font-semibold mt-2">1. Raw Data (Statcast)</h4>
        <ul className="list-disc pl-5 space-y-1">
          <li>Source: MLB Statcast via Baseball Savant</li>
          <li>Format: Parquet file (~711K pitches, 118 columns)</li>
          <li>Coverage: Current season (2,428 games)</li>
        </ul>
        <h4 className="font-semibold mt-2">2. ETL (Pitch → PA)</h4>
        <ul className="list-disc pl-5 space-y-1">
          <li>Aggregate pitch-level data to plate appearance level</li>
          <li>Extract: batter_id, pitcher_id, game_date, delta_run_exp</li>
          <li>Result: ~183K plate appearances</li>
        </ul>
        <h4 className="font-semibold mt-2">3. ELO Engine (V5.3)</h4>
        <ul className="list-disc pl-5 space-y-1">
          <li>Load RE24 baseline (mean run value per base-out state) and park factors (30 venues)</li>
          <li>Process PAs chronologically (sorted by game_date, at_bat_number)</li>
          <li>Apply V5.3 formula: park adjustment → state normalization → zero-sum ELO</li>
          <li>Output: per-PA ELO detail + daily OHLC aggregation</li>
        </ul>
      </Accordion>

      <Accordion title="OHLC Tracking">
        <p>
          Daily OHLC (Open-High-Low-Close) values are computed for each player
          who had at least one plate appearance on a given day:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1">
          <p><strong>Open</strong>: ELO before the first PA of the day</p>
          <p><strong>High</strong>: Maximum ELO reached during the day</p>
          <p><strong>Low</strong>: Minimum ELO reached during the day</p>
          <p><strong>Close</strong>: ELO after the last PA of the day</p>
          <p><strong>Delta</strong>: Close − Open (daily change)</p>
        </div>
        <p>
          This allows visualization of daily ELO fluctuations using candlestick
          charts, making it easy to spot hot/cold streaks and turning points
          throughout the season.
        </p>
      </Accordion>

      <Accordion title="Two-Way Player Implementation">
        <p>
          The engine tracks <strong>separate batting and pitching ELO</strong> for every player via
          the <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">PlayerEloState</code> dataclass:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm space-y-1">
          <p>batting_elo:  float  <span className="text-gray-500"># updated only when batting</span></p>
          <p>pitching_elo: float  <span className="text-gray-500"># updated only when pitching</span></p>
          <p>batting_pa:   int    <span className="text-gray-500"># plate appearances as batter</span></p>
          <p>pitching_pa:  int    <span className="text-gray-500"># batters faced as pitcher</span></p>
        </div>
        <p className="mt-2">
          During <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">process_plate_appearance()</code>,
          the batter's <strong>batting_elo</strong> and the pitcher's <strong>pitching_elo</strong> are
          used to compute deltas. Pure batters have a dormant pitching_elo at 1,500, and vice versa.
        </p>
        <p className="mt-2">
          OHLC records are keyed by <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">(player_id, role)</code>,
          where <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">role</code> is either
          {' '}<code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">BATTING</code> or{' '}
          <code className="bg-gray-100 px-1.5 py-0.5 rounded text-sm">PITCHING</code>.
          This means a two-way player generates two OHLC entries per game day — one for each role.
        </p>
        <p className="mt-2">
          The <strong>composite_elo</strong> is a backward-compatible weighted average:
        </p>
        <div className="bg-gray-50 rounded-lg p-4 font-mono text-sm mt-1">
          composite = (batting_elo × batting_pa + pitching_elo × pitching_pa) / total_pa
        </div>
      </Accordion>

      <Accordion title="Database Schema">
        <p>
          The system uses Supabase (PostgreSQL) with the following key tables:
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-3 py-2 text-left font-semibold">Table</th>
                <th className="px-3 py-2 text-left font-semibold">Rows</th>
                <th className="px-3 py-2 text-left font-semibold">Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              <tr>
                <td className="px-3 py-2 font-mono">players</td>
                <td className="px-3 py-2">1,469</td>
                <td className="px-3 py-2">Player metadata (name, team, position)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">plate_appearances</td>
                <td className="px-3 py-2">183,092</td>
                <td className="px-3 py-2">All PAs with delta_run_exp</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">player_elo</td>
                <td className="px-3 py-2">1,469</td>
                <td className="px-3 py-2">Current ELO per player (batting_elo, pitching_elo, composite_elo)</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">elo_pa_detail</td>
                <td className="px-3 py-2">183,092</td>
                <td className="px-3 py-2">Per-PA ELO change records</td>
              </tr>
              <tr>
                <td className="px-3 py-2 font-mono">daily_ohlc</td>
                <td className="px-3 py-2">69,215</td>
                <td className="px-3 py-2">Daily OHLC candlestick data per player per role (BATTING / PITCHING)</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Accordion>

      <Accordion title="Frontend Stack">
        <p>
          This demo frontend is a static SPA that reads directly from Supabase:
        </p>
        <ul className="list-disc pl-5 space-y-1">
          <li><strong>Vite + React + TypeScript</strong> — build toolchain</li>
          <li><strong>Tailwind CSS</strong> — utility-first styling</li>
          <li><strong>@supabase/supabase-js</strong> — direct DB queries (read-only)</li>
          <li><strong>TanStack React Query</strong> — data fetching and caching</li>
          <li><strong>Lightweight Charts</strong> — OHLC candlestick visualization</li>
          <li><strong>React Router</strong> — client-side routing</li>
          <li><strong>Lucide React</strong> — icons</li>
        </ul>
        <p>
          No backend server is required — the frontend connects directly to Supabase
          using a read-only anonymous key with Row Level Security (RLS).
        </p>
      </Accordion>
    </div>
  );
}

export default function Guide() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const { data: seasonMeta } = useSeasonMeta();
  const seasonYear = seasonMeta?.year ?? '';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Guide</h2>
        <span className="text-xs font-medium px-2 py-0.5 rounded bg-primary/10 text-primary">
          {seasonYear} Season
        </span>
      </div>

      {/* Tab Selector */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold transition-all ${
            activeTab === 'overview'
              ? 'bg-primary text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Info className="w-4 h-4" />
          Project Overview
        </button>
        <button
          onClick={() => setActiveTab('general')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold transition-all ${
            activeTab === 'general'
              ? 'bg-primary text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <BookOpen className="w-4 h-4" />
          General
        </button>
        <button
          onClick={() => setActiveTab('talent')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold transition-all ${
            activeTab === 'talent'
              ? 'bg-primary text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          Talent ELO
        </button>
        <button
          onClick={() => setActiveTab('matchup')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold transition-all ${
            activeTab === 'matchup'
              ? 'bg-primary text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Crosshair className="w-4 h-4" />
          Matchup Engine
        </button>
        <button
          onClick={() => setActiveTab('developer')}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold transition-all ${
            activeTab === 'developer'
              ? 'bg-primary text-white'
              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
          }`}
        >
          <Code className="w-4 h-4" />
          Developer
        </button>
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
        {activeTab === 'overview' ? <OverviewTab /> : activeTab === 'general' ? <GeneralTab /> : activeTab === 'talent' ? <TalentTab /> : activeTab === 'matchup' ? <MatchupEngineTab /> : <DeveloperTab />}
      </div>
    </div>
  );
}
