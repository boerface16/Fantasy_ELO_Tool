import { useState, useEffect, useMemo } from 'react';
import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight } from 'lucide-react';
import { useLeaderboard, useSeasonMeta, useFantasyLeaderboard } from '../hooks/useElo';
import LeaderboardTable from '../components/leaderboard/LeaderboardTable';
import FantasyLeaderboardTable from '../components/leaderboard/FantasyLeaderboardTable';

type PositionTab = 'batter' | 'pitcher' | 'batter-fantasy' | 'pitcher-fantasy';

const ESTIMATED_TOTAL = { pitcher: 580, batter: 540, 'batter-fantasy': 540, 'pitcher-fantasy': 580 };

export default function Leaderboard() {
  const [position, setPosition] = useState<PositionTab>('batter');
  const [page, setPage] = useState(1);
  const limit = 20;

  const isFantasyTab = position === 'batter-fantasy' || position === 'pitcher-fantasy';
  const fantasyRole = position === 'pitcher-fantasy' ? 'pitcher' : 'batter';
  const eloPosition = isFantasyTab ? 'batter' : position;

  const { data: players = [], isLoading } = useLeaderboard({ position: eloPosition, page, limit });
  const { data: fantasyPlayers = [], isLoading: fantasyLoading } = useFantasyLeaderboard(fantasyRole, 2026, page, limit);
  const { data: seasonMeta } = useSeasonMeta();

  useEffect(() => {
    setPage(1);
  }, [position]);

  const activeData = isFantasyTab ? fantasyPlayers : players;

  const isLastPage = activeData.length < limit;
  const estimatedTotalPages = Math.ceil(ESTIMATED_TOTAL[position] / limit);
  const totalPages = isLastPage ? page : Math.max(page + 1, estimatedTotalPages);

  const visiblePages = useMemo(() => {
    const pages: number[] = [];
    let start = Math.max(1, page - 2);
    const end = Math.min(totalPages, start + 4);
    start = Math.max(1, end - 4);
    for (let i = start; i <= end; i++) {
      pages.push(i);
    }
    return pages;
  }, [page, totalPages]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Leaderboard</h2>
        <span className="text-xs font-medium px-2 py-0.5 rounded bg-primary/10 text-primary">
          {seasonMeta?.year ?? ''} Season
        </span>
      </div>

      {/* Position Tabs */}
      <div className="flex flex-wrap gap-2">
        {(['batter', 'pitcher', 'batter-fantasy', 'pitcher-fantasy'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setPosition(tab); setPage(1); }}
            className={`px-4 py-2 rounded-lg font-semibold transition-all text-sm ${
              position === tab
                ? 'bg-primary text-white'
                : 'bg-bg-elevated text-text-secondary hover:bg-bg-elevated'
            }`}
          >
            {{ batter: 'Batter', pitcher: 'Pitcher', 'batter-fantasy': 'Batter Fantasy', 'pitcher-fantasy': 'Pitcher Fantasy' }[tab]}
          </button>
        ))}
      </div>

      {/* Table */}
      {isFantasyTab ? (
        <FantasyLeaderboardTable
          players={fantasyPlayers}
          isLoading={fantasyLoading}
          startRank={(page - 1) * limit + 1}
          role={fantasyRole}
        />
      ) : (
        <LeaderboardTable
          players={players}
          isLoading={isLoading}
          startRank={(page - 1) * limit + 1}
          position={position as 'batter' | 'pitcher'}
        />
      )}

      {/* Pagination */}
      <div className="flex items-center justify-center gap-1 py-4">
        <button
          onClick={() => setPage(1)}
          disabled={page === 1}
          className="p-2 rounded-lg hover:bg-bg-elevated disabled:opacity-30 disabled:cursor-not-allowed"
          title="First page"
        >
          <ChevronFirst className="w-5 h-5" />
        </button>

        <button
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
          className="p-2 rounded-lg hover:bg-bg-elevated disabled:opacity-30 disabled:cursor-not-allowed"
          title="Previous page"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-1 mx-2">
          {visiblePages[0] > 1 && (
            <span className="px-2 text-text-secondary">...</span>
          )}
          {visiblePages.map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`min-w-[40px] h-10 rounded-lg font-semibold transition-all ${
                p === page
                  ? 'bg-primary text-white'
                  : 'hover:bg-bg-elevated text-text-primary'
              }`}
            >
              {p}
            </button>
          ))}
          {visiblePages[visiblePages.length - 1] < totalPages && (
            <span className="px-2 text-text-secondary">...</span>
          )}
        </div>

        <button
          onClick={() => setPage(p => p + 1)}
          disabled={isLastPage}
          className="p-2 rounded-lg hover:bg-bg-elevated disabled:opacity-30 disabled:cursor-not-allowed"
          title="Next page"
        >
          <ChevronRight className="w-5 h-5" />
        </button>

        <button
          onClick={() => setPage(totalPages)}
          disabled={isLastPage || page === totalPages}
          className="p-2 rounded-lg hover:bg-bg-elevated disabled:opacity-30 disabled:cursor-not-allowed"
          title="Last page"
        >
          <ChevronLast className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
