import { bootstrapApplication } from '@angular/platform-browser';
import { inject as injectAnalytics } from '@vercel/analytics';
import { appConfig } from './app/app.config';
import { App } from './app/app';

// Vercel Web Analytics; only reports from Vercel deployments, logs to console in dev.
injectAnalytics();

bootstrapApplication(App, appConfig)
  .catch((err) => console.error(err));
