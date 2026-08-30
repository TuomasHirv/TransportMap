import { Component, inject } from '@angular/core';
import { SettingsService } from '../../services/settings.service';

@Component({
  imports: [],
  selector: 'app-settings',
  styles: ``,
  template: ` <div class="flex flex-col gap-4">
    <p class="flex flex-col gap-1 text-xl font-medium text-slate-700">Settings</p>
    <label class="flex flex-col gap-1 text-sm font-medium text-slate-700">
      Day
      <input type="date" [value]="s.day()" (change)="s.day.set($any($event.target).value)" />
    </label>

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
}
