import { useState } from 'react';
import { Upload, Check, AlertCircle, Loader2 } from 'lucide-react';
import type { RosterEntry } from '../../types/fantasy';

interface Props {
  onRosterParsed: (entries: RosterEntry[], rawText: string) => void;
  isLoading?: boolean;
}

const PLACEHOLDER = `Paste your ESPN roster here, e.g.:

C\tSalvador Perez, KC C
1B\tVladimir Guerrero Jr., TOR 1B
SS\tTrea Turner, PHI SS
OF\tAaron Judge, NYY OF
SP\tZack Wheeler, PHI SP`;

export default function RosterUpload({ onRosterParsed, isLoading }: Props) {
  const [text, setText] = useState('');
  const [entries, setEntries] = useState<RosterEntry[] | null>(null);
  const [error, setError] = useState('');

  const handleParse = async () => {
    if (!text.trim()) return;
    setError('');
    try {
      const res = await fetch('/api/fantasy/roster', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roster_text: text }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      setEntries(data.entries);
      onRosterParsed(data.entries, text);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to parse roster');
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-100 shadow-sm">
      <div className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <Upload className="w-4 h-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-700">Paste Your Roster</h3>
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={PLACEHOLDER}
          rows={8}
          className="w-full rounded-lg border border-gray-200 p-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-y"
        />

        <div className="flex items-center gap-3 mt-3">
          <button
            onClick={handleParse}
            disabled={!text.trim() || isLoading}
            className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            Parse Roster
          </button>
          {entries && (
            <span className="text-sm text-green-600 flex items-center gap-1">
              <Check className="w-4 h-4" />
              {entries.length} players found
            </span>
          )}
          {error && (
            <span className="text-sm text-red-500 flex items-center gap-1">
              <AlertCircle className="w-4 h-4" />
              {error}
            </span>
          )}
        </div>
      </div>

      {entries && entries.length > 0 && (
        <div className="border-t border-gray-100 px-5 py-3 max-h-64 overflow-y-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-gray-400 uppercase">
                <th className="text-left py-1 w-16">Slot</th>
                <th className="text-left py-1">Name</th>
                <th className="text-left py-1 w-16">Team</th>
                <th className="text-left py-1 w-16">Pos</th>
                <th className="text-left py-1 w-20">Status</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i} className="border-t border-gray-50">
                  <td className="py-1.5 font-mono text-gray-500">{e.slot || '—'}</td>
                  <td className="py-1.5 font-medium">{e.matchedName || e.name}</td>
                  <td className="py-1.5 text-gray-600">{e.dbTeam || e.team}</td>
                  <td className="py-1.5 text-gray-600">{e.position || '—'}</td>
                  <td className="py-1.5">
                    {e.playerId ? (
                      <span className="text-green-600 text-xs">Matched</span>
                    ) : (
                      <span className="text-amber-500 text-xs">Not found</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
