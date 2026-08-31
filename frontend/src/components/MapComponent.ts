import {
  Component,
  AfterViewInit,
  ElementRef,
  ViewChild,
  inject,
  signal,
  effect,
} from '@angular/core';
import * as L from 'leaflet';

import { ReachableService, type ReachableStop } from '../app/services/reachable.service';
import { SettingsService } from '../app/services/settings.service';
const HSL_BOUNDS = L.latLngBounds([60.08, 24.45], [60.36, 25.3]);

@Component({
  selector: 'app-map',
  standalone: true,
  template: `<div #mapEl class="map"></div>`,
  styles: [
    `
      .map {
        height: 100vh;
        width: 100%;
      }
    `,
  ],
})
export class MapComponent implements AfterViewInit {
  @ViewChild('mapEl') mapEl!: ElementRef<HTMLDivElement>;
  private s = inject(SettingsService);
  private results = L.layerGroup();
  private originMarker?: L.CircleMarker;
  private origin = signal<L.LatLng | null>(null);
  private static RAMP = ['#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#104281'];

  private colourFor(travelSecs: number, budget: number): string {
    const band = Math.min(4, Math.floor((travelSecs / budget) * 5));
    return MapComponent.RAMP[band];
  }

  private map!: L.Map;
  private api = inject(ReachableService);
  constructor() {
    effect(() => {
      const origin = this.origin();
      const at = this.s.at();
      const budget = this.s.duration();
      const day = this.s.days();
      if (!day) return;
      if (!origin) return;

      this.api
        .query(origin.lat, origin.lng, at, budget, day)
        .subscribe({ next: (stops) => this.draw(stops, origin, budget) });
    });
  }

  stops = signal<ReachableStop[]>([]);
  loading = signal(false);

  ngAfterViewInit(): void {
    this.map = L.map(this.mapEl.nativeElement, {
      maxBounds: HSL_BOUNDS,
      maxBoundsViscosity: 1000,
      minZoom: 11,
      maxZoom: 18,
    });

    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(this.map);
    this.results.addTo(this.map);
    this.map.fitBounds(HSL_BOUNDS);
    this.map.on('click', (e: L.LeafletMouseEvent) => {
      this.map.on('click', (e) => this.origin.set(e.latlng));
    });
  }

  private draw(stops: ReachableStop[], origin: L.LatLng, budget: number): void {
    this.results.clearLayers();

    for (const s of stops) {
      const travel = budget - s.seconds_left;
      L.circleMarker([s.lat, s.lon], {
        radius: 3,
        fillColor: this.colourFor(travel, budget),
        fillOpacity: 0.9,
        weight: 2,
      })
        .bindTooltip(`${s.stop_name} — ${Math.round(travel / 60)} min`)
        .addTo(this.results);
    }

    this.originMarker?.remove();
    this.originMarker = L.circleMarker(origin, {
      radius: 7,
      fillColor: '#e34948',
      fillOpacity: 1,
      color: '#fff',
      weight: 3,
    }).addTo(this.map);
  }
}
