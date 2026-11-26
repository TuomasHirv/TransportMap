import { Component, computed, inject } from '@angular/core';
import { SettingsService } from '../../services/settings.service';

@Component({
  imports: [],
  selector: 'app-settings',
  styles: ``,
  template: ` <div class="flex flex-col gap-4">
    <!-- On mobile the bottom-sheet handle already shows this heading -->
    <p class="hidden md:flex flex-col gap-1 text-xl font-medium text-slate-700">Settings</p>
    <fieldset class="flex flex-col gap-1">
      <legend class="text-sm font-medium text-slate-700 mb-1">Day</legend>
      <div class="flex flex-wrap items-center gap-4">
        @for (d of days; track d) {
          <label class="flex items-center gap-2 py-1 text-sm text-slate-700 cursor-pointer">
            <input
              type="radio"
              name="days"
              class="h-4 w-4 accent-sky-600"
              [checked]="s.days() === d"
              (change)="s.days.set(d)"
            />
            <span class="capitalize">{{ d }}</span>
          </label>
        }
      </div>
    </fieldset>
    <label class="flex flex-col gap-1 text-sm font-medium text-slate-700"
      >Time
      <input
        type="time"
        class="rounded-md border border-slate-300 px-3 py-2 text-base"
        [value]="s.time()" (change)="s.time.set($any($event.target).value)" />
    </label>

    <label class="flex flex-col gap-1 text-sm font-medium text-slate-700">
      Duration (minutes)
      <input
        type="number"
        min="5"
        max="60"
        step="5"
        class="rounded-md border border-slate-300 px-3 py-2 text-base"
        [value]="s.duration() / 60"
        (change)="setDuration($any($event.target))"
      />
    </label>
    <label class="flex flex-col gap-1 text-sm font-medium text-slate-700">
      Transfers
      <input
        type="number"
        min="1"
        max="8"
        step="1"
        class="rounded-md border border-slate-300 px-3 py-2 text-base"
        [value]="s.transfers()"
        (change)="s.transfers.set(+$any($event.target).value)"
      />
    </label>
    <div>
      @if (lines().length) {
        <div class="flex flex-col gap-2">
          <span class="text-sm font-medium text-slate-700">Lines you can walk to</span>
          <div class="flex flex-wrap gap-1.5">
            @for (l of lines(); track l.name) {
              <span class="rounded-md bg-slate-800 px-2 py-1 text-xs font-semibold text-white">
                {{ l.name }}
                <span class="ml-1 font-normal opacity-70">{{ l.mins }} min</span>
              </span>
            }
          </div>
        </div>
      }
    </div>
  </div>`,
})
export class Settings {
  s = inject(SettingsService);
  days = ['weekday', 'saturday', 'sunday'] as const;
  // The max attribute only limits the spinner; typed values have to be clamped here.
  setDuration(input: HTMLInputElement) {
    const mins = Math.min(60, Math.max(5, +input.value || 5));
    input.value = String(mins);
    this.s.duration.set(mins * 60);
  }
  lines = computed(() =>
    Object.entries(this.s.upcoming())
      .map(([name, dep]) => ({ name, mins: Math.round((dep - this.s.at()) / 60) }))
      .sort((a, b) => a.mins - b.mins),
  );
}
