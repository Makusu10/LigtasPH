export interface CriticalFacility {
  id: string;
  name: string;
  phone: string;
  lat: number;
  lon: number;
  type: "hospital" | "clinic" | "police" | "evacuation";
  address: string;
}

export const CRITICAL_FACILITIES: CriticalFacility[] = [
  // Health Facilities
  { id: "h-marikina-amang", name: "Amang Rodriguez Memorial Medical Center", phone: "(02) 8941-5854", lat: 14.6337, lon: 121.0991, type: "hospital", address: "Sumulong Hwy, Marikina" },
  { id: "h-marikina-valley", name: "Marikina Valley Medical Center", phone: "(02) 8682-2222", lat: 14.6401, lon: 121.1065, type: "hospital", address: "Sumulong Hwy, Sto. Niño, Marikina" },
  { id: "h-marikina-garcia", name: "Garcia General Hospital", phone: "(02) 8941-5511", lat: 14.6315, lon: 121.0962, type: "hospital", address: "Bayan-Bayanan Ave, Marikina" },
  { id: "h-marikina-vincent", name: "St. Vincent General Hospital", phone: "(02) 8948-0314", lat: 14.6468, lon: 121.1077, type: "hospital", address: "Concepcion Uno, Marikina" },
  { id: "h-marikina-stonino", name: "Sto. Niño Barangay Health Center", phone: "(02) 8646-0422", lat: 14.6395, lon: 121.1012, type: "clinic", address: "Sto. Niño, Marikina" },
  
  // Police Stations
  { id: "p-marikina-hq", name: "Marikina City Police Station (HQ)", phone: "(02) 8646-1631", lat: 14.6318, lon: 121.0975, type: "police", address: "Shoe Ave, Marikina" },
  { id: "p-marikina-sub1", name: "Marikina Police Sub-Station 1", phone: "(02) 8942-0111", lat: 14.6550, lon: 121.1085, type: "police", address: "Concepcion Uno, Marikina" },
  { id: "p-marikina-sub2", name: "Marikina Police Sub-Station 2", phone: "(02) 8681-1111", lat: 14.6220, lon: 121.0920, type: "police", address: "San Roque, Marikina" },
  { id: "p-qc-ps3", name: "Quezon City Police Station 3 (Talipapa)", phone: "(02) 8936-1111", lat: 14.6750, lon: 121.0350, type: "police", address: "Talipapa, Quezon City" },
  { id: "p-pasig-hq", name: "Pasig City Police Station", phone: "(02) 8641-1111", lat: 14.5775, lon: 121.0845, type: "police", address: "Pasig Blvd, Pasig" },
];
