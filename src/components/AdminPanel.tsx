import React, { useState, useEffect } from 'react';
import { ShieldAlert, Users, Package, LogOut } from 'lucide-react';
import { EvacuationCenter } from '../types';

interface AdminPanelProps {
  onCentersChange: () => void;
}

export default function AdminPanel({ onCentersChange }: AdminPanelProps) {
  const [token, setToken] = useState<string | null>(localStorage.getItem('adminToken'));
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  
  const [centers, setCenters] = useState<EvacuationCenter[]>([]);
  const [selectedCenter, setSelectedCenter] = useState<EvacuationCenter | null>(null);
  const [loading, setLoading] = useState(false);

  // Form states
  const [occupancy, setOccupancy] = useState(0);
  const [foodStatus, setFoodStatus] = useState('Adequate');
  const [waterStatus, setWaterStatus] = useState('Adequate');

  useEffect(() => {
    if (token) {
      fetchCenters();
    }
  }, [token]);

  const fetchCenters = async () => {
    try {
      const res = await fetch('/api/centers');
      const data = await res.json();
      setCenters(data);
    } catch (err) {
      console.error("Failed to fetch centers for admin", err);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      
      if (!res.ok) {
        setError(data.error || 'Login failed');
        return;
      }
      
      localStorage.setItem('adminToken', data.token);
      setToken(data.token);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    setToken(null);
  };

  const handleCenterSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const center = centers.find(c => c.id === parseInt(e.target.value)) || null;
    setSelectedCenter(center);
    if (center) {
      setOccupancy(center.currentOccupancy);
      setFoodStatus(center.foodStatus);
      setWaterStatus(center.waterStatus);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCenter) return;
    
    setLoading(true);
    try {
      const res = await fetch(`/api/centers/${selectedCenter.id}`, {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          currentOccupancy: occupancy,
          foodStatus,
          waterStatus,
          medicalStatus: selectedCenter.medicalStatus
        })
      });
      
      if (res.status === 401 || res.status === 403) {
        handleLogout();
        return;
      }
      
      if (res.ok) {
        alert('Update successful!');
        fetchCenters();
        onCentersChange(); // Notify parent to refresh public view
      } else {
        const data = await res.json();
        alert(data.error || 'Failed to update');
      }
    } catch (err: any) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="bg-white p-8 md:p-12 rounded-2xl shadow-xl border border-slate-200 h-full flex flex-col justify-center max-w-md mx-auto mt-10 md:mt-20">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-blue-100 shadow-inner">
            <ShieldAlert className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Admin Access</h2>
          <p className="text-slate-500 text-sm mt-1">LGU & DRRMO Personnel Only</p>
        </div>
        
        <form onSubmit={handleLogin} className="space-y-5 w-full">
          {error && <div className="text-red-500 text-sm text-center bg-red-50 border border-red-100 font-medium p-3 rounded-lg">{error}</div>}
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5">Username</label>
            <input 
              type="text" 
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-medium focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none transition-colors"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </div>
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-1.5">Password</label>
            <input 
              type="password" 
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg text-slate-800 font-medium focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none transition-colors"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button 
            type="submit" 
            className="w-full bg-blue-600 text-white py-3 mt-4 rounded-lg font-bold text-sm tracking-wide hover:bg-blue-700 shadow-lg shadow-blue-200 transition-colors uppercase"
          >
            Authenticate
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="bg-white p-6 md:p-8 rounded-2xl shadow-xl border border-slate-200 h-full flex flex-col max-w-2xl mx-auto">
      <div className="flex justify-between items-center mb-8 border-b border-slate-100 pb-5">
        <div>
          <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2 tracking-tight">
            <ShieldAlert className="w-6 h-6 text-blue-600" />
            Dashboard
          </h2>
          <p className="text-slate-500 text-sm mt-1">Update Evacuation Center Status</p>
        </div>
        <button 
          onClick={handleLogout}
          className="text-slate-500 hover:text-red-600 flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest transition-colors px-3 py-2 hover:bg-red-50 rounded-lg"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <form onSubmit={handleUpdate} className="space-y-8">
          <div>
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Select Target Facility</label>
            <select 
              className="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-lg font-medium text-slate-800 focus:bg-white focus:ring-2 focus:ring-blue-500 outline-none transition-colors"
              onChange={handleCenterSelect}
              value={selectedCenter?.id || ''}
              required
            >
              <option value="" disabled>-- Select a center to update --</option>
              {centers.map(c => (
                <option key={c.id} value={c.id}>{c.name} ({c.city})</option>
              ))}
            </select>
          </div>

          {selectedCenter && (
            <div className="space-y-6 animate-in fade-in slide-in-from-top-4 duration-300">
              <div className="p-6 bg-slate-50 rounded-xl border border-slate-200">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                  <Users className="w-4 h-4 text-blue-500" /> Real-time Headcount
                </h3>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">Current Occupancy (Max: {selectedCenter.capacity})</label>
                  <input 
                    type="number" 
                    min="0"
                    max={selectedCenter.capacity}
                    className="w-full px-4 py-3 border border-slate-200 bg-white rounded-lg font-medium text-slate-800 focus:ring-2 focus:ring-blue-500 outline-none"
                    value={occupancy}
                    onChange={(e) => setOccupancy(parseInt(e.target.value) || 0)}
                    required
                  />
                </div>
              </div>

              <div className="p-6 bg-slate-50 rounded-xl border border-slate-200">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
                  <Package className="w-4 h-4 text-emerald-500" /> Supplies Inventory
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Food Levels</label>
                    <select 
                      className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg font-medium text-slate-800 focus:ring-2 focus:ring-blue-500 outline-none"
                      value={foodStatus}
                      onChange={(e) => setFoodStatus(e.target.value)}
                    >
                      <option value="High">High</option>
                      <option value="Adequate">Adequate</option>
                      <option value="Low">Low</option>
                      <option value="Critical">Critical</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">Water Levels</label>
                    <select 
                      className="w-full px-4 py-3 bg-white border border-slate-200 rounded-lg font-medium text-slate-800 focus:ring-2 focus:ring-blue-500 outline-none"
                      value={waterStatus}
                      onChange={(e) => setWaterStatus(e.target.value)}
                    >
                      <option value="High">High</option>
                      <option value="Adequate">Adequate</option>
                      <option value="Low">Low</option>
                      <option value="Critical">Critical</option>
                    </select>
                  </div>
                </div>
              </div>

              <button 
                type="submit" 
                disabled={loading}
                className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold tracking-wide hover:bg-blue-700 shadow-lg shadow-blue-200 transition-colors disabled:opacity-70 uppercase text-sm mt-4"
              >
                {loading ? 'Committing Updates...' : 'Commit Facility Updates'}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
