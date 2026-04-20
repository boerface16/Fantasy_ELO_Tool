import { useState, useEffect } from 'react';
import { useQueries } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, TrendingUp, TrendingDown, GitCompare } from 'lucide-react';
import EloCandlestickChart from '../components/player/EloCandlestickChart';
import EloCompareChart from '../components/player/EloCompareChart';
import PlayerCompareSearch from '../components/player/PlayerCompareSearch';
import type { ComparedPlayer } from '../components/player/PlayerCompareSearch';
import type { CompareSeries } from '../components/player/EloCompareChart';
import { getEloTier, getEloTierColor } from '../types/elo';
import { getTeamBorderColor } from '../utils/teamColors';
import { usePlayerElo, usePlayerOhlc, usePlayerStats, usePlayerGames, useSeasonMeta, usePlayerStatLine } from '../hooks/useElo';
import { usePlayerTalentOhlc } from '../hooks/useTalent';
import { BATTER_TALENTS, PITCHER_TALENTS } from '../types/talent';
import TeamLogo from '../components/common/TeamLogo';
import TalentCardSection from '../components/player/TalentCardSection';
import StatLine from '../components/player/StatLine';
import type { PlayerGameEntry } from '../api/elo';
import * as eloApi from '../api/elo';
import * as talentApi from '../api/talent';

const PLAYER_COLORS = ['#ffb000', '#648fff', '#fe6100', '#dc267f', '#785ef0'];

type RoleTab = 'BATTING' | 'PITCHING';

function EloCard({ label, elo, delta, paCount, paLabel = 'PA' }: { label: string; elo: number; delta: number; paCount: number; paLabel?: string }) {
  const tier = getEloTier(elo);
  const tierColor = getEloTierColor(tier);
  const DeltaIcon = delta > 0 ? TrendingUp : TrendingDown;
  const deltaColor = delta > 0 ? 'text-delta-up' : delta < 0 ? 'text-delta-down' : 'text-text-secondary';
  const deltaSign = delta > 0 ? '+' : '';

  return (
    <div className="text-center p-4 rounded-lg bg-primary/10 ring-2 ring-primary">
      <div className="text-sm text-text-secondary mb-1">{label}</div>
      <div className={`text-3xl font-bold ${tierColor}`}>
        {Math.round(elo)}
      </div>
      <div className={`flex items-center justify-center gap-1 ${deltaColor} mt-1`}>
        <DeltaIcon className="w-4 h-4" />
        <span>{deltaSign}{Math.round(delta)}</span>
      </div>
      <div className="text-xs text-text-secondary mt-1">{paCount} {paLabel}</div>
    </div>
  );
}

function StatsGrid({ stats, role }: { stats: { totalPa: number; avgDelta: number; highestElo: { value: number; date: string }; lowestElo: { value: number; date: string }; avgRange: number }; role: 'BATTING' | 'PITCHING' }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div>
        <div className="text-sm text-text-secondary">{role === 'PITCHING' ? 'Total BF' : 'Total PA'}</div>
        <div className="text-xl font-bold text-text-primary">{stats.totalPa}</div>
      </div>
      <div>
        <div className="text-sm text-text-secondary">Avg Delta/Day</div>
        <div className={`text-xl font-bold ${stats.avgDelta >= 0 ? 'text-delta-up' : 'text-delta-down'}`}>
          {stats.avgDelta >= 0 ? '+' : ''}{stats.avgDelta.toFixed(1)}
        </div>
      </div>
      <div>
        <div className="text-sm text-text-secondary">Highest ELO</div>
        <div className="text-xl font-bold text-elo-elite">{Math.round(stats.highestElo.value)}</div>
        <div className="text-xs text-text-secondary">{stats.highestElo.date}</div>
      </div>
      <div>
        <div className="text-sm text-text-secondary">Lowest ELO</div>
        <div className="text-xl font-bold text-elo-cold">{Math.round(stats.lowestElo.value)}</div>
        <div className="text-xs text-text-secondary">{stats.lowestElo.date}</div>
      </div>
      <div>
        <div className="text-sm text-text-secondary">Avg Range</div>
        <div className="text-xl font-bold text-text-primary">{stats.avgRange.toFixed(1)}</div>
      </div>
    </div>
  );
}

