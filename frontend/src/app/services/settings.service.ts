import { Injectable, signal, computed } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  day = signal('2026-09-01');
  time = signal('08:00');
  duration = signal(1800);

  at = computed(() => {
    const [h, m] = this.time().split(':').map(Number);
    return h * 3600 + m * 60;
  });
}
