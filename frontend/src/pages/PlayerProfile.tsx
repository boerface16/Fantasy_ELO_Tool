import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, TrendingUp, TrendingDown } from 'lucide-react';
import EloCandlestickChart from '../components/player/EloCandlestickChart';
import { getEloTier, getEloTierColor } from '../types/elo';
import { getTeamBorderColor } from '../utils/teamColors';
import { usePlayerElo, usePlayerOhlc, usePlayerStats, usePlayerGames } from '../hooks/useElo';
import TeamLogo from '../components/common/TeamLogo';
import TalentCardSection from '../components/player/TalentCardSection';
import type { PlayerGameEntry } from '../api/elo';

type RoleTab = 'BATTING' | 'PITCHING';

function EloCard({ label, elo, delta, paCount, paLabel = 'PA' }: { label: string; elo: number; delta: number; paCount: number; paLabel?: string }) {
  const tier = getEloTier(elo);
  const tierColor = getEloTierColor(tier);
  const DeltaIcon = delta > 0 ? TrendingUp : TrendingDown;
  const deltaColor = delta > 0 ? 'text-delta-up' : delta < 0 ? 'text-delta-down' : 'text-gray-400';
  const deltaSign = delta > 0 ? '+' : '';

  return (
    <div className="text-center p-4 rounded-lg bg-primary/10 ring-2 ring-primary">
      <div className="text-sm text-gray-400 mb-1">{label}</div>
      <div className={`text-3xl font-bold ${tierColor}`}>
        {Math.round(elo)}
      </div>
      <div className={`flex items-center justify-center gap-1 ${deltaColor} mt-1`}>
        <DeltaIcon className="w-4 h-4" />
        <span>{deltaSign}{Math.round(delta)}</span>
      </div>
      <div className="text-xs text-gray-400 mt-1">{paCount} {paLabel}</div>
    </div>
  );
}

function StatsGrid({ stats, role }: { stats: { totalPa: number; avgDelta: number; highestElo: { value: number; date: string }; lowestElo: { value: number; date: string }; avgRange: number }; role: 'BATTING' | 'PITCHING' }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div>
        <div className="text-sm text-gray-400">{role === 'PITCHING' ? 'Total BF' : 'Total PA'}</div>
        <div className="text-xl font-bold text-gray-100">{stats.totalPa}</div>
      </div>
      <div>
        <div className="text-sm text-gray-400">Avg Delta/Day</div>
        <div className={`text-xl font-bold ${stats.avgDelta >= 0 ? 'text-delta-up' : 'text-delta-down'}`}>
          {stats.avgDelta >= 0 ? '+' : ''}{stats.avgDelta.toFixed(1)}
        </div>
      </div>
      <div>
        <div className="text-sm text-gray-400">Highest ELO</div>
        <div className="text-xl font-bold text-elo-elite">{Math.round(stats.highestElo.value)}</div>
        <div className="text-xs text-gray-400">{stats.highestElo.date}</div>
      </div>
      <div>
        <div className="text-sm text-gray-400">Lowest ELO</div>
        <div className="text-xl font-bold text-elo-cold">{Math.round(stats.lowestElo.value)}</div>
        <div className="text-xs text-gray-400">{stats.lowestElo.date}</div>
      </div>
      <div>
        <div className="text-sm text-gray-400">Avg Range</div>
        <div className="text-xl font-bold text-gray-100">{stats.avgRange.toFixed(1)}</div>
      </div>
    </div>
  );
}

