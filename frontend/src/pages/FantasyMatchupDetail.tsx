import { useParams, Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useFantasyMatchup } from '../hooks/useFantasy';
import { useBatterTalentElo, usePitcherTalentElo } from '../hooks/useMatchup';
import FinalPrediction from '../components/matchup/FinalPrediction';
import MatchupBar from '../components/matchup/MatchupBar';

export default function FantasyMatchupDetail() {
  const { batterId, pitcherId } = useParams<{ batterId: string; pitcherId: string }>();
  const bId = batterId ? parseInt(batterId, 10) : null;
  const pId = pitcherId ? parseInt(pitcherId, 10) : null;

  const { data: matchup, isLoading } = useFantasyMatchup(bId, pId);
  const { data: batter } = useBatterTalentElo(bId);
  const { data: pitcher } = usePitcherTalentElo(pId);

  if (!bId || !pId) {
    return <div className="text-center text-text-secondary py-12">Invalid matchup IDs</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/fantasy" className="text-sm text-primary flex items-center gap-1 hover:underline">
          <ArrowLeft className="w-4 h-4" /> Back
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Matchup Detail</h1>
          <p className="text-sm text-text-secondary">
            {batter?.fullName ?? `Batter #${bId}`} vs {pitcher?.fullName ?? `Pitcher #${pId}`}
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="text-center text-text-secondary py-8">Loading matchup...</div>
      )}

      {matchup && (
        <>
          {/* Fantasy Points */}
          <div className="bg-bg-card rounded-lg border border-border-line shadow-modern p-5">
            <div className="text-xs font-semibold text-text-secondary uppercase mb-2">Expected Fantasy Points (4 PA)</div>
            <div className="text-3xl font-bold text-primary tabular-nums">{matchup.expectedPoints.toFixed(1)}</div>
            <div className="text-sm text-text-secondary mt-1">Expected wOBA: {matchup.expectedWoba.toFixed(3)}</div>
          </div>

          {/* Probabilities */}
          <FinalPrediction
            expectedWoba={matchup.expectedWoba}
            probabilities={matchup.probabilities}
          />

          <MatchupBar probabilities={matchup.probabilities} />

          {/* Z-Score Diffs */}
          <div className="bg-bg-card rounded-lg border border-border-line shadow-modern p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">Talent Z-Score Differentials</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {Object.entries(matchup.zDiffs).map(([key, val]) => (
                <div key={key} className="text-center">
                  <div className="text-xs text-text-secondary uppercase mb-1">
                    {key.replace('z_', '').replace(/_/g, ' ')}
                  </div>
                  <div className={`text-lg font-bold tabular-nums ${val > 0 ? 'text-delta-up' : val < 0 ? 'text-delta-down' : 'text-text-secondary'}`}>
                    {val > 0 ? '+' : ''}{val.toFixed(3)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
