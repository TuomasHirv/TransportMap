import { Component, signal } from '@angular/core';
import { MapComponent } from '../components/MapComponent';
import { Settings } from './components/settings/settings';
import { Info } from './components/info/info';
@Component({
  selector: 'app-root',
  standalone: true,
  imports: [MapComponent, Settings, Info],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  protected readonly title = signal('frontend');
}
