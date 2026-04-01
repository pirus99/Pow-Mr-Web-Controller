import { Component, OnInit, ChangeDetectorRef, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, AutomationRule, AutomationLog } from '../../services/api';

@Component({
  selector: 'app-automation',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './automation.html',
  styleUrl: './automation.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AutomationComponent implements OnInit {
  rules: AutomationRule[] = [];
  logs: AutomationLog[] = [];

  showForm = false;
  editingRule: AutomationRule | null = null;

  saving = false;
  message = '';
  messageType: 'success' | 'error' = 'success';

  form: AutomationRule = this.emptyRule();

  operators = ['>', '>=', '<', '<=', '==', '!='];
  sources = [
    { value: 'solax', label: 'Solax Inverter' },
    { value: 'battery', label: 'Battery BMS' },
    { value: 'powmr', label: 'PowMr Inverter' },
  ];

  registers = [
    'output_source_priority', 'charger_source_priority',
    'utility_charge_current', 'max_total_charge_current',
    'buzzer_alarm', 'overload_bypass', 'beep_on_primary_fail',
    'comeback_utility_voltage', 'comeback_battery_voltage',
  ];

  metricHints: Record<string, string[]> = {
    solax: ['solax_feedin_power_watts', 'solax_grid_power_watts', 'solax_pv1_power_watts',
            'solax_inverter_status', 'solax_daily_energy_kwh'],
    battery: ['daly_bms_soc_percent', 'daly_bms_pack_voltage_volts',
              'daly_bms_pack_current_amperes', 'daly_bms_temperature_max_celsius'],
    powmr: ['battery_soc', 'battery_voltage', 'load_power', 'pv_voltage'],
  };

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.loadRules();
    this.loadLogs();
  }

  loadRules(): void {
    this.api.getRules().subscribe({
      next: (r) => { this.rules = r; this.cdr.markForCheck(); },
    });
  }

  loadLogs(): void {
    this.api.getLogs().subscribe({
      next: (l) => { this.logs = l; this.cdr.markForCheck(); },
    });
  }

  emptyRule(): AutomationRule {
    return {
      name: '',
      description: '',
      enabled: true,
      metric_source: 'solax',
      metric_name: '',
      metric_labels: {},
      operator: '>',
      threshold: 0,
      duration_seconds: 60,
      action_register: 'output_source_priority',
      action_value: 0,
      reset_register: '',
      reset_value: undefined,
      reset_duration_seconds: 60,
    };
  }

  openCreate(): void {
    this.form = this.emptyRule();
    this.editingRule = null;
    this.showForm = true;
    this.message = '';
  }

  openEdit(rule: AutomationRule): void {
    this.form = { ...rule, metric_labels: { ...rule.metric_labels } };
    this.editingRule = rule;
    this.showForm = true;
    this.message = '';
  }

  cancelForm(): void {
    this.showForm = false;
    this.editingRule = null;
  }

  saveRule(): void {
    this.saving = true;
    const obs = this.editingRule?.id
      ? this.api.updateRule(this.editingRule.id, this.form)
      : this.api.createRule(this.form);

    obs.subscribe({
      next: () => {
        this.message = `✔ Rule "${this.form.name}" saved`;
        this.messageType = 'success';
        this.saving = false;
        this.showForm = false;
        this.loadRules();
        this.loadLogs();
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.message = `✖ Error: ${JSON.stringify(err?.error || 'Unknown error')}`;
        this.messageType = 'error';
        this.saving = false;
        this.cdr.markForCheck();
      },
    });
  }

  deleteRule(rule: AutomationRule): void {
    if (!confirm(`Delete rule "${rule.name}"?`)) return;
    this.api.deleteRule(rule.id!).subscribe({
      next: () => { this.loadRules(); this.loadLogs(); },
    });
  }

  toggleRule(rule: AutomationRule): void {
    this.api.toggleRule(rule.id!).subscribe({
      next: (r) => {
        rule.enabled = r.enabled;
        this.cdr.markForCheck();
      },
    });
  }

  get currentHints(): string[] {
    return this.metricHints[this.form.metric_source] || [];
  }

  labelJson(labels: Record<string, string>): string {
    if (!labels || Object.keys(labels).length === 0) return '(any)';
    return JSON.stringify(labels);
  }

  logActionClass(action: string): string {
    if (action === 'triggered') return 'badge-success';
    if (action === 'reset') return 'badge-info';
    return 'badge-danger';
  }

  objectKeys = Object.keys;

  tryParseJson(str: string): Record<string, string> {
    try {
      return JSON.parse(str) || {};
    } catch {
      return {};
    }
  }
}