function LastGamesTable({ games, role }: { games: PlayerGameEntry[]; role: RoleTab }) {
  if (games.length === 0) {
    return <p className="text-sm text-gray-500">No recent game data available.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-400 border-b border-white/10">
            <th className="pb-2 pr-4 font-medium">Date</th>
            <th className="pb-2 pr-4 font-medium">Opp</th>
            <th className="pb-2 pr-4 font-medium text-right">ELO</th>
            <th className="pb-2 pr-4 font-medium text-right">Δ ELO</th>
            <th className="pb-2 pr-4 font-medium text-right">Pts</th>
            <th className="pb-2 font-medium text-right text-gray-500">
              {role === 'BATTING' ? 'PA / TB / HR / BB / K' : 'IP / H / BB / K'}
            </th>
          </tr>
        </thead>
        <tbody>
          {games.map((g) => {
            const deltaColor = g.eloDelta > 0 ? 'text-delta-up' : g.eloDelta < 0 ? 'text-delta-down' : 'text-gray-400';
            const ptsColor = g.fantasyPoints > 0 ? 'text-delta-up' : g.fantasyPoints < 0 ? 'text-delta-down' : 'text-gray-400';
            const deltaSign = g.eloDelta > 0 ? '+' : '';
            const ptsSign = g.fantasyPoints > 0 ? '+' : '';
            const statsStr = role === 'BATTING'
              ? `${g.stats.pa ?? '–'} / ${g.stats.tb ?? '–'} / ${g.stats.hr ?? '–'} / ${g.stats.bb} / ${g.stats.k}`
              : `${g.stats.ip ?? '–'} / ${g.stats.h ?? '–'} / ${g.stats.bb} / ${g.stats.k}`;

            return (
              <tr key={g.gamePk} className="border-b border-white/5 hover:bg-white/5 transition-colors">
                <td className="py-2 pr-4 text-gray-300">{g.date}</td>
                <td className="py-2 pr-4 font-semibold text-gray-100">{g.opponent}</td>
                <td className="py-2 pr-4 text-right text-gray-200">{g.elo > 0 ? g.elo.toFixed(0) : '—'}</td>
                <td className={`py-2 pr-4 text-right font-medium ${deltaColor}`}>
                  {g.elo > 0 ? `${deltaSign}${g.eloDelta.toFixed(1)}` : '—'}
                </td>
                <td className={`py-2 pr-4 text-right font-semibold ${ptsColor}`}>
                  {ptsSign}{g.fantasyPoints.toFixed(1)}
                </td>
                <td className="py-2 text-right text-gray-500 text-xs">{statsStr}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function RoleSection({ playerId, role }: { playerId: string; role: RoleTab }) {
  const { data: ohlcData, isLoading: ohlcLoading } = usePlayerOhlc(playerId, role);
  const { data: stats, isLoading: statsLoading } = usePlayerStats(playerId, role);
  const { data: recentGames, isLoading: gamesLoading } = usePlayerGames(playerId, role, 5);

  if (ohlcLoading || statsLoading) {
    return (
      <div className="space-y-6">
        <div className="bg-bg-card rounded-lg shadow-sm p-6 h-[400px] animate-pulse">
          <div className="h-full bg-white/15 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-bg-card rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold mb-4">
          {role === 'BATTING' ? 'Batting' : 'Pitching'} ELO History
        </h3>
        <EloCandlestickChart data={ohlcData ?? []} height={400} />
      </div>

      {stats && (
        <div className="bg-bg-card rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-100 mb-4">
            {role === 'BATTING' ? 'Batting' : 'Pitching'} Statistics
          </h3>
          <StatsGrid stats={stats} role={role} />
        </div>
      )}

      <div className="bg-bg-card rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-100 mb-4">Last 5 Games</h3>
        {gamesLoading ? (
          <div className="h-32 bg-white/10 rounded animate-pulse" />
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

  if (eloLoading) {
    return (
      <div className="space-y-6">
        <Link to="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-100">
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>
        <div className="bg-bg-card rounded-lg shadow-sm p-6 animate-pulse">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 bg-white/15 rounded-full"></div>
            <div className="flex-1">
              <div className="h-8 bg-white/15 rounded w-48 mb-2"></div>
              <div className="h-4 bg-white/15 rounded w-32"></div>
            </div>
          </div>
        </div>
        <div className="bg-bg-card rounded-lg shadow-sm p-6 h-[400px] animate-pulse">
          <div className="h-full bg-white/15 rounded"></div>
        </div>
      </div>
    );
  }

  if (!playerElo) {
    return (
      <div className="space-y-6">
        <Link to="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-100">
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>
        <div className="bg-bg-card rounded-lg shadow-sm p-6 text-center text-gray-400">
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

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <Link to="/" className="inline-flex items-center gap-2 text-gray-400 hover:text-gray-100">
        <ArrowLeft className="w-5 h-5" />
        Back
      </Link>

      {/* Player Header */}
      <div className="bg-bg-card rounded-lg shadow-sm p-6">
        <div className="flex items-start gap-6">
          {/* Team Badge */}
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center border-2 overflow-hidden"
            style={{ borderColor: teamColor }}
          >
            <TeamLogo size={72} />
          </div>

          {/* Player Info */}
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-gray-100">{player.full_name}</h1>
            <p className="text-gray-400">
              {player.team} | {positionLabel}
              {isTwoWay && (
                <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-700">
                  TWP
                </span>
              )}
            </p>
          </div>

          {/* ELO Stats */}
          {isTwoWay ? (
            <div className="flex gap-3">
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
                  : 'bg-white/10 text-gray-400 hover:bg-white/15'
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
      <RoleSection playerId={playerId ?? ''} role={currentRole} />
    </div>
  );
}
