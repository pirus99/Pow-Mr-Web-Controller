import { Component, OnInit, ChangeDetectorRef, ChangeDetectionStrategy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, InverterOptions, InverterStatus } from '../../services/api';

@Component({
  selector: 'app-inverter-control',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './inverter-control.html',
  styleUrl: './inverter-control.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InverterControlComponent implements OnInit {
  status: InverterStatus | null = null;
  options: InverterOptions | null = null;

  selectedOutputPriority: number | null = null;
  selectedChargerPriority: number | null = null;
  selectedUtilityChargeCurrent: number | null = null;

  customRegister = '';
  customValue: number | null = null;

  saving = false;
  message = '';
  messageType: 'success' | 'error' = 'success';

  constructor(private api: ApiService, private cdr: ChangeDetectorRef) {}

  ngOnInit(): void {
    this.api.getInverterStatus().subscribe({
      next: (s) => {
        this.status = s;
        this.selectedOutputPriority = s.output_source_priority ?? null;
        this.selectedChargerPriority = s.charger_source_priority ?? null;
        this.selectedUtilityChargeCurrent = s.max_utility_charge_current ?? null;
        this.cdr.markForCheck();
      },
    });
    this.api.getInverterOptions().subscribe({
      next: (o) => { this.options = o; this.cdr.markForCheck(); },
    });
  }

  setRegister(register: string, value: number | null): void {
    if (value === null || value === undefined) return;
    this.saving = true;
    this.message = '';
    this.api.writeRegister(register, value).subscribe({
      next: () => {
        this.message = `✔ ${register} set to ${value}`;
        this.messageType = 'success';
        this.saving = false;
        this.api.getInverterStatus().subscribe({
          next: (s) => { this.status = s; this.cdr.markForCheck(); },
        });
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.message = `✖ Error: ${err?.error?.error || 'Unknown error'}`;
        this.messageType = 'error';
        this.saving = false;
        this.cdr.markForCheck();
      },
    });
  }

  writeCustom(): void {
    if (!this.customRegister || this.customValue === null) return;
    this.setRegister(this.customRegister, this.customValue);
  }
}
