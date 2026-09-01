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

import {
  ReachableService,
  type ReachableStop,
  ReachableResponse,
} from '../app/services/reachable.service';
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
  private radius = L.layerGroup();
  private isoRenderer!: L.Canvas;
  private originMarker?: L.CircleMarker;
  private origin = signal<L.LatLng | null>(null);

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
    const pane = this.map.createPane('iso');
    pane.style.opacity = '0.35';
    pane.style.zIndex = '450';
    this.isoRenderer = L.canvas({ pane: 'iso' });

    this.radius.addTo(this.map); // blob first, so dots draw above
    this.results.addTo(this.map);
    this.map.fitBounds(HSL_BOUNDS);
    this.map.on('click', (e: L.LeafletMouseEvent) => this.origin.set(e.latlng));
  }

  private static BANDS: Record<number, string> = {
    10: '#8a3312',
    20: '#d2551f',
    30: '#ef8449',
  };

  private draw(res: ReachableResponse, origin: L.LatLng, budget: number): void {
    this.results.clearLayers();
    this.radius.clearLayers();

    L.geoJSON(res.bands, {
      pane: 'iso',
      style: (f) => ({
        renderer: this.isoRenderer,
        stroke: false,
        fillColor: MapComponent.BANDS[f!.properties['max_minutes']] ?? '#256abf',
        fillOpacity: 1,
      }),
    }).addTo(this.radius);
    for (const s of res.stops) {
      L.circleMarker([s.lat, s.lon], { radius: 3 })
        .bindTooltip(`${s.stop_name} — ${Math.round(s.seconds_left / 60)} min`)
        .addTo(this.results);
    }

    this.originMarker?.remove();
    this.originMarker = L.circleMarker(origin, {
      radius: 4,
      fillColor: '#e34948',
      fillOpacity: 1,
      color: '#e34948',
      weight: 3,
    }).addTo(this.map);
  }
}
