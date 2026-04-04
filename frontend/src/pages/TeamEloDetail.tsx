import { useParams, Link } from 'react-router-dom';
import { useEffect, useRef } from 'react';
import { ArrowLeft } from 'lucide-react';
import { createChart, LineSeries } from 'lightweight-charts';
import type { IChartApi, LineData, Time } from 'lightweight-charts';
import { useTeamElo, useTeamEloHistory } from '../hooks/useFantasy';
import { TEAM_COLORS, getChartColor } from '../utils/teamColors';

export default function TeamEloDetail() {
  const { teamCode = '' } = useParams<{ teamCode: string }>();
  const { data: detail, isLoading: detailLoading } = useTeamElo(teamCode);
  const { data: history = [], isLoading: historyLoading } = useTeamEloHistory(teamCode);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const color = getChartColor(teamCode);

  useEffect(() => {
    if (!chartContainerRef.current || history.length === 0) return;

    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const rafId = requestAnimationFrame(() => {
      if (!chartContainerRef.current) return;

      const chart = createChart(chartContainerRef.current, {
        width: chartContainerRef.current.clientWidth || 600,
        height: 400,
        layout: {
          background: { color: '#1E293B' },
          textColor: '#9CA3AF',
        },
        grid: {
          vertLines: { color: '#334155' },
          horzLines: { color: '#334155' },
        },
        timeScale: { borderColor: '#334155' },
        rightPriceScale: { borderColor: '#334155' },
      });

      chartRef.current = chart;

      const lineSeries = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      });

      // Deduplicate by date — keep last game of the day (doubleheaders produce 2 records)
      const byDate = new Map<string, number>();
      for (const h of history) byDate.set(h.date, h.eloAfter);
      const lineData: LineData<Time>[] = Array.from(byDate.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([date, value]) => ({ time: date as Time, value }));

      lineSeries.setData(lineData);
      chart.timeScale().fitContent();
    });

    return () => {
      cancelAnimationFrame(rafId);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [history, color]);

  useEffect(() => {
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const isLoading = detailLoading || historyLoading;

  return (
    <div className="space-y-6">
      {/* Back link + header */}
      <div className="flex items-center gap-4">
        <Link to="/team-elo" className="p-2 rounded-lg hover:bg-white/10 text-gray-400">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-3">
          <span
            className="w-4 h-4 rounded-full"
            style={{ backgroundColor: color }}
          />
          <h2 className="text-3xl font-bold tracking-tight">{teamCode}</h2>
          {detail && (
            <span className="text-xl text-gray-400 font-mono ml-2">
              {Math.round(detail.currentElo)}
            </span>
          )}
        </div>
      </div>

      {/* Chart */}
      <div className="bg-bg-card rounded-xl border border-border-line p-4">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          ELO Over Time
        </h3>
        {isLoading ? (
          <div className="h-[400px] flex items-center justify-center text-gray-400">Loading...</div>
        ) : history.length === 0 ? (
          <div className="h-[400px] flex items-center justify-center text-gray-400">No history available</div>
        ) : (
          <div ref={chartContainerRef} />
        )}
      </div>

      {/* Game Log */}
      <div className="bg-bg-card rounded-xl border border-border-line overflow-hidden">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider px-4 py-3 border-b border-border-line">
          Game Log
        </h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-line text-gray-400 text-xs uppercase tracking-wider">
              <th className="text-left px-4 py-2">Date</th>
              <th className="text-left px-4 py-2">Opponent</th>
              <th className="text-center px-4 py-2">Result</th>
              <th className="text-right px-4 py-2">Run Diff</th>
              <th className="text-right px-4 py-2">ELO</th>
              <th className="text-right px-4 py-2">Change</th>
            </tr>
          </thead>
          <tbody>
            {[...history].reverse().slice(0, 30).map((game, idx) => {
              const change = game.eloAfter - game.eloBefore;
              return (
                <tr key={idx} className="border-b border-border-line last:border-0 hover:bg-white/5">
                  <td className="px-4 py-2 text-gray-300">{game.date}</td>
                  <td className="px-4 py-2 text-gray-300">{game.opponent}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={game.result === 'W' ? 'text-green-400' : 'text-red-400'}>
                      {game.result}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    <span className={game.runDiff > 0 ? 'text-green-400' : game.runDiff < 0 ? 'text-red-400' : 'text-gray-400'}>
                      {game.runDiff > 0 ? '+' : ''}{game.runDiff}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-gray-100">
                    {Math.round(game.eloAfter)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    <span className={change > 0 ? 'text-green-400' : change < 0 ? 'text-red-400' : 'text-gray-400'}>
                      {change > 0 ? '+' : ''}{change.toFixed(1)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
