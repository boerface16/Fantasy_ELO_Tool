import { useState, useEffect, useMemo } from 'react';
import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight } from 'lucide-react';
import { useLeaderboard, useSeasonMeta } from '../hooks/useElo';
import LeaderboardTable from '../components/leaderboard/LeaderboardTable';

type PositionTab = 'batter' | 'pitcher';

const ESTIMATED_TOTAL = { pitcher: 580, batter: 540 };

export default function Leaderboard() {
  const [position, setPosition] = useState<PositionTab>('batter');
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data: players = [], isLoading } = useLeaderboard({ position, page, limit });
  const { data: seasonMeta } = useSeasonMeta();

  useEffect(() => {
    setPage(1);
  }, [position]);

  const isLastPage = players.length < limit;
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
      <div className="flex gap-2">
        {(['batter', 'pitcher'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setPosition(tab); setPage(1); }}
            className={`px-6 py-2 rounded-lg font-semibold transition-all ${
              position === tab
                ? 'bg-primary text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {tab === 'pitcher' ? 'Pitcher' : 'Batter'}
          </button>
        ))}
      </div>

      {/* Table */}
      <LeaderboardTable
        players={players}
        isLoading={isLoading}
        startRank={(page - 1) * limit + 1}
        position={position}
      />

      {/* Pagination */}
      <div className="flex items-center justify-center gap-1 py-4">
        <button
          onClick={() => setPage(1)}
          disabled={page === 1}
          className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          title="First page"
        >
          <ChevronFirst className="w-5 h-5" />
        </button>

        <button
          onClick={() => setPage(p => Math.max(1, p - 1))}
          disabled={page === 1}
          className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Previous page"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-1 mx-2">
          {visiblePages[0] > 1 && (
            <span className="px-2 text-gray-400">...</span>
          )}
          {visiblePages.map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`min-w-[40px] h-10 rounded-lg font-semibold transition-all ${
                p === page
                  ? 'bg-primary text-white'
                  : 'hover:bg-gray-100 text-gray-700'
              }`}
            >
              {p}
            </button>
          ))}
          {visiblePages[visiblePages.length - 1] < totalPages && (
            <span className="px-2 text-gray-400">...</span>
          )}
        </div>

        <button
          onClick={() => setPage(p => p + 1)}
          disabled={isLastPage}
          className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Next page"
        >
          <ChevronRight className="w-5 h-5" />
        </button>

        <button
          onClick={() => setPage(totalPages)}
          disabled={isLastPage || page === totalPages}
          className="p-2 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
          title="Last page"
        >
          <ChevronLast className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
