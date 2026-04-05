import { useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch } from '../lib/apiClient';
import { Loader2, ArrowRight, Calendar, CalendarDays } from 'lucide-react';
import RosterUpload, { DEFAULT_ROSTER } from '../components/fantasy/RosterUpload';
import WeekSelector from '../components/fantasy/WeekSelector';
import FantasyPointsPanel from '../components/fantasy/FantasyPointsPanel';
import WeeklyGrid from '../components/fantasy/WeeklyGrid';
import PitcherGrid from '../components/fantasy/PitcherGrid';
import type { RosterEntry, WeeklyProjection } from '../types/fantasy';

function getMonday(d: Date): Date {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.getFullYear(), d.getMonth(), diff);
}

function shiftWeek(iso: string, weeks: number): string {
  const d = new Date(iso + 'T12:00:00');
  d.setDate(d.getDate() + weeks * 7);
  return d.toISOString().split('T')[0];
}

function getWeekEnd(start: string): string {
  const d = new Date(start + 'T12:00:00');
  d.setDate(d.getDate() + 6);
  return d.toISOString().split('T')[0];
}

function getTodayISO(): string {
  return new Date().toISOString().split('T')[0];
}

export default function FantasyDashboard() {
  const today = new Date();
  const monday = getMonday(today);
  const [weekStart, setWeekStart] = useState(monday.toISOString().split('T')[0]);
  const [rosterText, setRosterText] = useState(() => localStorage.getItem('rosterText') ?? DEFAULT_ROSTER);
  const [projection, setProjection] = useState<WeeklyProjection | null>(null);
  const [dailyProjection, setDailyProjection] = useState<WeeklyProjection | null>(null);
  const [isProjecting, setIsProjecting] = useState(false);
  const [isProjectingDaily, setIsProjectingDaily] = useState(false);
  const [error, setError] = useState('');

  const handleRosterParsed = (_entries: RosterEntry[], rawText: string) => {
    setRosterText(rawText);
    setProjection(null);
    setDailyProjection(null);
  };

  const handleProject = async () => {
    if (!rosterText) return;
    setIsProjecting(true);
    setError('');
    try {
      const data = await apiFetch<WeeklyProjection>('/api/fantasy/weekly-projection', {
        method: 'POST',
        body: JSON.stringify({ roster_text: rosterText, ref_date: weekStart }),
      });
      setProjection(data);
      sessionStorage.setItem('weeklyProjection', JSON.stringify(data));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Projection failed');
    } finally {
      setIsProjecting(false);
    }
  };

  const handleProjectDaily = async () => {
    if (!rosterText) return;
    setIsProjectingDaily(true);
    setError('');
    try {
      const data = await apiFetch<WeeklyProjection>('/api/fantasy/daily-projection', {
        method: 'POST',
        body: JSON.stringify({ roster_text: rosterText, ref_date: getTodayISO() }),
      });
      setDailyProjection(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Daily projection failed');
    } finally {
      setIsProjectingDaily(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Fantasy Matchup Predictor</h1>
        <p className="text-sm text-gray-400 mt-1">
          Paste your ESPN roster, pick a week, and get ELO-powered projections
        </p>
      </div>

      {/* Roster Upload */}
      <RosterUpload onRosterParsed={handleRosterParsed} />

      {/* Week Selector + Project Buttons */}
      {rosterText && (
        <div className="flex items-center gap-4 flex-wrap">
          <WeekSelector
            weekStart={weekStart}
            weekEnd={getWeekEnd(weekStart)}
            onPrev={() => setWeekStart(shiftWeek(weekStart, -1))}
            onNext={() => setWeekStart(shiftWeek(weekStart, 1))}
          />
          <button
            onClick={handleProject}
            disabled={isProjecting}
            className="px-5 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {isProjecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CalendarDays className="w-4 h-4" />}
            Project Week
          </button>
          <button
            onClick={handleProjectDaily}
            disabled={isProjectingDaily}
            className="px-5 py-2 bg-emerald-600 text-white rounded-lg text-sm font-semibold hover:bg-emerald-600/90 disabled:opacity-50 transition-colors flex items-center gap-2"
          >
            {isProjectingDaily ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calendar className="w-4 h-4" />}
            Project Today
          </button>
        </div>
      )}

      {error && <div className="text-red-500 text-sm">{error}</div>}

      {/* Daily Projection */}
      {dailyProjection && (
        <div className="space-y-4">
          <FantasyPointsPanel
            totalPoints={dailyProjection.totalPoints}
            batterPoints={dailyProjection.totalBatterPoints}
            pitcherPoints={dailyProjection.totalPitcherPoints}
            optimalTotalPoints={dailyProjection.optimalTotalPoints}
            optimalBatterPoints={dailyProjection.optimalBatterPoints}
            optimalPitcherPoints={dailyProjection.optimalPitcherPoints}
            weekLabel={`Today — ${dailyProjection.weekStart}`}
          />
          <div className="bg-bg-card rounded-xl border border-border-line shadow-sm p-5">
            <h2 className="text-lg font-bold mb-4">Today's Batter Matchups</h2>
            <WeeklyGrid batters={dailyProjection.batters} weekStart={dailyProjection.weekStart} />
          </div>
          <div className="bg-bg-card rounded-xl border border-border-line shadow-sm p-5">
            <h2 className="text-lg font-bold mb-4">Today's Pitcher Matchups</h2>
            <PitcherGrid pitchers={dailyProjection.pitchers} />
          </div>
        </div>
      )}

      {/* Weekly Projection Results */}
      {projection && (
        <>
          <FantasyPointsPanel
            totalPoints={projection.totalPoints}
            batterPoints={projection.totalBatterPoints}
            pitcherPoints={projection.totalPitcherPoints}
            optimalTotalPoints={projection.optimalTotalPoints}
            optimalBatterPoints={projection.optimalBatterPoints}
            optimalPitcherPoints={projection.optimalPitcherPoints}
            weekLabel={`${projection.weekStart} → ${projection.weekEnd}`}
          />

          {/* Batter Grid */}
          <div className="bg-bg-card rounded-xl border border-border-line shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">Batter Matchups</h2>
              <Link to="/fantasy/batters" className="text-sm text-primary flex items-center gap-1 hover:underline">
                Full View <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
            <WeeklyGrid batters={projection.batters} weekStart={projection.weekStart} />
          </div>

          {/* Pitcher Grid */}
          <div className="bg-bg-card rounded-xl border border-border-line shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold">Pitcher Starts</h2>
              <Link to="/fantasy/pitchers" className="text-sm text-primary flex items-center gap-1 hover:underline">
                Full View <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
            <PitcherGrid pitchers={projection.pitchers} />
          </div>
        </>
      )}

    </div>
  );
}
