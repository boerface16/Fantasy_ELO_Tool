import { Users, BarChart3, Medal } from 'lucide-react';

interface LeagueSummaryProps {
  activePlayersCount: number;
  averageElo: number;
  eliteCount: number;
  isLoading?: boolean;
}

export default function LeagueSummary({ activePlayersCount, averageElo, eliteCount, isLoading }: LeagueSummaryProps) {
  if (isLoading) {
    return (
      <footer className="mt-12 bg-white p-6 rounded-2xl shadow-modern border border-gray-100 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-32 mb-6"></div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="bg-gray-200 p-3 rounded-full w-11 h-11"></div>
              <div>
                <div className="h-6 bg-gray-200 rounded w-16 mb-1"></div>
                <div className="h-4 bg-gray-200 rounded w-24"></div>
              </div>
            </div>
          ))}
        </div>
      </footer>
    );
  }

  return (
    <footer className="mt-12 bg-white p-6 rounded-2xl shadow-modern border border-gray-100">
      <h4 className="text-xs font-bold uppercase tracking-[0.2em] text-gray-500 mb-6 border-b border-gray-50 pb-2">
        League Summary
      </h4>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <div className="flex items-center gap-4">
          <div className="bg-primary/10 p-3 rounded-full">
            <Users className="w-5 h-5 text-primary" />
          </div>
          <div>
            <p className="text-2xl font-bold">{activePlayersCount}</p>
            <p className="text-sm text-gray-500">Active Players</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="bg-green-100 p-3 rounded-full">
            <BarChart3 className="w-5 h-5 text-green-700" />
          </div>
          <div>
            <p className="text-2xl font-bold">{averageElo}</p>
            <p className="text-sm text-gray-500">Average League ELO</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="bg-elo-elite/10 p-3 rounded-full">
            <Medal className="w-5 h-5 text-elo-elite" />
          </div>
          <div>
            <p className="text-2xl font-bold text-elo-elite">{eliteCount}</p>
            <p className="text-sm text-gray-500">Elite Tier (1800+)</p>
          </div>
        </div>
      </div>
    </footer>
  );
}
