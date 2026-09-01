import { useState, useEffect } from 'react';
import MapComponent from './components/MapComponent';
import LocalContextWidget from './components/LocalContextWidget';
import HotlinesList from './components/HotlinesList';
import AdminPanel from './components/AdminPanel';
import { EvacuationCenter } from './types';

export default function App() {
  const [centers, setCenters] = useState<EvacuationCenter[]>([]);
  const [activeCenterId, setActiveCenterId] = useState<number | null>(null);
  const [isAdminMode, setIsAdminMode] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    fetchCenters();
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  const fetchCenters = async () => {
    try {
      const res = await fetch('/api/centers');
      const data = await res.json();
      setCenters(data);
    } catch (err) {
      console.error("Failed to fetch public centers", err);
    }
  };

  return (
    <div className="h-screen w-full bg-[#f8fafc] flex flex-col font-sans overflow-hidden text-slate-900">
      {/* Header */}
      <nav className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-8 shrink-0 relative z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded flex items-center justify-center">
            <div className="w-4 h-4 border-2 border-white rounded-sm"></div>
          </div>
          <span className="font-bold text-xl tracking-tight text-slate-800">
            LIGTAS<span className="text-blue-600">MAP</span>
          </span>
        </div>
        
        <div className="flex items-center gap-6">
          <div className="hidden sm:flex flex-col items-end">
            <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Current Status</span>
            <span className="text-sm font-semibold text-emerald-600 flex items-center gap-1.5">
              <span className="w-2 h-2 bg-emerald-500 rounded-full"></span> Systems Active / Level 1
            </span>
          </div>
          <div className="hidden sm:block h-8 w-[1px] bg-slate-200"></div>
          <div className="text-right">
            <div className="text-sm font-bold">
              {currentTime.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
            </div>
            <div className="text-xs text-slate-500">
              {currentTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })}
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col md:flex-row overflow-hidden relative z-10">
        
        {/* Left Sidebar: Widgets & Admin */}
        <aside className="w-full md:w-96 bg-white border-r border-slate-200 flex flex-col shrink-0 overflow-y-auto md:overflow-hidden z-10 shadow-lg">
          <div className="p-6 space-y-6 flex-1 md:overflow-y-auto">
            <LocalContextWidget />
            <div className="border-t border-slate-100 my-2"></div>
            <HotlinesList />
          </div>
          
          <div className="mt-auto p-6 border-t border-slate-100 shrink-0">
            <div className="bg-blue-50 p-4 rounded-xl text-sm">
              <div className="font-bold text-blue-800 mb-1">Admin Panel Access</div>
              <p className="text-blue-600 mb-3 text-xs leading-relaxed">
                Log in to update evacuation center capacities and supply levels.
              </p>
              <button 
                onClick={() => setIsAdminMode(!isAdminMode)}
                className="w-full py-2 bg-blue-600 text-white rounded-lg font-bold text-xs shadow-lg shadow-blue-200 hover:bg-blue-700 transition-colors uppercase"
              >
                {isAdminMode ? 'Return to Map' : 'Admin Login'}
              </button>
            </div>
          </div>
        </aside>

        {/* Right Section: Map / Admin */}
        <section className="flex-1 relative bg-slate-200 flex flex-col">
          {isAdminMode ? (
            <div className="absolute inset-0 bg-[#f8fafc] overflow-y-auto p-4 sm:p-8">
              <div className="max-w-2xl mx-auto h-full min-h-[500px]">
                <AdminPanel onCentersChange={fetchCenters} />
              </div>
            </div>
          ) : (
            <div className="absolute inset-0">
              <MapComponent centers={centers} activeCenterId={activeCenterId} />
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

