import { useState, useEffect } from 'react';
import { PhoneCall, Search } from 'lucide-react';
import { Hotline } from '../types';

export default function HotlinesList() {
  const [hotlines, setHotlines] = useState<Hotline[]>([]);
  const [cityFilter, setCityFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHotlines();
  }, [cityFilter]);

  const fetchHotlines = async () => {
    setLoading(true);
    try {
      const url = cityFilter ? `/api/hotlines?city=${encodeURIComponent(cityFilter)}` : '/api/hotlines';
      const res = await fetch(url);
      const data = await res.json();
      setHotlines(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Emergency Contacts</h2>
      </div>
      
      <div className="relative mb-4">
        <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <select 
          className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 appearance-none"
          value={cityFilter}
          onChange={(e) => setCityFilter(e.target.value)}
        >
          <option value="">All Cities & National</option>
          <option value="Marikina">Marikina</option>
          <option value="Quezon City">Quezon City</option>
          <option value="Pasig">Pasig</option>
        </select>
      </div>

      <div className="space-y-2">
        {loading ? (
          <>
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-slate-50 rounded-lg border border-slate-100 animate-pulse" />
            ))}
          </>
        ) : hotlines.length === 0 ? (
          <p className="text-center text-slate-500 text-sm py-8 font-medium">No hotlines found.</p>
        ) : (
          <>
            {hotlines.map((hotline) => (
              <div key={hotline.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100 transition-colors hover:border-blue-100 hover:bg-blue-50/50">
                <div>
                  <div className="text-xs font-bold text-slate-500">{hotline.agency} - {hotline.city}</div>
                  <div className="text-sm font-bold text-slate-800">{hotline.number}</div>
                </div>
                <a href={`tel:${hotline.number}`} className="p-2 text-blue-600 hover:bg-blue-100 rounded-full shrink-0 transition-colors">
                  <PhoneCall className="w-4 h-4" />
                </a>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
