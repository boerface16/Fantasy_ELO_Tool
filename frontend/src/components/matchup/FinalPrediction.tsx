import type { PAProbabilities } from '../../types/matchup';
import { LEAGUE_AVG_WOBA } from '../../lib/matchupPredictor';

interface FinalPredictionProps {
  expectedWoba: number;
  probabilities: PAProbabilities;
}

export default function FinalPrediction({ expectedWoba, probabilities }: FinalPredictionProps) {
  const wobaDiff = expectedWoba - LEAGUE_AVG_WOBA;
  const obp = probabilities.BB + probabilities['1B'] + probabilities['2B'] + probabilities['3B'] + probabilities.HR;
  const xslg =
    probabilities['1B'] * 1 +
    probabilities['2B'] * 2 +
    probabilities['3B'] * 3 +
    probabilities.HR * 4 +
    probabilities.BB * 0;

  return (
    <div className="grid grid-cols-3 gap-4">
      {/* wOBA */}
      <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 text-center">
        <div className="text-xs font-semibold text-gray-400 mb-1">Expected wOBA</div>
        <div className="text-3xl font-bold tabular-nums">{expectedWoba.toFixed(3)}</div>
        <div className={`text-sm font-medium mt-1 ${wobaDiff >= 0 ? 'text-green-600' : 'text-red-500'}`}>
          {wobaDiff >= 0 ? '+' : ''}{(wobaDiff * 1000).toFixed(0)} vs avg
        </div>
      </div>

      {/* OBP */}
      <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 text-center">
        <div className="text-xs font-semibold text-gray-400 mb-1">On-Base %</div>
        <div className="text-3xl font-bold tabular-nums">{(obp * 100).toFixed(1)}%</div>
        <div className="text-sm text-gray-400 mt-1">BB + H</div>
      </div>

      {/* xSLG */}
      <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100 text-center">
        <div className="text-xs font-semibold text-gray-400 mb-1">xSLG</div>
        <div className="text-3xl font-bold tabular-nums">{xslg.toFixed(3)}</div>
        <div className="text-sm text-gray-400 mt-1">Expected bases / PA</div>
      </div>
    </div>
  );
}
