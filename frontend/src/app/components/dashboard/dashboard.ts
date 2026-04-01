import { Component, OnInit, OnDestroy, ChangeDetectorRef, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, InverterStatus, MetricsResult } from '../../services/api';
import { interval, Subscription } from 'rxjs';
import { startWith } from 'rxjs/operators';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DashboardComponent implements OnInit, OnDestroy {
  inverter: InverterStatus | null = null;
  solax: MetricsResult | null = null;
  battery: MetricsResult | null = null;

  loading = true;
  lastUpdated: Date | null = null;

  private sub?: Subscription;

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    // Poll every 10 seconds
    this.sub = interval(10000).pipe(startWith(0)).subscribe(() => this.fetchAll());
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  fetchAll(): void {
    this.api.getInverterStatus().subscribe({
      next: (d) => {
        this.inverter = d;
        this.lastUpdated = new Date();
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => { this.loading = false; this.cdr.markForCheck(); },
    });
    this.api.getSolaxMetrics().subscribe({
      next: (d) => { this.solax = d; this.cdr.markForCheck(); },
    });
    this.api.getBatteryMetrics().subscribe({
      next: (d) => { this.battery = d; this.cdr.markForCheck(); },
    });
  }

  /** Get a single scalar metric value from a metrics result. */
  getMetric(result: MetricsResult | null, name: string, labels?: Record<string, string>): number | null {
    if (!result?.metrics?.[name]) return null;
    const samples = result.metrics[name];
    if (!labels || Object.keys(labels).length === 0) return samples[0]?.value ?? null;
    const match = samples.find(s => Object.entries(labels).every(([k, v]) => s.labels[k] === v));
    return match?.value ?? null;
  }

  socColor(soc: number | undefined | null): string {
    if (soc == null) return 'bar-orange';
    if (soc >= 60) return 'bar-green';
    if (soc >= 25) return 'bar-orange';
    return 'bar-red';
  }

  loadColor(pct: number | undefined | null): string {
    if (pct == null) return 'bar-green';
    if (pct < 70) return 'bar-green';
    if (pct < 90) return 'bar-orange';
    return 'bar-red';
  }

  formatFeedin(v: number | null): string {
    if (v == null) return '–';
    if (v > 0) return `+${v.toFixed(0)} W (export)`;
    return `${v.toFixed(0)} W (import)`;
  }

  feedinClass(v: number | null): string {
    if (v == null) return '';
    return v > 0 ? 'badge-success' : 'badge-warning';
  }

  formatVal(v: number | null | undefined, unit = '', decimals = 1): string {
    if (v == null || v === undefined) return '–';
    return `${v.toFixed(decimals)} ${unit}`.trim();
  }
}
