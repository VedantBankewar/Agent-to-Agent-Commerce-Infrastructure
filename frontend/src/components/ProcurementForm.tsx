import { useState } from 'react';

export interface ProcurementFormData {
  item: string;
  category: string;
  quantity: number;
  budget_usd: number;
  deadline: string;
  target_price_usd: number | null;
  min_warranty_yrs: number;
  priority: string;
  requirements: string;
}

interface ProcurementFormProps {
  onSubmit: (data: ProcurementFormData) => void;
  disabled?: boolean;
}

const CATEGORIES = [
  { value: 'furniture', label: 'Furniture' },
  { value: 'office_supplies', label: 'Office Supplies' },
  { value: 'electronics', label: 'Electronics' },
  { value: 'general', label: 'General' },
];

const PRIORITIES = [
  { value: 'cost', label: 'Cost', desc: 'Minimize total cost' },
  { value: 'speed', label: 'Speed', desc: 'Fastest delivery' },
  { value: 'quality', label: 'Quality', desc: 'Best rating & warranty' },
  { value: 'balanced', label: 'Balanced', desc: 'Optimize all factors' },
];

const WARRANTIES = [
  { value: 1, label: '1 year' },
  { value: 2, label: '2 years' },
  { value: 3, label: '3 years' },
  { value: 5, label: '5 years' },
];

const PRESETS: { label: string; data: Partial<ProcurementFormData> }[] = [
  {
    label: '50 Office Chairs',
    data: {
      item: 'Ergonomic Office Chair',
      category: 'furniture',
      quantity: 50,
      budget_usd: 15000,
      target_price_usd: 250,
      min_warranty_yrs: 2,
      priority: 'balanced',
    },
  },
  {
    label: '100 Pens',
    data: {
      item: 'Ballpoint Pen',
      category: 'office_supplies',
      quantity: 100,
      budget_usd: 500,
      target_price_usd: 3,
      min_warranty_yrs: 1,
      priority: 'cost',
    },
  },
  {
    label: '10 Standing Desks',
    data: {
      item: 'Standing Desk',
      category: 'furniture',
      quantity: 10,
      budget_usd: 8000,
      target_price_usd: 700,
      min_warranty_yrs: 3,
      priority: 'quality',
    },
  },
];

function getDefaultDeadline(): string {
  const d = new Date();
  d.setDate(d.getDate() + 30);
  return d.toISOString().split('T')[0];
}

