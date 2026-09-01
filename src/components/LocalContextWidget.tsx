import { useState, useEffect } from 'react';
import { MapPin, PhoneCall, ExternalLink, Waves } from 'lucide-react';
import { FLOOD_ZONES } from '../data/floodZones';

interface HealthFacility {
  id: string;
  name: string;
  phone: string;
  lat: number;
  lon: number;
  type: string;
  address?: string;
  distance?: number;
}

// Haversine formula to calculate distance in meters
function getDistance(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371e3; // metres
  const φ1 = (lat1 * Math.PI) / 180;
  const φ2 = (lat2 * Math.PI) / 180;
  const Δφ = ((lat2 - lat1) * Math.PI) / 180;
  const Δλ = ((lon2 - lon1) * Math.PI) / 180;

  const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ / 2) * Math.sin(Δλ / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}

export default function LocalContextWidget() {
  const [weather, setWeather] = useState<any>(null);
  const [facilities, setFacilities] = useState<HealthFacility[]>([]);
  const [floodRisk, setFloodRisk] = useState<{inZone: boolean, zoneName?: string, level?: string, distance?: number} | null>(null);
  const [isGpsActive, setIsGpsActive] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);

  const loadDataForLocation = async (latitude: number, longitude: number, isGps = false) => {
    try {
      // Calculate Flood Risk Assessment
      let minDistance = Infinity;
      let closestZone = null;
      
      for (const zone of FLOOD_ZONES) {
        const dist = getDistance(latitude, longitude, zone.lat, zone.lng);
        if (dist < minDistance) {
          minDistance = dist;
          closestZone = zone;
        }
      }

      if (closestZone && minDistance <= closestZone.radius) {
        setFloodRisk({ inZone: true, zoneName: closestZone.name, level: closestZone.level, distance: minDistance });
      } else if (closestZone) {
        setFloodRisk({ inZone: false, zoneName: closestZone.name, level: 'Low', distance: minDistance });
      }

      // Fetch Weather and Health Facilities in parallel
      const [weatherRes, facilitiesRes] = await Promise.allSettled([
        fetch(`/api/weather?lat=${latitude}&lon=${longitude}`),
        fetch(`/api/nearby-health?lat=${latitude}&lon=${longitude}`)
      ]);

      if (weatherRes.status === 'fulfilled' && weatherRes.value.ok) {
        const weatherData = await weatherRes.value.json();
        setWeather(weatherData);
      } else {
        // Safe default weather
        setWeather({
          name: "Metro Manila Area",
          weather: [{ description: "Scattered Rain Showers", icon: "10d" }],
          main: { temp: 28, humidity: 82 },
          wind: { speed: 4.8 }
        });
      }

      if (facilitiesRes.status === 'fulfilled' && facilitiesRes.value.ok) {
        const facilitiesData = await facilitiesRes.value.json();
        setFacilities(facilitiesData);
      }

      setIsGpsActive(isGps);
    } catch (err: any) {
      console.warn("Context load notice:", err?.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Default location: Marikina / Metro Manila Core
    const defaultLat = 14.6308;
    const defaultLng = 121.0968;

    // Load initial data immediately for default monitoring area
    loadDataForLocation(defaultLat, defaultLng, false);

    // If geolocation is available, query for accurate GPS
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          loadDataForLocation(position.coords.latitude, position.coords.longitude, true);
        },
        () => {
          // Keep default location if permission denied or timeout
          setIsGpsActive(false);
        },
        { timeout: 8000, maximumAge: 60000 }
      );
    }
  }, []);

  if (loading) {
    return (
      <div>
        <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Location Context</h2>
        <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 animate-pulse space-y-4">
          <div className="h-8 bg-slate-200 rounded w-1/3"></div>
          <div className="h-16 bg-slate-200 rounded w-full"></div>
          <div className="h-20 bg-slate-200 rounded w-full"></div>
        </div>
      </div>
    );
  }

  if (!weather) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Weather Block */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Current Location</h2>
          <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
            isGpsActive ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'
          }`}>
            {isGpsActive ? '● GPS Active' : '● Monitoring Area'}
          </span>
        </div>
        <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 relative overflow-hidden">
          <div className="flex justify-between items-start mb-2 relative z-10">
            <div>
              <div className="text-2xl font-bold">{Math.round(weather.main?.temp ?? 28)}°C</div>
              <div className="text-sm text-slate-600 font-medium">{weather.name || 'Metro Manila Area'}</div>
            </div>
            <div className="text-blue-500">
              {weather.weather && weather.weather[0] && (
                <img 
                  src={`https://openweathermap.org/img/wn/${weather.weather[0].icon}@2x.png`} 
                  alt={weather.weather[0].description}
                  className="w-12 h-12 -mt-2 -mr-2 drop-shadow-md"
                />
              )}
            </div>
          </div>
          <div className="text-xs text-amber-600 bg-amber-50 font-bold px-2 py-1 rounded border border-amber-100 inline-block capitalize relative z-10">
            {weather.weather && weather.weather[0] ? weather.weather[0].description : 'Scattered Rain'}
          </div>
        </div>
      </div>

      {/* Flood Risk Block */}
      <div>
        <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Flood Risk Assessment</h2>
        {floodRisk?.inZone ? (
          <div className="bg-red-50 p-4 rounded-xl border border-red-200">
            <div className="flex items-center gap-2 mb-2">
              <div className="p-1.5 bg-red-100 rounded-lg text-red-600">
                <Waves className="w-4 h-4" />
              </div>
              <span className="font-bold text-red-800 text-sm">HIGH RISK AREA</span>
            </div>
            <p className="text-xs text-red-700 leading-relaxed font-medium">
              You are currently inside the <span className="font-bold">{floodRisk.zoneName}</span> flood-prone zone. Evacuate immediately if water levels rise.
            </p>
          </div>
        ) : (
          <div className="bg-emerald-50 p-4 rounded-xl border border-emerald-200">
            <div className="flex items-center gap-2 mb-2">
              <div className="p-1.5 bg-emerald-100 rounded-lg text-emerald-600">
                <MapPin className="w-4 h-4" />
              </div>
              <span className="font-bold text-emerald-800 text-sm">LOW RISK AREA</span>
            </div>
            <p className="text-xs text-emerald-700 leading-relaxed font-medium">
              Your location is currently outside major flood zones. Nearest zone is {floodRisk?.zoneName} ({(floodRisk?.distance ? floodRisk.distance / 1000 : 0).toFixed(1)}km away).
            </p>
          </div>
        )}
      </div>

      {/* Health Facilities Block */}
      <div>
        <h2 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Nearby Health Facilities</h2>
        {facilities.length === 0 ? (
          <div className="text-sm text-slate-500 font-medium italic">No health facilities found nearby.</div>
        ) : (
          <div className="space-y-3">
            {facilities.map((facility) => (
              <div key={facility.id} className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm hover:border-slate-300 transition-colors">
                <div className="flex justify-between items-start mb-1.5">
                  <div className="pr-2">
                    <div className="text-sm font-bold text-slate-800 leading-tight mb-0.5">{facility.name}</div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold text-blue-600 uppercase tracking-wider">{facility.type}</span>
                      {facility.distance !== undefined && (
                        <span className="text-[10px] text-slate-500 font-medium">
                          • {facility.distance < 1000 ? `${facility.distance}m` : `${(facility.distance / 1000).toFixed(1)}km`} away
                        </span>
                      )}
                    </div>
                  </div>
                  <a 
                    href={`https://www.google.com/maps/dir/?api=1&destination=${facility.lat},${facility.lon}`}
                    target="_blank"
                    rel="noreferrer"
                    className="p-1.5 bg-slate-50 hover:bg-blue-50 hover:text-blue-600 text-slate-600 rounded-lg transition-colors flex-shrink-0"
                    title="Open Directions in Google Maps"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </div>
                {facility.address && (
                  <p className="text-[11px] text-slate-500 mb-1.5 line-clamp-1">{facility.address}</p>
                )}
                {facility.phone && facility.phone !== "Number not available" && (
                  <div className="flex items-center gap-2 text-xs font-medium text-slate-700 mt-1">
                    <PhoneCall className="w-3.5 h-3.5 text-slate-400" />
                    <a href={`tel:${facility.phone}`} className="hover:text-blue-600 transition-colors font-semibold">{facility.phone}</a>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

    </div>
  );
}
