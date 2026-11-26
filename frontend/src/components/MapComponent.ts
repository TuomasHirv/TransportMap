import {
  Component,
  AfterViewInit,
  ElementRef,
  ViewChild,
  inject,
  signal,
  effect,
  DestroyRef,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import * as L from 'leaflet';
import 'leaflet.markercluster';
import {
  ReachableService,
  type ReachableStop,
  ReachableResponse,
} from '../app/services/reachable.service';
import { SettingsService } from '../app/services/settings.service';
import { asyncScheduler, catchError, EMPTY, map, Subject, switchMap, throttleTime } from 'rxjs';

const QUERY_INTERVAL_MS = 500;
interface Query {
  origin: L.LatLng;
  at: number;
  budget: number;
  day: string;
  transfers: number;
}

const HSL_BOUNDS = L.latLngBounds([60.08, 24.45], [60.36, 25.3]);
// The plugin patches the global window.L; in production builds `import * as L` is a
// copy taken before that, so markerClusterGroup has to be read from the global.
const LeafletGlobal = (window as unknown as { L: typeof L }).L;

@Component({
  selector: 'app-map',
  standalone: true,
  template: `<div class="relative h-full">
    <div #mapEl class="map"></div>
    @if (!origin()) {
      <div
        class="pointer-events-none absolute bottom-6 left-1/2 z-1000 -translate-x-1/2 whitespace-nowrap rounded-md bg-white/90 px-3 py-1.5 text-sm font-medium text-slate-700 shadow"
      >
        Tap the map to pick a starting point
      </div>
    }
    @if (loading()) {
      <div
        class="absolute top-3 right-3 z-1000 flex items-center gap-2 rounded-md bg-white/90 px-3 py-1.5 text-sm font-medium text-slate-700 shadow"
        role="status"
      >
        <span
          class="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-sky-600"
        ></span>
        Calculating…
      </div>
    }
  </div>`,
  styles: [
    `
      .map {
        height: 100%;
        width: 100%;
      }
    `,
  ],
})
export class MapComponent implements AfterViewInit {
  @ViewChild('mapEl') mapEl!: ElementRef<HTMLDivElement>;
  private s = inject(SettingsService);
  private results = LeafletGlobal.markerClusterGroup({
    maxClusterRadius: 35,
    disableClusteringAtZoom: 15,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: false,
    spiderfyOnMaxZoom: false,
  });
  private radius = L.layerGroup();
  private isoRenderer!: L.Canvas;
  private originMarker?: L.CircleMarker;
  protected origin = signal<L.LatLng | null>(null);
  private destroyRef = inject(DestroyRef);

  private map!: L.Map;
  private api = inject(ReachableService);
  private queries = new Subject<Query>();
  // Only the newest query clears `loading`; an older response landing while the
  // newest is still held by the throttle must not hide the indicator.
  private latest?: Query;
  constructor() {
    effect(() => {
      const origin = this.origin();
      const at = this.s.at();
      const budget = this.s.duration();
      const day = this.s.days();
      const transfers = this.s.transfers();
      if (transfers > 8 || transfers < 1) return;
      if (!day) return;
      if (!origin) return;

      const q = { origin, at, budget, day, transfers };
      this.latest = q;
      this.loading.set(true);
      this.queries.next(q);
    });

    // At most one request per QUERY_INTERVAL_MS. The first of a burst goes out at once
    // and the latest is sent when the window ends; switchMap drops superseded responses.
    this.queries
      .pipe(
        throttleTime(QUERY_INTERVAL_MS, asyncScheduler, { leading: true, trailing: true }),
        switchMap((q) =>
          this.api.query(q.origin.lat, q.origin.lng, q.at, q.budget, q.day, q.transfers).pipe(
            map((res) => ({ res, q })),
            // A failed request must not complete the stream and stop later queries.
            catchError((err) => {
              console.error(err);
              if (q === this.latest) this.loading.set(false);
              return EMPTY;
            }),
          ),
        ),
        takeUntilDestroyed(),
      )
      .subscribe(({ res, q }) => {
        console.log(res);
        this.draw(res, q.origin, q.budget);
        this.s.upcoming.set(res.upcoming);
        if (q === this.latest) this.loading.set(false);
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
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(this.map);
    const pane = this.map.createPane('iso');
    pane.style.pointerEvents = 'none';
    pane.style.opacity = '0.35';
    pane.style.zIndex = '450';
    this.isoRenderer = L.canvas({ pane: 'iso' });

    this.radius.addTo(this.map); // blob first, so dots draw above
    this.results.addTo(this.map);
    this.map.fitBounds(HSL_BOUNDS);
    // The container changes size when the mobile settings sheet opens/closes or the
    // phone rotates; Leaflet has to be told so tiles and clicks line up.
    const ro = new ResizeObserver(() => this.map.invalidateSize());
    ro.observe(this.mapEl.nativeElement);
    this.destroyRef.onDestroy(() => ro.disconnect());
    this.map.on('click', (e: L.LeafletMouseEvent) => this.origin.set(e.latlng));
  }

  private static BANDS: Record<number, string> = {
    10: '#e8a33d',
    20: '#bc3754',
    30: '#511a63',
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
      if (Math.round(s.seconds_left / 60) > 2) {
        L.circleMarker([s.lat, s.lon], { radius: 2 })
          .bindTooltip(`${s.stop_name} — ${Math.round(s.seconds_left / 60)} min`)
          .addTo(this.results);
        continue;
      }
      L.circleMarker([s.lat, s.lon], { radius: 1, color: '#6E260E' })
        .bindTooltip(`${s.stop_name} — ${Math.round((budget - s.seconds_left) / 60)} min`)
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