function formatIp(ip: number | undefined): string {
  if (ip == null) return '–';
  const full = Math.floor(ip);
  const outs = Math.round((ip - full) * 3);
  return outs === 0 ? `${full}` : `${full}.${outs}`;
}

function LastGamesTable({ games, role }: { games: PlayerGameEntry[]; role: RoleTab }) {
  if (games.length === 0) {
    return <p className="text-sm text-text-tertiary">No recent game data available.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-text-secondary border-b border-border-line">
            <th className="pb-2 pr-4 font-medium">Date</th>
            <th className="pb-2 pr-4 font-medium">Opp</th>
            <th className="pb-2 pr-4 font-medium text-right">ELO</th>
            <th className="pb-2 pr-4 font-medium text-right">Δ ELO</th>
            <th className="pb-2 pr-4 font-medium text-right">Pts</th>
            <th className="pb-2 font-medium text-right text-text-tertiary">
              {role === 'BATTING' ? 'PA / TB / HR / BB / K' : 'IP / H / ER / HR / BB / K'}
            </th>
          </tr>
        </thead>
        <tbody>
          {games.map((g) => {
            const deltaColor = g.eloDelta > 0 ? 'text-delta-up' : g.eloDelta < 0 ? 'text-delta-down' : 'text-text-secondary';
            const ptsColor = g.fantasyPoints > 0 ? 'text-delta-up' : g.fantasyPoints < 0 ? 'text-delta-down' : 'text-text-secondary';
            const deltaSign = g.eloDelta > 0 ? '+' : '';
            const ptsSign = g.fantasyPoints > 0 ? '+' : '';
            const statsStr = role === 'BATTING'
              ? `${g.stats.pa ?? '–'} / ${g.stats.tb ?? '–'} / ${g.stats.hr ?? '–'} / ${g.stats.bb} / ${g.stats.k}`
              : `${formatIp(g.stats.ip)} / ${g.stats.h ?? '–'} / ${g.stats.er ?? '–'} / ${g.stats.hr ?? '–'} / ${g.stats.bb} / ${g.stats.k}`;

            return (
              <tr key={g.gamePk} className="border-b border-white/5 hover:bg-bg-elevated/60 transition-colors">
                <td className="py-2 pr-4 text-text-primary">{g.date}</td>
                <td className="py-2 pr-4 font-semibold text-text-primary">{g.opponent}</td>
                <td className="py-2 pr-4 text-right text-text-primary">{g.elo > 0 ? g.elo.toFixed(0) : '—'}</td>
                <td className={`py-2 pr-4 text-right font-medium ${deltaColor}`}>
                  {g.elo > 0 ? `${deltaSign}${g.eloDelta.toFixed(1)}` : '—'}
                </td>
                <td className={`py-2 pr-4 text-right font-semibold ${ptsColor}`}>
                  {ptsSign}{g.fantasyPoints.toFixed(1)}
                </td>
                <td className="py-2 text-right text-text-tertiary text-xs">{statsStr}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RoleSection({
  playerId,
  role,
  playerName,
  playerTeam,
}: {
  playerId: string;
  role: RoleTab;
  playerName: string;
  playerTeam: string;
}) {
  const [eloView, setEloView] = useState<string>('main');
  const [chartScope, setChartScope] = useState<'season' | 'all'>('season');
  const [compareMode, setCompareMode] = useState(false);
  const [comparedPlayers, setComparedPlayers] = useState<ComparedPlayer[]>([]);
  const { data: seasonMeta } = useSeasonMeta();
  const seasonYear = seasonMeta?.year ?? new Date().getFullYear();
  const scopeSeason = chartScope === 'season' ? seasonYear : undefined;

  // Reset to main ELO and clear compare when role changes (two-way players)
  useEffect(() => {
    setEloView('main');
    setCompareMode(false);
    setComparedPlayers([]);
  }, [role]);

  const { data: ohlcData, isLoading: ohlcLoading } = usePlayerOhlc(playerId, role, scopeSeason);
  const { data: talentOhlcData, isLoading: talentOhlcLoading } = usePlayerTalentOhlc(
    playerId,
    eloView !== 'main' ? eloView : '',
    scopeSeason,
  );
  const { data: stats, isLoading: statsLoading } = usePlayerStats(playerId, role);
  const { data: recentGames, isLoading: gamesLoading } = usePlayerGames(playerId, role, 5);

  // Fetch OHLC for compared players (main ELO)
  const compareMainQueries = useQueries({
    queries: comparedPlayers.map(p => ({
      queryKey: ['playerOhlc', p.playerId, role, scopeSeason],
      queryFn: () => eloApi.getPlayerOhlc(p.playerId, role, scopeSeason),
      staleTime: 60_000,
      enabled: compareMode,
    })),
  });

  // Fetch OHLC for compared players (talent)
  const compareTalentQueries = useQueries({
    queries: comparedPlayers.map(p => ({
      queryKey: ['playerTalentOhlc', p.playerId, eloView, scopeSeason],
      queryFn: () => talentApi.getPlayerTalentOhlc(p.playerId, eloView, scopeSeason),
      staleTime: 60_000,
      enabled: compareMode && eloView !== 'main',
    })),
  });

  const talentList = role === 'PITCHING' ? PITCHER_TALENTS : BATTER_TALENTS;
  const chartData = eloView === 'main' ? (ohlcData ?? []) : (talentOhlcData ?? []);
  const chartTitle = eloView === 'main'
    ? `${role === 'BATTING' ? 'Batting' : 'Pitching'} ELO History`
    : `${talentList.find(t => t.dbType === eloView)?.label ?? eloView} ELO History`;
  const chartLoading = eloView === 'main' ? ohlcLoading : talentOhlcLoading;

  const currentPlayer: ComparedPlayer = { playerId, name: playerName, team: playerTeam };

  const compareSeries: CompareSeries[] = [
    { playerId, name: playerName, team: playerTeam, color: PLAYER_COLORS[0], data: chartData },
    ...comparedPlayers.map((p, i) => ({
      playerId: p.playerId,
      name: p.name,
      team: p.team,
      color: PLAYER_COLORS[i + 1],
      data: (eloView === 'main'
        ? compareMainQueries[i]?.data
        : compareTalentQueries[i]?.data) ?? [],
    })),
  ];

  if ((ohlcLoading && eloView === 'main') || statsLoading) {
    return (
      <div className="space-y-6">
        <div className="bg-bg-card rounded-lg shadow-modern p-6 h-[400px] animate-pulse">
          <div className="h-full bg-bg-elevated/60 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-bg-card rounded-lg shadow-modern p-6">
        {/* Chart header */}
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-semibold">{chartTitle}</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => {
                setCompareMode(m => !m);
                if (compareMode) setComparedPlayers([]);
              }}
              className={`flex items-center gap-1.5 px-3 py-1 rounded text-xs font-semibold transition-all ${
                compareMode
                  ? 'bg-primary text-white'
                  : 'bg-bg-elevated text-text-secondary hover:bg-bg-elevated'
              }`}
            >
              <GitCompare className="w-3.5 h-3.5" />
              Compare
            </button>
            {(['season', 'all'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setChartScope(s)}
                className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
                  chartScope === s ? 'bg-primary text-white' : 'bg-bg-elevated text-text-secondary hover:bg-bg-elevated'
                }`}
              >
                {s === 'season' ? `${seasonYear}` : 'All Time'}
              </button>
            ))}
          </div>
        </div>

        {/* ELO view toggle buttons */}
        <div className="flex flex-wrap gap-1 mb-4">
          <button
            onClick={() => setEloView('main')}
            className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
              eloView === 'main' ? 'bg-primary text-white' : 'bg-bg-elevated text-text-secondary hover:bg-bg-elevated'
            }`}
          >
            Main ELO
          </button>
          {talentList.map((t) => (
            <button
              key={t.type}
              onClick={() => setEloView(t.dbType)}
              className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
                eloView === t.dbType ? 'bg-primary text-white' : 'bg-bg-elevated text-text-secondary hover:bg-bg-elevated'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Compare search UI */}
        {compareMode && (
          <div className="mb-4 p-3 rounded-lg bg-bg-elevated/40 border border-border-line">
            <PlayerCompareSearch
              currentPlayer={currentPlayer}
              role={role}
              compared={comparedPlayers}
              colors={PLAYER_COLORS}
              onAdd={(p) => setComparedPlayers(prev => [...prev, p])}
              onRemove={(id) => setComparedPlayers(prev => prev.filter(p => p.playerId !== id))}
            />
          </div>
        )}

        {/* Chart */}
        {chartLoading ? (
          <div className="h-[400px] bg-bg-elevated/50 rounded animate-pulse" />
        ) : compareMode ? (
          <EloCompareChart series={compareSeries} height={400} />
        ) : (
          <EloCandlestickChart data={chartData} height={400} />
        )}
      </div>

      {stats && (
        <div className="bg-bg-card rounded-lg shadow-modern p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            {role === 'BATTING' ? 'Batting' : 'Pitching'} Statistics
          </h3>
          <StatsGrid stats={stats} role={role} />
        </div>
      )}

      <div className="bg-bg-card rounded-lg shadow-modern p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">Last 5 Games</h3>
        {gamesLoading ? (
          <div className="h-32 bg-bg-elevated/50 rounded animate-pulse" />
        ) : (
          <LastGamesTable games={recentGames ?? []} role={role} />
        )}
      </div>
    </div>
  );
}

export default function PlayerProfile() {
  const { playerId } = useParams<{ playerId: string }>();
  const [activeRole, setActiveRole] = useState<RoleTab>('BATTING');

  const { data: playerElo, isLoading: eloLoading } = usePlayerElo(playerId ?? '');
  const { data: seasonMeta } = useSeasonMeta();
  const seasonYear = seasonMeta?.year ?? new Date().getFullYear();

  // Must be called unconditionally before any early returns (Rules of Hooks)
  const { data: statLineBatter } = usePlayerStatLine(playerId ?? '', 'batter', seasonYear);
  const { data: statLinePitcher } = usePlayerStatLine(playerId ?? '', 'pitcher', seasonYear);

  if (eloLoading) {
    return (
      <div className="space-y-6">
        <Link to="/" className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary">
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>
        <div className="bg-bg-card rounded-lg shadow-modern p-6 animate-pulse">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 bg-bg-elevated/60 rounded-full"></div>
            <div className="flex-1">
              <div className="h-8 bg-bg-elevated/60 rounded w-48 mb-2"></div>
              <div className="h-4 bg-bg-elevated/60 rounded w-32"></div>
            </div>
          </div>
        </div>
        <div className="bg-bg-card rounded-lg shadow-modern p-6 h-[400px] animate-pulse">
          <div className="h-full bg-bg-elevated/60 rounded"></div>
        </div>
      </div>
    );
  }

  if (!playerElo) {
    return (
      <div className="space-y-6">
        <Link to="/" className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary">
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>
        <div className="bg-bg-card rounded-lg shadow-modern p-6 text-center text-text-secondary">
          Player not found
        </div>
      </div>
    );
  }

  const { player, batting_elo, pitching_elo, batting_pa, pitching_pa } = playerElo;
  const isTwoWay = batting_pa > 0 && pitching_pa > 0;
  const teamColor = getTeamBorderColor(player.team);

  // Determine primary role — use PA data if available, fall back to position code
  const isPitcher = pitching_pa > 0
    ? pitching_pa >= batting_pa
    : ['SP', 'RP', 'P'].includes(player.position);

  const positionLabel = isTwoWay ? 'Two-Way Player' : isPitcher ? 'Pitcher' : 'Batter';
  const primaryRole: RoleTab = isPitcher && !isTwoWay ? 'PITCHING' : 'BATTING';
  const displayElo = isTwoWay
    ? (activeRole === 'BATTING' ? batting_elo : pitching_elo)
    : (primaryRole === 'PITCHING' ? pitching_elo : batting_elo);
  const displayPa = isTwoWay
    ? (activeRole === 'BATTING' ? batting_pa : pitching_pa)
    : (primaryRole === 'PITCHING' ? pitching_pa : batting_pa);

  // For delta, we use the role-filtered OHLC (loaded in RoleSection), so show 0 here
  const currentRole = isTwoWay ? activeRole : primaryRole;

  const displayStatLine = currentRole === 'PITCHING' ? statLinePitcher : statLineBatter;

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <Link to="/" className="inline-flex items-center gap-2 text-text-secondary hover:text-text-primary">
        <ArrowLeft className="w-5 h-5" />
        Back
      </Link>

      {/* Player Header */}
      <div className="bg-bg-card rounded-lg shadow-modern p-6">
        <div className="flex flex-col sm:flex-row items-start gap-4 sm:gap-6">
          {/* Team Badge */}
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center border-2 overflow-hidden"
            style={{ borderColor: teamColor }}
          >
            <TeamLogo size={72} />
          </div>

          {/* Player Info */}
          <div className="flex-1 min-w-0">
            <h1 className="text-2xl font-bold text-text-primary">{player.full_name}</h1>
            <p className="text-text-secondary">
              {player.team} | {positionLabel}
              {isTwoWay && (
                <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded bg-amber-900/40 text-amber-400">
                  TWP
                </span>
              )}
            </p>
            {displayStatLine && (
              <StatLine data={displayStatLine} role={currentRole} />
            )}
          </div>

          {/* ELO Stats */}
          {isTwoWay ? (
            <div className="flex flex-wrap gap-3">
              <EloCard label="Batting ELO" elo={batting_elo} delta={0} paCount={batting_pa} />
              <EloCard label="Pitching ELO" elo={pitching_elo} delta={0} paCount={pitching_pa} paLabel="BF" />
            </div>
          ) : (
            <EloCard
              label="Season ELO"
              elo={displayElo}
              delta={0}
              paCount={displayPa}
              paLabel={primaryRole === 'PITCHING' ? 'BF' : 'PA'}
            />
          )}
        </div>
      </div>

      {/* TWP Role Tabs */}
      {isTwoWay && (
        <div className="flex gap-2">
          {(['BATTING', 'PITCHING'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveRole(tab)}
              className={`px-6 py-2 rounded-lg font-semibold transition-all ${
                activeRole === tab
                  ? 'bg-primary text-white'
                  : 'bg-bg-elevated text-text-secondary hover:bg-bg-elevated'
              }`}
            >
              {tab === 'BATTING' ? 'Batting' : 'Pitching'}
            </button>
          ))}
        </div>
      )}

      {/* Talent Cards */}
      <TalentCardSection
        playerId={playerId ?? ''}
        position={currentRole === 'PITCHING' ? 'pitcher' : 'batter'}
      />
      {/* Chart + Stats (role-filtered) */}
      <RoleSection
        playerId={playerId ?? ''}
        role={currentRole}
        playerName={player.full_name}
        playerTeam={player.team}
      />
    </div>
  );
}
