import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

export interface ReachableResponse {
  stops: ReachableStop[];
  bands: GeoJSON.FeatureCollection<GeoJSON.MultiPolygon, BandProps>;
}

export interface BandProps {
  max_seconds: number;
  max_minutes: number;
}

export interface ReachableStop {
  stop_name: string;
  lat: number;
  lon: number;
  seconds_left: number;
  arrival: number;
}

@Injectable({ providedIn: 'root' })
export class ReachableService {
  private http = inject(HttpClient);

  query(lat: number, lon: number, at: number, budget: number, day: string, max_rounds: number) {
    return this.http.get<ReachableResponse>('/api/isochrone', {
      params: { lat, lon, at, budget, day, max_rounds },
    });
  }
}
