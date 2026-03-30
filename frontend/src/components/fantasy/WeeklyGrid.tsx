import type { BatterProjection } from '../../types/fantasy';

interface Props {
  batters: BatterProjection[];
  weekStart: string;
}

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function getWeekDates(weekStart: string): string[] {
  const dates: string[] = [];
  const start = new Date(weekStart + 'T12:00:00');
  for (let i = 0; i < 7; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    dates.push(d.toISOString().split('T')[0]);
  }
  return dates;
}

function wobaColor(woba: number): string {
  if (woba >= 0.370) return 'bg-green-100 text-green-800';
  if (woba >= 0.330) return 'bg-green-50 text-green-700';
  if (woba >= 0.290) return 'bg-gray-50 text-gray-700';
  if (woba >= 0.250) return 'bg-red-50 text-red-700';
  return 'bg-red-100 text-red-800';
}

export default function WeeklyGrid({ batters, weekStart }: Props) {
  const weekDates = getWeekDates(weekStart);

  if (!batters.length) {
    return <div className="text-center text-gray-400 py-8">No batter projections available</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="text-left py-2 px-2 text-xs text-gray-400 uppercase w-12">Slot</th>
            <th className="text-left py-2 px-2 text-xs text-gray-400 uppercase min-w-[140px]">Player</th>
            <th className="text-left py-2 px-2 text-xs text-gray-400 uppercase w-12">Team</th>
            {DAY_LABELS.map((day, i) => (
              <th key={i} className="text-center py-2 px-2 text-xs text-gray-400 uppercase w-20">
                {day}
              </th>
            ))}
            <th className="text-right py-2 px-2 text-xs text-gray-400 uppercase w-16">Total</th>
            <th className="text-right py-2 px-2 text-xs text-gray-400 uppercase w-16">PPG</th>
          </tr>
        </thead>
        <tbody>
          {batters.map((b, idx) => {
            const matchupByDate: Record<string, typeof b.matchups[0]> = {};
            for (const m of b.matchups) {
              matchupByDate[m.date] = m;
            }

            return (
              <tr key={idx} className="border-b border-gray-50 hover:bg-gray-50/50">
                <td className="py-2 px-2 font-mono text-gray-500 text-xs">{b.slot}</td>
                <td className="py-2 px-2 font-medium">{b.name}</td>
                <td className="py-2 px-2 text-gray-600">{b.team}</td>
                {weekDates.map((date) => {
                  const m = matchupByDate[date];
                  if (!m) {
                    return <td key={date} className="py-2 px-2 text-center text-gray-300">—</td>;
                  }
                  return (
                    <td key={date} className="py-2 px-1 text-center">
                      <div className={`rounded px-1.5 py-0.5 text-xs font-medium ${wobaColor(m.expectedWoba)}`}>
                        <div>{m.isHome ? 'vs' : '@'} {m.opponent}</div>
                        <div className="tabular-nums font-semibold">{m.expectedPoints.toFixed(1)}</div>
                      </div>
                    </td>
                  );
                })}
                <td className="py-2 px-2 text-right font-bold tabular-nums">{b.totalPoints.toFixed(1)}</td>
                <td className="py-2 px-2 text-right text-gray-600 tabular-nums">{b.pointsPerGame.toFixed(1)}</td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-gray-200 font-semibold">
            <td colSpan={3} className="py-2 px-2 text-gray-500">Total</td>
            {weekDates.map((date) => {
              const dayTotal = batters.reduce((sum, b) => {
                const m = b.matchups.find((m) => m.date === date);
                return sum + (m?.expectedPoints ?? 0);
              }, 0);
              return (
                <td key={date} className="py-2 px-2 text-center tabular-nums">
                  {dayTotal > 0 ? dayTotal.toFixed(1) : '—'}
                </td>
              );
            })}
            <td className="py-2 px-2 text-right tabular-nums">
              {batters.reduce((sum, b) => sum + b.totalPoints, 0).toFixed(1)}
            </td>
            <td className="py-2 px-2" />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
