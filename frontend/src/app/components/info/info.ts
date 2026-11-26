import { Component } from '@angular/core';

@Component({
  imports: [],
  selector: 'app-info',
  styles: ``,
  template: ` <button
      type="button"
      class="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 cursor-pointer"
      (click)="dialog.showModal()"
    >
      About &amp; credits
    </button>

    <dialog
      #dialog
      class="m-auto w-[calc(100%-2rem)] max-w-lg max-h-[85dvh] overflow-y-auto rounded-lg p-6 shadow-xl backdrop:bg-slate-900/50"
      (click)="$event.target === dialog && dialog.close()"
    >
      <div class="flex flex-col gap-4 text-sm text-slate-700">
        <p class="text-xl font-medium">About Transport Map</p>
        <p>
          Click anywhere on the map to see where you can get by public transport within the chosen
          time. Routes are computed with a RAPTOR journey planner.
        </p>

        <section class="flex flex-col gap-1">
          <p class="font-medium">Timetable data</p>
          <p>
            Source: HSL (Helsinki Regional Transport Authority). GTFS feed from
            <a
              class="text-sky-700 underline"
              href="https://www.hsl.fi/en/hsl/open-data"
              target="_blank"
              rel="noopener"
              >HSL open data</a
            >
            via Digitransit, licensed under
            <a
              class="text-sky-700 underline"
              href="https://creativecommons.org/licenses/by/4.0/"
              target="_blank"
              rel="noopener"
              >CC BY 4.0</a
            >. The feed has been filtered to the trips this app uses.
          </p>
        </section>

        <section class="flex flex-col gap-1">
          <p class="font-medium">Map and coastline</p>
          <p>
            Map tiles and the land polygon used to clip isochrones are &copy;
            <a
              class="text-sky-700 underline"
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noopener"
              >OpenStreetMap contributors</a
            >, available under the Open Database License (ODbL). Land polygons from
            <a
              class="text-sky-700 underline"
              href="https://osmdata.openstreetmap.de/"
              target="_blank"
              rel="noopener"
              >osmdata.openstreetmap.de</a
            >.
          </p>
        </section>

        <button
          type="button"
          class="self-end rounded-md bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 cursor-pointer"
          (click)="dialog.close()"
        >
          Close
        </button>
      </div>
    </dialog>`,
})
export class Info {}