export default function ProcurementForm({ onSubmit, disabled }: ProcurementFormProps) {
  const [item, setItem] = useState('');
  const [category, setCategory] = useState('furniture');
  const [quantity, setQuantity] = useState<number | ''>('');
  const [budgetUsd, setBudgetUsd] = useState<number | ''>('');
  const [deadline, setDeadline] = useState(getDefaultDeadline());
  const [targetPrice, setTargetPrice] = useState<number | ''>('');
  const [minWarranty, setMinWarranty] = useState(1);
  const [priority, setPriority] = useState('balanced');
  const [requirements, setRequirements] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const isValid = item.trim() && quantity && budgetUsd && deadline;

  const handleSubmit = () => {
    if (!isValid) return;
    onSubmit({
      item: item.trim(),
      category,
      quantity: Number(quantity),
      budget_usd: Number(budgetUsd),
      deadline,
      target_price_usd: targetPrice ? Number(targetPrice) : null,
      min_warranty_yrs: minWarranty,
      priority,
      requirements: requirements.trim(),
    });
  };

  const applyPreset = (preset: typeof PRESETS[number]) => {
    const d = preset.data;
    if (d.item) setItem(d.item);
    if (d.category) setCategory(d.category);
    if (d.quantity) setQuantity(d.quantity);
    if (d.budget_usd) setBudgetUsd(d.budget_usd);
    if (d.target_price_usd) setTargetPrice(d.target_price_usd);
    if (d.min_warranty_yrs) setMinWarranty(d.min_warranty_yrs);
    if (d.priority) setPriority(d.priority);
    setDeadline(getDefaultDeadline());
    setShowAdvanced(true);
  };

  const inputClass =
    'w-full bg-[#111111] border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-on-surface-variant/40 font-body outline-none text-sm focus:border-primary/50 transition-colors disabled:opacity-50';
  const labelClass = 'text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/60 mb-1.5 block';

  return (
    <div className="flex flex-col gap-5">
      {/* Required Fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className={labelClass}>Product Name</label>
          <input
            type="text"
            value={item}
            onChange={(e) => setItem(e.target.value)}
            placeholder="Ergonomic Office Chair"
            className={inputClass}
            disabled={disabled}
          />
        </div>
        <div>
          <label className={labelClass}>Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className={inputClass}
            disabled={disabled}
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass}>Quantity</label>
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value ? parseInt(e.target.value) : '')}
            placeholder="50"
            min={1}
            className={inputClass}
            disabled={disabled}
          />
        </div>
        <div>
          <label className={labelClass}>Max Budget (USD)</label>
          <div className="relative">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/50 text-sm">$</span>
            <input
              type="number"
              value={budgetUsd}
              onChange={(e) => setBudgetUsd(e.target.value ? parseFloat(e.target.value) : '')}
              placeholder="15,000"
              min={0}
              step={100}
              className={`${inputClass} pl-8`}
              disabled={disabled}
            />
          </div>
        </div>
        <div>
          <label className={labelClass}>Delivery Deadline</label>
          <input
            type="date"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            className={inputClass}
            disabled={disabled}
          />
        </div>
      </div>

      {/* Advanced Options Toggle */}
      <button
        type="button"
        onClick={() => setShowAdvanced(!showAdvanced)}
        className="flex items-center gap-2 text-xs text-on-surface-variant/60 hover:text-on-surface-variant transition-colors self-start"
        disabled={disabled}
      >
        <span className="material-symbols-outlined text-[14px]">
          {showAdvanced ? 'expand_less' : 'expand_more'}
        </span>
        Advanced Options
      </button>

      {/* Advanced Fields */}
      {showAdvanced && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-white/[0.02] border border-white/5 rounded-xl p-4 animate-in fade-in slide-in-from-top-2 duration-300">
          <div>
            <label className={labelClass}>Target Price/Unit (USD, optional)</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant/50 text-sm">$</span>
              <input
                type="number"
                value={targetPrice}
                onChange={(e) => setTargetPrice(e.target.value ? parseFloat(e.target.value) : '')}
                placeholder="Agent discovers market rate"
                min={0}
                step={1}
                className={`${inputClass} pl-8`}
                disabled={disabled}
              />
            </div>
          </div>
          <div>
            <label className={labelClass}>Minimum Warranty</label>
            <select
              value={minWarranty}
              onChange={(e) => setMinWarranty(Number(e.target.value))}
              className={inputClass}
              disabled={disabled}
            >
              {WARRANTIES.map((w) => (
                <option key={w.value} value={w.value}>{w.label}</option>
              ))}
            </select>
          </div>
          <div className="md:col-span-2">
            <label className={labelClass}>Priority</label>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {PRIORITIES.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setPriority(p.value)}
                  disabled={disabled}
                  className={`flex flex-col items-center gap-1 px-3 py-3 rounded-xl border text-xs transition-all ${
                    priority === p.value
                      ? 'bg-primary/10 border-primary/40 text-primary'
                      : 'bg-[#111111] border-white/5 text-on-surface-variant hover:border-white/20'
                  }`}
                >
                  <span className="font-bold uppercase tracking-wider text-[10px]">{p.label}</span>
                  <span className="text-[9px] opacity-70">{p.desc}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="md:col-span-2">
            <label className={labelClass}>Special Requirements (optional)</label>
            <textarea
              value={requirements}
              onChange={(e) => setRequirements(e.target.value)}
              placeholder="BIFMA certified, adjustable lumbar support..."
              rows={2}
              className={`${inputClass} resize-none`}
              disabled={disabled}
            />
          </div>
        </div>
      )}

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={disabled || !isValid}
        className={`w-full px-8 py-4 rounded-xl font-bold flex items-center justify-center gap-2 transition-all text-sm ${
          disabled || !isValid
            ? 'bg-outline-variant text-white/50 cursor-not-allowed'
            : 'bg-gradient-to-r from-primary-container to-primary text-white hover:opacity-90 shadow-[0_0_20px_rgba(249,171,255,0.3)] active:scale-95'
        }`}
      >
        <span className="material-symbols-outlined text-sm">
          {disabled ? 'hourglass_empty' : 'rocket_launch'}
        </span>
        <span>{disabled ? 'Agent Running...' : 'Deploy Procurement Agent'}</span>
      </button>

      {/* Presets */}
      <div className="flex flex-wrap gap-2">
        <span className="text-[10px] text-on-surface-variant/40 uppercase tracking-wider self-center mr-1">Quick Presets:</span>
        {PRESETS.map((preset, idx) => (
          <button
            key={idx}
            onClick={() => applyPreset(preset)}
            className="bg-surface-container-highest/20 border border-outline-variant/10 px-4 py-2 rounded-full text-xs text-on-surface-variant/80 hover:bg-surface-container-highest/40 transition-colors"
            disabled={disabled}
          >
            {preset.label}
          </button>
        ))}
      </div>
    </div>
  );
}
