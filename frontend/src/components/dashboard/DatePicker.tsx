import { useRef } from 'react';
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';

interface DatePickerProps {
  selectedDate: string;
  onDateChange: (date: string) => void;
  minDate?: string;
  maxDate?: string;
}

export default function DatePicker({ selectedDate, onDateChange, minDate, maxDate }: DatePickerProps) {
  const dateInputRef = useRef<HTMLInputElement>(null);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr + 'T12:00:00');
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const goToPrevDay = () => {
    const current = new Date(selectedDate + 'T12:00:00');
    current.setDate(current.getDate() - 1);
    const newDate = current.toISOString().split('T')[0];
    if (!minDate || newDate >= minDate) {
      onDateChange(newDate);
    }
  };

  const goToNextDay = () => {
    const current = new Date(selectedDate + 'T12:00:00');
    current.setDate(current.getDate() + 1);
    const newDate = current.toISOString().split('T')[0];
    if (!maxDate || newDate <= maxDate) {
      onDateChange(newDate);
    }
  };

  const handleCalendarClick = () => {
    dateInputRef.current?.showPicker();
  };

  const handleDateInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newDate = e.target.value;
    if (newDate) {
      onDateChange(newDate);
    }
  };

  return (
    <div className="flex items-center gap-2 bg-white p-2 rounded-xl shadow-modern border border-gray-100">
      <button
        onClick={goToPrevDay}
        className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
        title="Previous day"
      >
        <ChevronLeft className="w-5 h-5 text-gray-600" />
      </button>

      <span className="px-4 font-bold text-sm min-w-[160px] text-center">
        {formatDate(selectedDate)}
      </span>

      <button
        onClick={goToNextDay}
        className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
        title="Next day"
      >
        <ChevronRight className="w-5 h-5 text-gray-600" />
      </button>

      <button
        onClick={handleCalendarClick}
        className="ml-2 bg-primary/10 text-primary p-1.5 rounded-lg hover:bg-primary/20 transition-colors"
        title="Open calendar"
      >
        <Calendar className="w-[18px] h-[18px]" />
      </button>

      <input
        ref={dateInputRef}
        type="date"
        value={selectedDate}
        onChange={handleDateInputChange}
        min={minDate}
        max={maxDate}
        className="sr-only"
      />
    </div>
  );
}
