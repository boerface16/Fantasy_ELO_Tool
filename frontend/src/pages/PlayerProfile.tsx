import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, TrendingUp, TrendingDown } from 'lucide-react';
import EloCandlestickChart from '../components/player/EloCandlestickChart';
import { getEloTier, getEloTierColor } from '../types/elo';
import { getTeamBorderColor } from '../utils/teamColors';
import { usePlayerElo, usePlayerOhlc, usePlayerStats } from '../hooks/useElo';
import TeamLogo from '../components/common/TeamLogo';
import TalentCardSection from '../components/player/TalentCardSection';

type RoleTab = 'BATTING' | 'PITCHING';

function EloCard({ label, elo, delta, paCount }: { label: string; elo: number; delta: number; paCount: number }) {
  const tier = getEloTier(elo);
  const tierColor = getEloTierColor(tier);
  const DeltaIcon = delta > 0 ? TrendingUp : TrendingDown;
  const deltaColor = delta > 0 ? 'text-delta-up' : delta < 0 ? 'text-delta-down' : 'text-gray-500';
  const deltaSign = delta > 0 ? '+' : '';

  return (
    <div className="text-center p-4 rounded-lg bg-primary/10 ring-2 ring-primary">
      <div className="text-sm text-gray-500 mb-1">{label}</div>
      <div className={`text-3xl font-bold ${tierColor}`}>
        {Math.round(elo)}
      </div>
      <div className={`flex items-center justify-center gap-1 ${deltaColor} mt-1`}>
        <DeltaIcon className="w-4 h-4" />
        <span>{deltaSign}{Math.round(delta)}</span>
      </div>
      <div className="text-xs text-gray-400 mt-1">{paCount} PA</div>
    </div>
  );
}

function StatsGrid({ stats }: { stats: { totalPa: number; avgDelta: number; highestElo: { value: number; date: string }; lowestElo: { value: number; date: string }; avgRange: number } }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      <div>
        <div className="text-sm text-gray-500">Total PA</div>
        <div className="text-xl font-bold text-gray-900">{stats.totalPa}</div>
      </div>
      <div>
        <div className="text-sm text-gray-500">Avg Delta/Day</div>
        <div className={`text-xl font-bold ${stats.avgDelta >= 0 ? 'text-delta-up' : 'text-delta-down'}`}>
          {stats.avgDelta >= 0 ? '+' : ''}{stats.avgDelta.toFixed(1)}
        </div>
      </div>
      <div>
        <div className="text-sm text-gray-500">Highest ELO</div>
        <div className="text-xl font-bold text-elo-elite">{Math.round(stats.highestElo.value)}</div>
        <div className="text-xs text-gray-400">{stats.highestElo.date}</div>
      </div>
      <div>
        <div className="text-sm text-gray-500">Lowest ELO</div>
        <div className="text-xl font-bold text-elo-cold">{Math.round(stats.lowestElo.value)}</div>
        <div className="text-xs text-gray-400">{stats.lowestElo.date}</div>
      </div>
      <div>
        <div className="text-sm text-gray-500">Avg Range</div>
        <div className="text-xl font-bold text-gray-900">{stats.avgRange.toFixed(1)}</div>
      </div>
    </div>
  );
}

function RoleSection({ playerId, role }: { playerId: string; role: RoleTab }) {
  const { data: ohlcData, isLoading: ohlcLoading } = usePlayerOhlc(playerId, role);
  const { data: stats, isLoading: statsLoading } = usePlayerStats(playerId, role);

  if (ohlcLoading || statsLoading) {
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow-sm p-6 h-[400px] animate-pulse">
          <div className="h-full bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow-sm p-6">
        <h3 className="text-lg font-semibold mb-4">
          {role === 'BATTING' ? 'Batting' : 'Pitching'} ELO History
        </h3>
        <EloCandlestickChart data={ohlcData ?? []} height={400} />
      </div>

      {stats && (
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            {role === 'BATTING' ? 'Batting' : 'Pitching'} Statistics
          </h3>
          <StatsGrid stats={stats} />
        </div>
      )}
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
        <Link to="/" className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900">
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>
        <div className="bg-white rounded-lg shadow-sm p-6 animate-pulse">
          <div className="flex items-start gap-6">
            <div className="w-20 h-20 bg-gray-200 rounded-full"></div>
            <div className="flex-1">
              <div className="h-8 bg-gray-200 rounded w-48 mb-2"></div>
              <div className="h-4 bg-gray-200 rounded w-32"></div>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm p-6 h-[400px] animate-pulse">
          <div className="h-full bg-gray-200 rounded"></div>
        </div>
      </div>
    );
  }

  if (!playerElo) {
    return (
      <div className="space-y-6">
        <Link to="/" className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900">
          <ArrowLeft className="w-5 h-5" />
          Back
        </Link>
        <div className="bg-white rounded-lg shadow-sm p-6 text-center text-gray-500">
          Player not found
        </div>
      </div>
    );
  }

  const { player, batting_elo, pitching_elo, batting_pa, pitching_pa } = playerElo;
  const isTwoWay = batting_pa > 0 && pitching_pa > 0;
  const teamColor = getTeamBorderColor(player.team);

  // Determine display role label
  const positionLabel = isTwoWay
    ? 'Two-Way Player'
    : player.position === 'pitcher'
      ? 'Pitcher'
      : 'Batter';

  // For non-TWP, determine primary role
  const primaryRole: RoleTab = player.position === 'pitcher' && !isTwoWay ? 'PITCHING' : 'BATTING';
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
      <Link to="/" className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900">
        <ArrowLeft className="w-5 h-5" />
        Back
      </Link>

      {/* Player Header */}
      <div className="bg-white rounded-lg shadow-sm p-6">
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
            <h1 className="text-2xl font-bold text-gray-900">{player.full_name}</h1>
            <p className="text-gray-600">
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
              <EloCard label="Pitching ELO" elo={pitching_elo} delta={0} paCount={pitching_pa} />
            </div>
          ) : (
            <EloCard
              label="Season ELO"
              elo={displayElo}
              delta={0}
              paCount={displayPa}
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
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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
