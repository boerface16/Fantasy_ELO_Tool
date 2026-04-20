import { useParams, Link } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft } from 'lucide-react';
import { createChart, LineSeries } from 'lightweight-charts';
import type { IChartApi, LineData, Time } from 'lightweight-charts';
import { useQueries } from '@tanstack/react-query';
import { useTeamElo, useTeamEloHistory } from '../hooks/useFantasy';
import * as fantasyApi from '../api/fantasy';
import { getChartColor } from '../utils/teamColors';
import TeamCompareChart from '../components/team/TeamCompareChart';
import TeamCompareSearch from '../components/team/TeamCompareSearch';
import type { TeamCompareSeries } from '../components/team/TeamCompareChart';

const TEAM_COLORS = ['#ffb000', '#648fff', '#fe6100', '#dc267f', '#785ef0'];

export default function TeamEloDetail() {
  const { teamCode = '' } = useParams<{ teamCode: string }>();
  const { data: detail, isLoading: detailLoading } = useTeamElo(teamCode);
  const { data: history = [], isLoading: historyLoading } = useTeamEloHistory(teamCode);

  const [compareMode, setCompareMode] = useState(false);
  const [comparedTeams, setComparedTeams] = useState<string[]>([]);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const color = getChartColor(teamCode);

  // Reset compare state when team changes
  useEffect(() => {
    setCompareMode(false);
    setComparedTeams([]);
  }, [teamCode]);

  const comparedQueries = useQueries({
    queries: comparedTeams.map(tc => ({
      queryKey: ['teamEloHistory', tc],
      queryFn: () => fantasyApi.getTeamEloHistory(tc),
      enabled: compareMode,
      staleTime: 5 * 60 * 1000,
    })),
  });

  const compareSeries: TeamCompareSeries[] = compareMode
    ? [
        { teamCode, color: TEAM_COLORS[0], data: history },
        ...comparedTeams.map((tc, i) => ({
          teamCode: tc,
          color: TEAM_COLORS[i + 1] ?? '#888',
          data: comparedQueries[i]?.data ?? [],
        })),
      ]
    : [];

  useEffect(() => {
    if (compareMode) return;
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
          background: { color: '#16161e' },
          textColor: '#8a8d98',
        },
        grid: {
          vertLines: { color: '#242430' },
          horzLines: { color: '#242430' },
        },
        timeScale: { borderColor: '#242430' },
        rightPriceScale: { borderColor: '#242430' },
      });

      chartRef.current = chart;

      const lineSeries = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
      });

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
  }, [history, color, compareMode]);

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
        <Link to="/team-elo" className="p-2 rounded-lg hover:bg-bg-elevated text-text-secondary">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div className="flex items-center gap-3">
          <span
            className="w-4 h-4 rounded-full"
            style={{ backgroundColor: color }}
          />
          <h2 className="text-3xl font-bold tracking-tight">{teamCode}</h2>
          {detail && (
            <span className="text-xl text-text-secondary font-mono ml-2">
              {Math.round(detail.currentElo)}
            </span>
          )}
        </div>
      </div>

      {/* Chart */}
      <div className="bg-bg-card rounded-lg border border-border-line p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider">
            ELO Over Time
          </h3>
          <button
            onClick={() => setCompareMode(m => !m)}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-colors ${
              compareMode
                ? 'bg-accent text-white'
                : 'bg-bg-elevated text-text-secondary hover:text-text-primary'
            }`}
          >
            Compare
          </button>
        </div>

        {compareMode && (
          <div className="mb-4">
            <TeamCompareSearch
              primaryTeam={teamCode}
              compared={comparedTeams}
              colors={TEAM_COLORS}
              onAdd={tc => setComparedTeams(prev => [...prev, tc])}
              onRemove={tc => setComparedTeams(prev => prev.filter(t => t !== tc))}
            />
          </div>
        )}

        {isLoading ? (
          <div className="h-[400px] flex items-center justify-center text-text-secondary">Loading...</div>
        ) : history.length === 0 ? (
          <div className="h-[400px] flex items-center justify-center text-text-secondary">No history available</div>
        ) : compareMode ? (
          <TeamCompareChart series={compareSeries} />
        ) : (
          <div ref={chartContainerRef} />
        )}
      </div>

      {/* Game Log */}
      <div className="bg-bg-card rounded-lg border border-border-line overflow-hidden">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-wider px-4 py-3 border-b border-border-line">
          Game Log
        </h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-line text-text-secondary text-xs uppercase tracking-wider">
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
                <tr key={idx} className="border-b border-border-line last:border-0 hover:bg-bg-elevated/60">
                  <td className="px-4 py-2 text-text-primary">{game.date}</td>
                  <td className="px-4 py-2 text-text-primary">{game.opponent}</td>
                  <td className="px-4 py-2 text-center">
                    <span className={game.result === 'W' ? 'text-green-400' : 'text-red-400'}>
                      {game.result}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    <span className={game.runDiff > 0 ? 'text-green-400' : game.runDiff < 0 ? 'text-red-400' : 'text-text-secondary'}>
                      {game.runDiff > 0 ? '+' : ''}{game.runDiff}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-text-primary">
                    {Math.round(game.eloAfter)}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    <span className={change > 0 ? 'text-green-400' : change < 0 ? 'text-red-400' : 'text-text-secondary'}>
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
