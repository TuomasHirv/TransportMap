import { Component, AfterViewInit, ElementRef, ViewChild, inject, signal } from '@angular/core';
import * as L from 'leaflet';

import { ReachableService, type ReachableStop } from '../app/services/reachable.service';
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
  private map!: L.Map;
  private api = inject(ReachableService);
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
    this.map.fitBounds(HSL_BOUNDS);
    this.map.on('click', (e: L.LeafletMouseEvent) => {
      this.loading.set(true);
      this.api.query(e.latlng.lat, e.latlng.lng, 8 * 3600, 1800).subscribe({
        next: (stops) => {
          this.stops.set(stops);
          this.loading.set(false);
        },
        error: (err) => {
          console.error(err);
          this.loading.set(false);
        },
      });
    });
  }
}
