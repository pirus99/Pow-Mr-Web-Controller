import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard';
import { InverterControlComponent } from './components/inverter-control/inverter-control';
import { AutomationComponent } from './components/automation/automation';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: DashboardComponent },
  { path: 'control', component: InverterControlComponent },
  { path: 'automation', component: AutomationComponent },
];
