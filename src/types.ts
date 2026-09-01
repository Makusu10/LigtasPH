export interface EvacuationCenter {
  id: number;
  name: string;
  city: string;
  lat: number;
  lng: number;
  capacity: number;
  currentOccupancy: number;
  foodStatus: string;
  waterStatus: string;
  medicalStatus: string;
}

export interface Hotline {
  id: number;
  city: string;
  agency: string;
  number: string;
}
