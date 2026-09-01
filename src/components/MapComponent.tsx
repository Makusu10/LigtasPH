import { useEffect, useState, useCallback } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, Circle } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { EvacuationCenter } from '../types';
import { FLOOD_ZONES } from '../data/floodZones';
import { CRITICAL_FACILITIES } from '../data/criticalFacilities';
import { Layers, LocateFixed, ShieldAlert, Cross, Tent, Waves, PhoneCall } from 'lucide-react';
import L from 'leaflet';

// @ts-ignore
import icon from 'leaflet/dist/images/marker-icon.png';
// @ts-ignore
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

let DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

const hospitalIcon = L.divIcon({
  html: `<div class="bg-red-500 w-5 h-5 rounded-full border-2 border-white shadow-md flex items-center justify-center relative"><div class="bg-white w-2.5 h-[2px] absolute"></div><div class="bg-white w-[2px] h-2.5 absolute"></div></div>`,
  className: '',
  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

const policeIcon = L.divIcon({
  html: `<div class="bg-blue-600 w-5 h-5 rounded border-2 border-white shadow-md flex items-center justify-center"><div class="bg-white w-2 h-2 rounded-full"></div></div>`,
  className: '',
  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

const userIcon = L.divIcon({
  html: `<div class="relative flex h-5 w-5"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span><span class="relative inline-flex rounded-full h-5 w-5 bg-blue-500 border-2 border-white shadow"></span></div>`,
  className: '',
  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

interface MapComponentProps {
  centers: EvacuationCenter[];
  activeCenterId: number | null;
}

function MapUpdater({ center, zoom, userLocation, shouldRecenter }: { center: [number, number], zoom: number, userLocation: [number, number] | null, shouldRecenter: boolean }) {
  const map = useMap();
  useEffect(() => {
    if (!shouldRecenter) {
      map.setView(center, zoom);
    }
  }, [center, zoom, map, shouldRecenter]);

  useEffect(() => {
    if (shouldRecenter && userLocation) {
      map.flyTo(userLocation, 15);
    }
  }, [shouldRecenter, userLocation, map]);
  return null;
}

export default function MapComponent({ centers, activeCenterId }: MapComponentProps) {
  const activeCenter = centers.find(c => c.id === activeCenterId);
  const mapCenter: [number, number] = activeCenter 
    ? [activeCenter.lat, activeCenter.lng] 
    : [14.6308, 121.0968]; // Default to Marikina area

  const [showFloodZones, setShowFloodZones] = useState(true);
  const [showEvacCenters, setShowEvacCenters] = useState(true);
  const [showHealth, setShowHealth] = useState(false);
  const [showPolice, setShowPolice] = useState(false);
  const [showLayers, setShowLayers] = useState(false);

  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
  const [recenterFlag, setRecenterFlag] = useState(false);

  useEffect(() => {
    let watchId: number;
    if ("geolocation" in navigator) {
      watchId = navigator.geolocation.watchPosition(
        (pos) => {
          setUserLocation([pos.coords.latitude, pos.coords.longitude]);
        },
        (err) => console.warn("Location error:", err),
        { enableHighAccuracy: true, maximumAge: 10000 }
      );
    }
    return () => {
      if (watchId) navigator.geolocation.clearWatch(watchId);
    };
  }, []);

  const handleRecenter = () => {
    if (userLocation) {
      setRecenterFlag(true);
      setTimeout(() => setRecenterFlag(false), 1000);
    } else {
      alert("Current location not available yet.");
    }
  };

  return (
    <div className="absolute inset-0 z-0 bg-slate-200">
      
      {/* Map Controls Overlay */}
      <div className="absolute top-4 right-4 z-[400] flex flex-col gap-2">
        <button 
          onClick={handleRecenter}
          className="bg-white p-3 rounded-full shadow-lg text-slate-700 hover:text-blue-600 hover:bg-slate-50 transition-all border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-center"
          title="Recenter to my location"
        >
          <LocateFixed className="w-5 h-5" />
        </button>
        
        <div className="relative">
          <button 
            onClick={() => setShowLayers(!showLayers)}
            className={`p-3 rounded-full shadow-lg transition-all border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center justify-center ${showLayers ? 'bg-blue-50 text-blue-600' : 'bg-white text-slate-700 hover:text-blue-600 hover:bg-slate-50'}`}
            title="Map Layers"
          >
            <Layers className="w-5 h-5" />
          </button>
          
          {showLayers && (
            <div className="absolute top-0 right-14 w-64 bg-white rounded-xl shadow-xl border border-slate-200 p-4 animate-in fade-in zoom-in-95 duration-200">
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Map Overlays</h3>
              
              <div className="space-y-3">
                <label className="flex items-center justify-between cursor-pointer group">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 group-hover:text-blue-600 transition-colors">
                    <Waves className="w-4 h-4 text-orange-500" />
                    Flood Zones
                  </div>
                  <input type="checkbox" className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 accent-blue-600 cursor-pointer" checked={showFloodZones} onChange={(e) => setShowFloodZones(e.target.checked)} />
                </label>
                
                <label className="flex items-center justify-between cursor-pointer group">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 group-hover:text-blue-600 transition-colors">
                    <Tent className="w-4 h-4 text-blue-500" />
                    Evacuation Centers
                  </div>
                  <input type="checkbox" className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 accent-blue-600 cursor-pointer" checked={showEvacCenters} onChange={(e) => setShowEvacCenters(e.target.checked)} />
                </label>
                
                <label className="flex items-center justify-between cursor-pointer group">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 group-hover:text-blue-600 transition-colors">
                    <Cross className="w-4 h-4 text-red-500" />
                    Health Facilities
                  </div>
                  <input type="checkbox" className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 accent-blue-600 cursor-pointer" checked={showHealth} onChange={(e) => setShowHealth(e.target.checked)} />
                </label>

                <label className="flex items-center justify-between cursor-pointer group">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 group-hover:text-blue-600 transition-colors">
                    <ShieldAlert className="w-4 h-4 text-blue-700" />
                    Police Stations
                  </div>
                  <input type="checkbox" className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500 accent-blue-600 cursor-pointer" checked={showPolice} onChange={(e) => setShowPolice(e.target.checked)} />
                </label>
              </div>
            </div>
          )}
        </div>
      </div>

      <MapContainer 
        center={mapCenter} 
        zoom={13} 
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <MapUpdater center={mapCenter} zoom={activeCenter ? 15 : 13} userLocation={userLocation} shouldRecenter={recenterFlag} />
        
        {/* User Location */}
        {userLocation && (
          <Marker position={userLocation} icon={userIcon}>
            <Popup>
              <div className="p-1 font-bold text-sm text-slate-800">Your Current Location</div>
            </Popup>
          </Marker>
        )}

        {/* Render Flood Zones */}
        {showFloodZones && FLOOD_ZONES.map(zone => (
          <Circle 
            key={`zone-${zone.id}`}
            center={[zone.lat, zone.lng]}
            radius={zone.radius}
            pathOptions={{
              color: zone.color,
              fillColor: zone.color,
              fillOpacity: 0.2,
              weight: 1
            }}
          >
            <Popup>
              <div className="p-1">
                <h3 className="font-bold text-slate-800 mb-1">{zone.name}</h3>
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                  zone.level === 'High' ? 'bg-red-50 text-red-600' : 'bg-orange-50 text-orange-600'
                }`}>
                  {zone.level} Risk Zone
                </span>
              </div>
            </Popup>
          </Circle>
        ))}

        {/* Render Evacuation Centers */}
        {showEvacCenters && centers.map(center => {
          const occupancyRate = center.currentOccupancy / center.capacity;
          let statusColor = "text-emerald-600";
          if (occupancyRate > 0.9) statusColor = "text-red-600";
          else if (occupancyRate > 0.7) statusColor = "text-orange-600";

          return (
            <Marker key={center.id} position={[center.lat, center.lng]}>
              <Popup>
                <div className="p-1 min-w-[200px]">
                  <h3 className="font-bold text-slate-800 mb-1">{center.name}</h3>
                  <p className="text-sm text-slate-500 mb-3">{center.city}</p>
                  
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600">Occupancy</span>
                      <span className={`font-semibold bg-slate-50 px-1.5 py-0.5 rounded ${statusColor}`}>
                        {center.currentOccupancy} / {center.capacity}
                      </span>
                    </div>
                    
                    <div className="border-t border-slate-100 pt-2 space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-600">Food</span>
                        <span className={`font-semibold ${center.foodStatus === 'Low' ? 'text-red-500' : 'text-emerald-600'}`}>
                          {center.foodStatus}
                        </span>
                      </div>
                      <div className="flex justify-between text-xs">
                        <span className="text-slate-600">Water</span>
                        <span className={`font-semibold ${center.waterStatus === 'Low' ? 'text-red-500' : 'text-emerald-600'}`}>
                          {center.waterStatus}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {/* Render Critical Facilities */}
        {CRITICAL_FACILITIES.filter(f => (showHealth && (f.type === 'hospital' || f.type === 'clinic')) || (showPolice && f.type === 'police')).map(facility => (
          <Marker 
            key={facility.id} 
            position={[facility.lat, facility.lon]}
            icon={facility.type === 'police' ? policeIcon : hospitalIcon}
          >
            <Popup>
              <div className="p-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider text-white ${
                    facility.type === 'police' ? 'bg-blue-600' : 'bg-red-500'
                  }`}>
                    {facility.type}
                  </span>
                </div>
                <h3 className="font-bold text-slate-800 mb-1">{facility.name}</h3>
                <p className="text-xs text-slate-500 mb-2">{facility.address}</p>
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-700 bg-slate-50 p-2 rounded-lg border border-slate-100">
                  <PhoneCall className="w-3.5 h-3.5 text-slate-400" />
                  <a href={`tel:${facility.phone}`} className="hover:text-blue-600">{facility.phone}</a>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

      </MapContainer>
    </div>
  );
}
