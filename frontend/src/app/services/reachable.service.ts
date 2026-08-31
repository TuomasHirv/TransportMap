import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ReachableStop {
  stop_id: string;
  lat: number;
  lon: number;
  seconds_left: number;
  arrival: number;
}

@Injectable({ providedIn: 'root' })
export class ReachableService {
  private http = inject(HttpClient);

  query(
    lat: number,
    lon: number,
    at: number,
    budget: number,
    day: string,
  ): Observable<ReachableStop[]> {
    return this.http.get<ReachableStop[]>('/api/reachable', {
      params: { lat, lon, at, budget, day },
    });
  }
}
