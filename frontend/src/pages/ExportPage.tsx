import { useState } from 'react';
import { FileDown, Loader2 } from 'lucide-react';
import { BASE_URL } from '../lib/apiClient';

export default function ExportPage() {
  const [rosterText, setRosterText] = useState(() => {
    const saved = sessionStorage.getItem('weeklyProjection');
    if (saved) {
      // If we have a projection, pre-fill the roster text from session
      return sessionStorage.getItem('rosterText') ?? '';
    }
    return '';
  });
  const [refDate, setRefDate] = useState(() => {
    const d = new Date();
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(d.getFullYear(), d.getMonth(), diff);
    return monday.toISOString().split('T')[0];
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');

  const handleExport = async () => {
    if (!rosterText.trim()) return;
    setIsGenerating(true);
    setError('');

    try {
      const res = await fetch(`${BASE_URL}/api/fantasy/export/pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roster_text: rosterText, ref_date: refDate }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `API error: ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `fantasy-report-${refDate}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Export failed');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Export PDF Report</h1>
        <p className="text-sm text-gray-400 mt-1">
          Generate a downloadable PDF with your weekly fantasy projections
        </p>
      </div>

      {/* Roster Input */}
      <div className="bg-bg-card rounded-xl border border-border-line shadow-sm p-5">
        <label className="block text-sm font-semibold text-gray-300 mb-2">
          Paste ESPN Roster
        </label>
        <textarea
          value={rosterText}
          onChange={(e) => setRosterText(e.target.value)}
          placeholder="Paste your ESPN roster here (e.g., C\tSalvador Perez, KC C)..."
          className="w-full h-40 border border-border-line rounded-lg p-3 text-sm font-mono resize-y focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
        />
      </div>

      {/* Week + Export Button */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <label className="text-sm font-semibold text-gray-300">Week of:</label>
          <input
            type="date"
            value={refDate}
            onChange={(e) => setRefDate(e.target.value)}
            className="border border-border-line rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
        <button
          onClick={handleExport}
          disabled={isGenerating || !rosterText.trim()}
          className="px-5 py-2 bg-primary text-white rounded-lg text-sm font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
        >
          {isGenerating ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <FileDown className="w-4 h-4" />
          )}
          Generate PDF
        </button>
      </div>

      {error && <div className="text-red-500 text-sm">{error}</div>}

      {/* Instructions */}
      <div className="bg-white/5 rounded-xl border border-border-line p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-2">How it works</h3>
        <ol className="text-sm text-gray-400 space-y-1 list-decimal list-inside">
          <li>Paste your ESPN roster (copy from My Team page)</li>
          <li>Select the week start date</li>
          <li>Click "Generate PDF" to download your report</li>
          <li>Report includes batter/pitcher projections and team ELO rankings</li>
        </ol>
      </div>
    </div>
  );
}
