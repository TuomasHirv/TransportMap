import { Component, signal } from '@angular/core';
import { MapComponent } from '../components/MapComponent';
import { Settings } from './components/settings/settings';
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [MapComponent, Settings],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly title = signal('frontend');
}
