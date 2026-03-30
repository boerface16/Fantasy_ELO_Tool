import type { PitcherProjection } from '../../types/fantasy';

interface Props {
  pitchers: PitcherProjection[];
}

function wobaAgainstColor(woba: number): string {
  // Lower wOBA against is better for the pitcher
  if (woba <= 0.270) return 'bg-green-100 text-green-800';
  if (woba <= 0.300) return 'bg-green-50 text-green-700';
  if (woba <= 0.330) return 'bg-gray-50 text-gray-700';
  if (woba <= 0.360) return 'bg-red-50 text-red-700';
  return 'bg-red-100 text-red-800';
}

export default function PitcherGrid({ pitchers }: Props) {
  if (!pitchers.length) {
    return <div className="text-center text-gray-400 py-8">No pitcher projections available</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 px-3 text-xs text-gray-400 uppercase">Pitcher</th>
            <th className="text-left py-2 px-3 text-xs text-gray-400 uppercase w-14">Team</th>
            <th className="text-center py-2 px-3 text-xs text-gray-400 uppercase w-16">Starts</th>
            <th className="text-left py-2 px-3 text-xs text-gray-400 uppercase">Matchups</th>
            <th className="text-right py-2 px-3 text-xs text-gray-400 uppercase w-20">Total Pts</th>
          </tr>
        </thead>
        <tbody>
          {pitchers.map((p, idx) => (
            <tr key={idx} className="border-b border-gray-50 hover:bg-gray-50/50">
              <td className="py-2.5 px-3 font-medium">{p.name}</td>
              <td className="py-2.5 px-3 text-gray-600">{p.team}</td>
              <td className="py-2.5 px-3 text-center tabular-nums">{p.starts}</td>
              <td className="py-2.5 px-3">
                <div className="flex gap-2 flex-wrap">
                  {p.matchups.map((m, i) => (
                    <div
                      key={i}
                      className={`rounded px-2 py-1 text-xs font-medium ${wobaAgainstColor(m.expectedWoba)}`}
                    >
                      <div>{m.isHome ? 'vs' : '@'} {m.opponent}</div>
                      <div className="tabular-nums font-semibold">{m.expectedPoints.toFixed(1)} pts</div>
                    </div>
                  ))}
                </div>
              </td>
              <td className="py-2.5 px-3 text-right font-bold tabular-nums">{p.totalPoints.toFixed(1)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-gray-200 font-semibold">
            <td colSpan={4} className="py-2 px-3 text-gray-500">Total</td>
            <td className="py-2 px-3 text-right tabular-nums">
              {pitchers.reduce((sum, p) => sum + p.totalPoints, 0).toFixed(1)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
