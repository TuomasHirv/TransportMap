import { Component, computed, inject, signal } from '@angular/core';
import { MapComponent } from '../components/MapComponent';
import { Settings } from './components/settings/settings';
import { Info } from './components/info/info';
import { SettingsService } from './services/settings.service';
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [MapComponent, Settings, Info],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly title = signal('frontend');
  private s = inject(SettingsService);
  // Mobile bottom sheet state; on desktop the panel is always shown.
  protected readonly open = signal(false);
  protected readonly summary = computed(
    () => `${this.s.days()} · ${this.s.time()} · ${this.s.duration() / 60} min`,
  );
}
