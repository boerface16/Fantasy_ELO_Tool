import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight } from 'lucide-react';
import { useTalentLeaderboard } from '../hooks/useTalent';
import { useSeasonMeta } from '../hooks/useElo';
import TalentLeaderboardTable from '../components/talent/TalentLeaderboardTable';
import { ALL_TALENTS, BATTER_TALENTS, PITCHER_TALENTS } from '../types/talent';
import type { TalentMeta } from '../types/talent';

const ESTIMATED_TOTAL: Record<string, number> = {
  batter: 673,
  pitcher: 873,
};

export default function TalentLeaderboard() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialType = searchParams.get('type') || 'contact';
  const initialTab = ALL_TALENTS.find(t => t.type === initialType) || ALL_TALENTS[0];

  const [activeTab, setActiveTab] = useState<TalentMeta>(initialTab);
  const [page, setPage] = useState(1);
  const limit = 20;

  const { data: players = [], isLoading } = useTalentLeaderboard({
    talentType: activeTab.dbType,
    playerRole: activeTab.role,
    page,
    limit,
  });

  const { data: seasonMeta } = useSeasonMeta();

  useEffect(() => {
    setPage(1);
    setSearchParams({ type: activeTab.type }, { replace: true });
  }, [activeTab, setSearchParams]);

  const isLastPage = players.length < limit;
  const estimatedTotalPages = Math.ceil((ESTIMATED_TOTAL[activeTab.role] || 500) / limit);
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
        <h2 className="text-3xl font-bold tracking-tight">Talent Leaderboard</h2>
        <span className="text-xs font-medium px-2 py-0.5 rounded bg-primary/10 text-primary">
          {seasonMeta?.year ?? ''} Season
        </span>
      </div>

      {/* Dimension Tabs */}
      <div className="flex flex-wrap items-start gap-4">
        {/* Batting group */}
        <div className="flex items-center gap-1">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider mr-1">Batting</span>
          {BATTER_TALENTS.map((talent) => (
            <button
              key={talent.type}
              onClick={() => setActiveTab(talent)}
              className={`px-3 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap ${
                activeTab.type === talent.type
                  ? 'bg-primary text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {talent.label}
            </button>
          ))}
        </div>
        {/* Pitching group */}
        <div className="flex items-center gap-1">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider mr-1">Pitching</span>
          {PITCHER_TALENTS.map((talent) => (
            <button
              key={talent.type}
              onClick={() => setActiveTab(talent)}
              className={`px-3 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap ${
                activeTab.type === talent.type
                  ? 'bg-primary text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {talent.label}
            </button>
          ))}
        </div>
      </div>

      {/* Role indicator */}
      <div className="text-sm text-gray-500">
        {activeTab.role === 'batter' ? 'Batter' : 'Pitcher'} dimension
        {' · '}
        {ESTIMATED_TOTAL[activeTab.role] || '—'} players
      </div>

      {/* Table */}
      <TalentLeaderboardTable
        players={players}
        isLoading={isLoading}
        startRank={(page - 1) * limit + 1}
        totalInDimension={ESTIMATED_TOTAL[activeTab.role] || 0}
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
