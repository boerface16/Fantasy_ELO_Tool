import { useState, useEffect } from 'react';
import DatePicker from '../components/dashboard/DatePicker';
import HotColdSection from '../components/dashboard/HotColdSection';
import LeagueSummary from '../components/dashboard/LeagueSummary';
import { useHotPlayers, useColdPlayers, useLeagueSummary, useLatestDate, useSeasonMeta } from '../hooks/useElo';

export default function Dashboard() {
  const { data: latestDate } = useLatestDate();
  const { data: seasonMeta } = useSeasonMeta();
  const [selectedDate, setSelectedDate] = useState('');

  useEffect(() => {
    if (latestDate && !selectedDate) {
      setSelectedDate(latestDate);
    }
  }, [latestDate, selectedDate]);

  const { data: hotPlayers, isLoading: hotLoading } = useHotPlayers(selectedDate);
  const { data: coldPlayers, isLoading: coldLoading } = useColdPlayers(selectedDate);
  const { data: leagueSummary, isLoading: summaryLoading } = useLeagueSummary();

  return (
    <div className="space-y-10">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-extrabold tracking-tight">Daily Performance</h2>
          <p className="text-gray-500 mt-1">
            Player ELO fluctuations for the selected date.
            <span className="ml-2 text-xs font-medium px-2 py-0.5 rounded bg-primary/10 text-primary">
              {seasonMeta?.year ?? ''} Season
            </span>
          </p>
        </div>
        {selectedDate && (
          <DatePicker
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
            minDate={seasonMeta?.startDate ?? ''}
            maxDate={seasonMeta?.endDate ?? latestDate ?? ''}
          />
        )}
      </div>

      {/* Hot Players Section */}
      <HotColdSection
        type="hot"
        players={hotPlayers ?? []}
        isLoading={hotLoading}
      />

      {/* Cold Players Section */}
      <HotColdSection
        type="cold"
        players={coldPlayers ?? []}
        isLoading={coldLoading}
      />

      {/* League Summary */}
      <LeagueSummary
        activePlayersCount={leagueSummary?.activePlayersCount ?? 0}
        averageElo={leagueSummary?.averageElo ?? 1500}
        eliteCount={leagueSummary?.eliteCount ?? 0}
        isLoading={summaryLoading}
      />
    </div>
  );
}
