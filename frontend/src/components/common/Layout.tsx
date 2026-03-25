import type { ReactNode } from 'react';
import Header from './Header';
import AdBanner from './AdBanner';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-bg-page">
      <Header />
      <main className="flex-1 px-4 py-8 md:px-10">
        <div className="max-w-[1200px] mx-auto">
          {children}
          <AdBanner slot="YOUR_AD_SLOT_ID" format="horizontal" className="mt-8" />
        </div>
      </main>
    </div>
  );
}
