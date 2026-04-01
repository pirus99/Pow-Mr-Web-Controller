import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface InverterStatus {
  connected: boolean;
  error?: string;
  ac_voltage?: number;
  ac_frequency?: number;
  pv_voltage?: number;
  battery_voltage?: number;
  battery_soc?: number;
  battery_charge_current?: number;
  battery_discharge_current?: number;
  load_voltage?: number;
  load_frequency?: number;
  load_power?: number;
  load_va?: number;
  load_percent?: number;
  output_source_priority?: number;
  output_source_priority_label?: string;
  charger_source_priority?: number;
  charger_source_priority_label?: string;
  max_utility_charge_current?: number;
  max_total_charge_current?: number;
  on_battery?: boolean;
  ac_active?: boolean;
  load_enabled?: boolean;
  charger_status?: number;
  charger_status_label?: string;
  temperature?: number;
  bulk_charging_voltage?: number;
  floating_charging_voltage?: number;
  low_cutoff_voltage?: number;
  back_to_utility_voltage?: number;
  back_to_battery_voltage?: number;
}

export interface MetricSample {
  labels: Record<string, string>;
  value: number;
}

export interface MetricsResult {
  last_scraped?: number;
  error?: string;
  metrics: Record<string, MetricSample[]>;
}

export interface InverterOptions {
  output_source_priority: { value: number; label: string }[];
  charger_source_priority: { value: number; label: string }[];
  utility_charge_current: number[];
  registers: string[];
}

export interface AutomationRule {
  id?: number;
  name: string;
  description?: string;
  enabled: boolean;
  metric_source: 'solax' | 'battery' | 'powmr';
  metric_name: string;
  metric_labels: Record<string, string>;
  operator: string;
  threshold: number;
  duration_seconds: number;
  action_register: string;
  action_value: number;
  reset_register?: string;
  reset_value?: number;
  reset_duration_seconds: number;
  last_triggered?: string;
  last_reset?: string;
  created_at?: string;
  updated_at?: string;
}

export interface AutomationLog {
  id: number;
  rule: number;
  rule_name: string;
  timestamp: string;
  action: string;
  message: string;
  metric_value?: number;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  getInverterStatus(): Observable<InverterStatus> {
    return this.http.get<InverterStatus>(`${this.base}/api/inverter/status/`);
  }

  getInverterOptions(): Observable<InverterOptions> {
    return this.http.get<InverterOptions>(`${this.base}/api/inverter/options/`);
  }

  writeRegister(register: string, value: number): Observable<any> {
    return this.http.post(`${this.base}/api/inverter/control/`, { register, value });
  }

  getSolaxMetrics(): Observable<MetricsResult> {
    return this.http.get<MetricsResult>(`${this.base}/api/metrics/solax/`);
  }

  getBatteryMetrics(): Observable<MetricsResult> {
    return this.http.get<MetricsResult>(`${this.base}/api/metrics/battery/`);
  }

  getRules(): Observable<AutomationRule[]> {
    return this.http.get<AutomationRule[]>(`${this.base}/api/automation/rules/`);
  }

  createRule(rule: AutomationRule): Observable<AutomationRule> {
    return this.http.post<AutomationRule>(`${this.base}/api/automation/rules/`, rule);
  }

  updateRule(id: number, rule: AutomationRule): Observable<AutomationRule> {
    return this.http.put<AutomationRule>(`${this.base}/api/automation/rules/${id}/`, rule);
  }

  deleteRule(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/api/automation/rules/${id}/`);
  }

  toggleRule(id: number): Observable<{ id: number; enabled: boolean }> {
    return this.http.post<{ id: number; enabled: boolean }>(
      `${this.base}/api/automation/rules/${id}/toggle/`, {}
    );
  }

  getLogs(ruleId?: number): Observable<AutomationLog[]> {
    const params = ruleId ? `?rule=${ruleId}` : '';
    return this.http.get<AutomationLog[]>(`${this.base}/api/automation/logs/${params}`);
  }
}
