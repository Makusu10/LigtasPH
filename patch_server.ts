import fs from 'fs';

let content = fs.readFileSync('server.ts', 'utf8');

const replacement = `
import { CRITICAL_FACILITIES } from './src/data/criticalFacilities';

function calculateDistanceInMeters(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371e3; // meters
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const deltaP = ((lat2 - lat1) * Math.PI) / 180;
  const deltaL = ((lon2 - lon1) * Math.PI) / 180;

  const a = Math.sin(deltaP / 2) * Math.sin(deltaP / 2) +
            Math.cos(p1) * Math.cos(p2) *
            Math.sin(deltaL / 2) * Math.sin(deltaL / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

  return R * c;
}

app.get("/api/nearby-health", async (req, res) => {
  const lat = parseFloat(req.query.lat as string);
  const lon = parseFloat(req.query.lon as string);

  const targetLat = !isNaN(lat) ? lat : 14.6308;
  const targetLon = !isNaN(lon) ? lon : 121.0968;

  const healthFacilities = CRITICAL_FACILITIES.filter(f => f.type === 'hospital' || f.type === 'clinic');

  const sorted = healthFacilities.map((facility) => {
    const distMeters = calculateDistanceInMeters(targetLat, targetLon, facility.lat, facility.lon);
    return {
      ...facility,
      distance: Math.round(distMeters)
    };
  }).sort((a, b) => (a.distance || 0) - (b.distance || 0));

  res.json(sorted.slice(0, 5));
});
`;

// regex to replace the entire app.get("/api/nearby-health"... block
content = content.replace(/\/\/ Nearby Health Facilities Proxy \(using OpenStreetMap Overpass API\)[\s\S]*?\}\);/, replacement.trim());

fs.writeFileSync('server.ts', content);
