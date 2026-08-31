import { Component, inject } from '@angular/core';
import { SettingsService } from '../../services/settings.service';

@Component({
  imports: [],
  selector: 'app-settings',
  styles: ``,
  template: ` <div class="flex flex-col gap-4">
    <p class="flex flex-col gap-1 text-xl font-medium text-slate-700">Settings</p>
    <fieldset class="flex flex-col gap-1">
      <legend class="text-sm font-medium text-slate-700 mb-1">Day</legend>

      @for (d of days; track d) {
        <label class="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
          <input
            type="radio"
            name="days"
            class="accent-sky-600"
            [checked]="s.days() === d"
            (change)="s.days.set(d)"
          />
          <span class="capitalize">{{ d }}</span>
        </label>
      }
    </fieldset>
    <label class="flex flex-col gap-1 text-sm font-medium text-slate-700"
      >Time
      <input type="time" [value]="s.time()" (change)="s.time.set($any($event.target).value)" />
    </label>

    <label class="flex flex-col gap-1 text-sm font-medium text-slate-700">
      Duration (minutes)
      <input
        type="number"
        min="5"
        max="120"
        step="5"
        class="rounded-md border border-slate-300 px-3 py-2 text-base"
        [value]="s.duration() / 60"
        (change)="s.duration.set(+$any($event.target).value * 60)"
      />
    </label>
  </div>`,
})
export class Settings {
  s = inject(SettingsService);
  days = ['weekday', 'saturday', 'sunday'] as const;
}
