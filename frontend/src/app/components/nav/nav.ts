import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';

@Component({
  selector: 'app-nav',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  template: `
    <nav class="navbar">
      <div class="brand">
        <span class="brand-icon">⚡</span>
        <span>PowMr Controller</span>
      </div>
      <div class="nav-links">
        <a routerLink="/dashboard" routerLinkActive="active">Dashboard</a>
        <a routerLink="/control" routerLinkActive="active">Inverter Control</a>
        <a routerLink="/automation" routerLinkActive="active">Automation</a>
      </div>
    </nav>
  `,
  styles: [`
    .navbar {
      background: #1565c0;
      color: white;
      display: flex;
      align-items: center;
      padding: 0 20px;
      height: 56px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 1.1rem;
      font-weight: 700;
      margin-right: 32px;
    }
    .brand-icon { font-size: 1.4rem; }
    .nav-links { display: flex; gap: 4px; }
    .nav-links a {
      color: rgba(255,255,255,0.85);
      text-decoration: none;
      padding: 8px 14px;
      border-radius: 4px;
      font-size: 0.9rem;
      transition: background 0.2s;
    }
    .nav-links a:hover { background: rgba(255,255,255,0.15); color: white; }
    .nav-links a.active { background: rgba(255,255,255,0.2); color: white; font-weight: 600; }
  `]
})
export class NavComponent {}
