import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import PitcherGrid from '../components/fantasy/PitcherGrid';
import FantasyPointsPanel from '../components/fantasy/FantasyPointsPanel';
import type { WeeklyProjection } from '../types/fantasy';

export default function PitcherMatchups() {
  const [projection, setProjection] = useState<WeeklyProjection | null>(null);

  useEffect(() => {
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
        <div className="text-center text-gray-400 py-12">
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
          <h1 className="text-2xl font-bold">Pitcher Matchups</h1>
          <p className="text-sm text-gray-400">
            {projection.weekStart} — {projection.weekEnd}
          </p>
        </div>
      </div>

      <FantasyPointsPanel
        totalPoints={projection.totalPitcherPoints}
        batterPoints={0}
        pitcherPoints={projection.totalPitcherPoints}
        weekLabel="Pitcher Points"
      />

      <div className="bg-bg-card rounded-xl border border-border-line shadow-sm p-5">
        <PitcherGrid pitchers={projection.pitchers} />
      </div>
    </div>
  );
}
