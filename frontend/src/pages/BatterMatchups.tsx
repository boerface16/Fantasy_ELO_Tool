import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import WeeklyGrid from '../components/fantasy/WeeklyGrid';
import FantasyPointsPanel from '../components/fantasy/FantasyPointsPanel';
import type { WeeklyProjection } from '../types/fantasy';

export default function BatterMatchups() {
  const [projection, setProjection] = useState<WeeklyProjection | null>(null);

  useEffect(() => {
    // Load from sessionStorage if available (set by FantasyDashboard)
    const stored = sessionStorage.getItem('weeklyProjection');
    if (stored) {
      setProjection(JSON.parse(stored));
    }
  }, []);

  if (!projection) {
    return (
      <div className="space-y-4">
        <Link to="/fantasy" className="text-sm text-primary flex items-center gap-1 hover:underline">
          <ArrowLeft className="w-4 h-4" /> Back to Fantasy Dashboard
        </Link>
        <div className="text-center text-text-secondary py-12">
          No projection loaded. Go to the Fantasy Dashboard to generate one.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/fantasy" className="text-sm text-primary flex items-center gap-1 hover:underline">
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Batter Matchups</h1>
          <p className="text-sm text-text-secondary">
            {projection.weekStart} — {projection.weekEnd}
          </p>
        </div>
      </div>

      <FantasyPointsPanel
        totalPoints={projection.totalBatterPoints}
        batterPoints={projection.totalBatterPoints}
        pitcherPoints={0}
        weekLabel="Batter Points"
      />

      <div className="bg-bg-card rounded-lg border border-border-line shadow-modern p-5">
        <WeeklyGrid batters={projection.batters} weekStart={projection.weekStart} />
      </div>
    </div>
  );
}
