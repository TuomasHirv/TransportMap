import { Injectable, signal, computed } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  days = signal<'weekday' | 'saturday' | 'sunday'>('weekday');
  time = signal('08:00');
  duration = signal(1800);
  transfers = signal(4);
  at = computed(() => {
    const [h, m] = this.time().split(':').map(Number);
    return h * 3600 + m * 60;
  });
}
