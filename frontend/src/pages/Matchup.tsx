import { useState } from 'react';
import { Eye, Zap, Hand, Sparkles, Shield, Crosshair } from 'lucide-react';
import PlayerSelector from '../components/matchup/PlayerSelector';
import FinalPrediction from '../components/matchup/FinalPrediction';
import MatchupBar from '../components/matchup/MatchupBar';
import StageResults from '../components/matchup/StageResults';
import { useMatchupPrediction } from '../hooks/useMatchup';
import type { BatterTalentElo, PitcherTalentElo } from '../types/matchup';

function TalentPill({ label, elo, icon: Icon }: { label: string; elo: number; icon: React.ComponentType<{ className?: string }> }) {
  return (
    <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-gray-100 text-sm">
      <Icon className="w-3.5 h-3.5 text-gray-500" />
      <span className="text-gray-600">{label}</span>
      <span className="font-semibold tabular-nums">{Math.round(elo)}</span>
    </div>
  );
}

function BatterPills({ batter }: { batter: BatterTalentElo }) {
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      <TalentPill label="Contact" elo={batter.contact} icon={Hand} />
      <TalentPill label="Power" elo={batter.power} icon={Zap} />
      <TalentPill label="Discipline" elo={batter.discipline} icon={Eye} />
    </div>
  );
}

function PitcherPills({ pitcher }: { pitcher: PitcherTalentElo }) {
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      <TalentPill label="Stuff" elo={pitcher.stuff} icon={Sparkles} />
      <TalentPill label="BIP Supp." elo={pitcher.bipSuppression} icon={Shield} />
      <TalentPill label="Command" elo={pitcher.command} icon={Crosshair} />
    </div>
  );
}

export default function Matchup() {
  const [batterId, setBatterId] = useState<number | null>(null);
  const [batterName, setBatterName] = useState('');
  const [pitcherId, setPitcherId] = useState<number | null>(null);
  const [pitcherName, setPitcherName] = useState('');

  const { batter, pitcher, prediction, isLoading, error } = useMatchupPrediction(batterId, pitcherId);

  const handleBatterSelect = (id: number, name: string) => {
    setBatterId(id || null);
    setBatterName(name);
  };

  const handlePitcherSelect = (id: number, name: string) => {
    setPitcherId(id || null);
    setPitcherName(name);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Matchup Predictor</h1>
        <p className="text-sm text-gray-500 mt-1">
          3-stage plate appearance prediction using talent ELO z-scores
        </p>
      </div>

      {/* Player selectors */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Batter */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="text-xs font-semibold text-gray-400 mb-2">BATTER</div>
          <PlayerSelector
            role="batter"
            selectedName={batterName}
            onSelect={handleBatterSelect}
          />
          {batter && <BatterPills batter={batter} />}
        </div>

        {/* Pitcher */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
          <div className="text-xs font-semibold text-gray-400 mb-2">PITCHER</div>
          <PlayerSelector
            role="pitcher"
            selectedName={pitcherName}
            onSelect={handlePitcherSelect}
          />
          {pitcher && <PitcherPills pitcher={pitcher} />}
        </div>
      </div>

      {/* Loading / Error */}
      {isLoading && batterId && pitcherId && (
        <div className="text-center text-gray-400 py-8">Loading prediction...</div>
      )}
      {error && (
        <div className="text-center text-red-500 py-4">
          Error loading talent data. Please try again.
        </div>
      )}

      {/* Results */}
      {prediction && (
        <div className="space-y-6">
          <FinalPrediction
            expectedWoba={prediction.expectedWoba}
            probabilities={prediction.probabilities}
          />
          <MatchupBar probabilities={prediction.probabilities} />
          <StageResults stages={prediction.stages} zDiffs={prediction.zDiffs} />
        </div>
      )}

      {/* Empty state */}
      {!batterId && !pitcherId && (
        <div className="text-center text-gray-400 py-12">
          Select a batter and pitcher to see matchup prediction
        </div>
      )}
    </div>
  );
}
