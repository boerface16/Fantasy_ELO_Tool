import type { BatterProjection } from '../../types/fantasy';

interface Props {
  batters: BatterProjection[];
}

function wobaColor(woba: number): string {
  if (woba >= 0.370) return 'bg-green-900/30 text-green-400';
  if (woba >= 0.330) return 'bg-green-900/20 text-green-400';
  if (woba >= 0.290) return 'bg-white/5 text-gray-300';
  if (woba >= 0.250) return 'bg-red-900/20 text-red-400';
  return 'bg-red-900/30 text-red-400';
}

export default function DailyGrid({ batters }: Props) {
  if (!batters.length) {
    return <div className="text-center text-gray-400 py-8">No batter projections available</div>;
  }

  const totalPts = batters.reduce((sum, b) => sum + (b.matchups[0]?.expectedPoints ?? 0), 0);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border-line">
            <th className="text-left py-2 px-2 text-xs text-gray-400 uppercase w-12">Slot</th>
            <th className="text-left py-2 px-2 text-xs text-gray-400 uppercase min-w-[140px]">Player</th>
            <th className="text-left py-2 px-2 text-xs text-gray-400 uppercase w-12">Team</th>
            <th className="text-right py-2 px-2 text-xs text-gray-400 uppercase w-14">ELO</th>
            <th className="text-center py-2 px-2 text-xs text-gray-400 uppercase w-28">Today</th>
            <th className="text-right py-2 px-2 text-xs text-gray-400 uppercase w-20">Proj Pts</th>
          </tr>
        </thead>
        <tbody>
          {batters.map((b, idx) => {
            const m = b.matchups[0] ?? null;
            return (
              <tr key={idx} className="border-b border-border-line hover:bg-white/5">
                <td className="py-2 px-2 font-mono text-gray-400 text-xs">{b.slot}</td>
                <td className="py-2 px-2 font-medium">{b.name}</td>
                <td className="py-2 px-2 text-gray-400 font-mono">{b.team}</td>
                <td className="py-2 px-2 text-right font-mono text-xs text-gray-400">{Math.round(b.compositeElo)}</td>
                <td className="py-2 px-2 text-center">
                  {m ? (
                    <div className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${wobaColor(m.expectedWoba)}`}>
                      {m.isHome ? 'vs' : '@'} {m.opponent}
                    </div>
                  ) : (
                    <span className="text-gray-600">—</span>
                  )}
                </td>
                <td className="py-2 px-2 text-right font-bold tabular-nums">
                  {m ? m.expectedPoints.toFixed(1) : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-border-line font-semibold">
            <td colSpan={5} className="py-2 px-2 text-gray-400">Total</td>
            <td className="py-2 px-2 text-right tabular-nums">{totalPts.toFixed(1)}</td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
