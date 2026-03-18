import * as React from 'react';
import { useState, useEffect, useMemo, useRef } from 'react';
import * as ReactDOM from 'react-dom';
import { api } from '../lib/api';
import { Reservation, ReservationCreate, ReservationItem, MenuItem } from '../types';
import {
  User,
  CalendarDays,
  Clock,
  Wine,
  Plus,
  Minus,
  Bold,
  Italic,
  Palette,
  Trash2,
  MessageSquare,
  CheckCircle2,
  Circle,
  X,
} from 'lucide-react';

const TIME_PRESETS = ['12:00', '12:30', '13:00', '13:30', '19:30', '20:00']

const DRINKS = [
  'sans alcool',
  'avec alcool',
  'sans alcool + cava',
  'avec alcool + cava',
  'sans alcool + champ',
  'avec alcool + champ',
  'à la carte',
  'sans Formule',
]

type AllergenOption = { key: string; label: string; icon_url?: string; has_icon?: boolean }
const DEFAULT_ALLERGENS: AllergenOption[] = [
  { key: 'gluten', label: 'Gluten' },
  { key: 'crustaces', label: 'Crustacés' },
  { key: 'oeufs', label: 'Œufs' },
  { key: 'poisson', label: 'Poisson' },
  { key: 'arachides', label: 'Arachides' },
  { key: 'soja', label: 'Soja' },
  { key: 'lait', label: 'Lait' },
  { key: 'fruits_a_coque', label: 'Fruits à coque' },
  { key: 'celeri', label: 'Céleri' },
  { key: 'moutarde', label: 'Moutarde' },
  { key: 'sesame', label: 'Sésame' },
  { key: 'sulfites', label: 'Sulfites' },
  { key: 'lupin', label: 'Lupin' },
  { key: 'mollusques', label: 'Mollusques' },
]

function PaxBadge({ label, count, pax }: { label: string; count: number; pax: number }) {
  const cls =
    count === 0
      ? 'bg-gray-100 text-gray-500'
      : count <= pax
      ? 'bg-green-100 text-green-700'
      : 'bg-red-100 text-red-700';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {label}: <b>{count}</b>/{pax}
    </span>
  );
}

type Props = {
  initial?: Partial<Reservation>
  onSubmit: (payload: Partial<ReservationCreate>) => Promise<void>
  formId?: string
  onOpenBilling?: () => void
  navActions?: React.ReactNode
}

export default function ReservationForm({ initial, onSubmit, formId, onOpenBilling, navActions }: Props) {
  const [client_name, setClient] = useState(initial?.client_name || '')
  const [service_date, setDate] = useState(initial?.service_date || '')
  const [arrival_time, setTime] = useState(initial?.arrival_time || '')
  const [pax, setPax] = useState(initial?.pax || 2)
  const [drink_formula, setDrink] = useState(initial?.drink_formula || DRINKS[0])
  const [notes, setNotes] = useState(initial?.notes || '')
  const [status, setStatus] = useState<Reservation['status']>(initial?.status || 'draft')
  const [finalVersion, setFinalVersion] = useState<boolean>(Boolean(initial?.final_version))
  const [onInvoice, setOnInvoice] = useState<boolean>(Boolean((initial as any)?.on_invoice))
  const [allergens, setAllergens] = useState<string[]>(initial?.allergens ? String(initial.allergens).split(',').map(s=>s.trim()).filter(Boolean) : [])
  const [items, setItems] = useState<ReservationItem[]>(initial?.items || [])
  const [openRow, setOpenRow] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [errs, setErrs] = useState<{client?:string,date?:string,pax?:string,time?:string}>({})
  const [itemsError, setItemsError] = useState<string | null>(null)
  const [allergenOptions, setAllergenOptions] = useState<AllergenOption[]>(DEFAULT_ALLERGENS)
  const [allergenQuery, setAllergenQuery] = useState('')

  const [pickerOpen, setPickerOpen] = useState(false)
  const [pickerItems, setPickerItems] = useState<MenuItem[]>([])
  const [pickerQ, setPickerQ] = useState('')
  const [pickerTypeFilter, setPickerTypeFilter] = useState<'all' | 'entrée' | 'plat' | 'dessert'>('all')

  const clientNameRef = useRef<HTMLInputElement>(null)

  const totalsByType = useMemo(() => {
    const effective = items.filter(it => (it.name || '').trim() !== '' || (it.quantity || 0) > 0)
    const t: Record<'entrée' | 'plat' | 'dessert', number> = { 'entrée': 0, 'plat': 0, 'dessert': 0 }
    for (const it of effective) {
      const k = (it.type || '').toLowerCase()
      const isEntree = k.startsWith('entrée') || k.startsWith('entree')
      if (isEntree) t['entrée'] += Number(it.quantity || 0)
      else if (k === 'plat') t['plat'] += Number(it.quantity || 0)
      else if (k === 'dessert') t['dessert'] += Number(it.quantity || 0)
    }
    return { entree: t['entrée'], plat: t['plat'], dessert: t['dessert'] }
  }, [items])

  const filteredPicker = useMemo(() => {
    const ql = pickerQ.trim().toLowerCase()
    return pickerItems.filter(it => {
      if (pickerTypeFilter !== 'all' && it.type !== pickerTypeFilter) return false
      if (ql && !it.name.toLowerCase().includes(ql)) return false
      return true
    })
  }, [pickerItems, pickerQ, pickerTypeFilter])

  const filteredAllergens = useMemo(() => {
    const ql = allergenQuery.trim().toLowerCase();
    const arr = [...allergenOptions];
    arr.sort((a, b) => {
      const ai = allergens.includes(a.key) ? 0 : 1;
      const bi = allergens.includes(b.key) ? 0 : 1;
      if (ai !== bi) return ai - bi;
      return String(a.label || a.key).localeCompare(String(b.label || b.key));
    });
    return arr.filter(a => !ql || a.key.toLowerCase().includes(ql) || String(a.label || '').toLowerCase().includes(ql));
  }, [allergenOptions, allergens, allergenQuery]);

  const isDirty = useMemo(() => {
    if (!initial?.id) return true
    if (client_name !== (initial.client_name || '')) return true
    if (service_date !== (initial.service_date || '')) return true
    if (arrival_time !== (initial.arrival_time || '')) return true
    if (pax !== (initial.pax || 2)) return true
    if (drink_formula !== (initial.drink_formula || DRINKS[0])) return true
    if (notes !== (initial.notes || '')) return true
    if (status !== (initial.status || 'draft')) return true
    if (finalVersion !== Boolean(initial.final_version)) return true
    if (onInvoice !== Boolean((initial as any).on_invoice)) return true
    const initAllergens = initial.allergens ? String(initial.allergens).split(',').map(s => s.trim()).filter(Boolean) : []
    if (allergens.slice().sort().join(',') !== initAllergens.slice().sort().join(',')) return true
    return false
  }, [client_name, service_date, arrival_time, pax, drink_formula, notes, status, finalVersion, onInvoice, allergens, initial])

  // Fonction pour formater le texte sélectionné
  const formatText = (prefix: string, suffix: string, title: string, showColorPicker = false) => {
    return (e: React.MouseEvent<HTMLButtonElement>) => {
      e.preventDefault();
      const textarea = document.querySelector('textarea[name="notes"]') as HTMLTextAreaElement;
      if (!textarea) return;
      
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      const selectedText = notes.substring(start, end);
      const before = notes.substring(0, start);
      const after = notes.substring(end);
      
      if (showColorPicker) {
        const colorPicker = document.createElement('input');
        colorPicker.type = 'color';
        colorPicker.onchange = (e) => {
          const color = (e.target as HTMLInputElement).value;
          if (selectedText) {
            setNotes(`${before}[color=${color}]${selectedText}[/color]${after}`);
            setTimeout(() => {
              textarea.focus();
              textarea.setSelectionRange(start, end + 15 + color.length);
            }, 0);
          } else {
            const newPosition = start + `[color=${color}][/color]`.length;
            setNotes(`${before}[color=${color}][/color]${after}`);
            setTimeout(() => {
              textarea.focus();
              textarea.setSelectionRange(newPosition - 8, newPosition - 8);
            }, 0);
          }
        };
        colorPicker.click();
      } else {
        setNotes(`${before}${prefix}${selectedText}${suffix}${after}`);
        setTimeout(() => {
          textarea.focus();
          if (selectedText) {
            textarea.setSelectionRange(start, end + prefix.length + suffix.length);
          } else {
            textarea.setSelectionRange(start + prefix.length, start + prefix.length);
          }
        }, 0);
      }
    };
  };
  
  // Fonction pour échapper les caractères HTML
  const escapeHtml = (unsafe: string) => {
    if (!unsafe) return '';
    return unsafe
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  };

  // Fonction pour prévisualiser le formatage
  const formatPreview = (text: string) => {
    if (!text) return '';
    // Échapper HTML pour éviter les injections
    let html = escapeHtml(text);
    // Remplacements itératifs pour supporter l'imbrication simple
    // Couleur
    let prev: string;
    do {
      prev = html;
      html = html.replace(/\[color=([^\]]+)\]([\s\S]*?)\[\/color\]/g, (_m, color, inner) => {
        return `<span style="color:${color}">${inner}</span>`;
      });
    } while (html !== prev);
    // Autres formats
    html = html
      .replace(/\*\*([^*]+)\*\*|\*([^*]+)\*/g, (_m, p1, p2) => `<strong>${p1 || p2}</strong>`)
      .replace(/_([^_]+)_/g, '<em>$1</em>')
      .replace(/\n-\s+/g, '<br/>• ')
      .replace(/\n/g, '<br/>')
      .replace(/&amp;(?=#?\w+;)/g, '&');
    return html;
  };

  useEffect(() => {
    if (!initial?.id) clientNameRef.current?.focus()
  }, [])

  // Sync when initial changes (e.g., when loading an existing reservation)
  useEffect(() => {
    if (!initial) return;
    setClient(initial.client_name || '');
    setDate(initial.service_date || '');
    setTime(initial.arrival_time || '');
    setPax(initial.pax || 2);
    setDrink(initial.drink_formula || DRINKS[0]);
    setNotes(initial.notes || '');
    setStatus(initial.status || 'draft');
    setItems(initial.items || []);
    setFinalVersion(Boolean(initial.final_version));
    setOnInvoice(Boolean((initial as any).on_invoice));
    setAllergens(initial.allergens ? String(initial.allergens).split(',').map(s=>s.trim()).filter(Boolean) : []);
  }, [initial]);

  useEffect(() => {
    if (!items.length) {
      setItems([
        { type: 'entrée', name: '', quantity: 0 },
        { type: 'plat', name: '', quantity: 0 },
        { type: 'dessert', name: '', quantity: 0 },
      ])
    }
  }, [])

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const res = await api.get('/api/allergens')
        const fromApi: AllergenOption[] = Array.isArray(res.data) ? res.data : []
        const byKey: Record<string, AllergenOption> = {}
        DEFAULT_ALLERGENS.forEach(a => { byKey[a.key] = a })
        fromApi.forEach(a => { byKey[a.key] = { ...(byKey[a.key] || {}), ...a } })
        const merged = Object.values(byKey)
        allergens.forEach(k => { if (!merged.find(a => a.key === k)) merged.push({ key: k, label: k }) })
        if (mounted) setAllergenOptions(merged)
      } catch {}
    })()
    return () => { mounted = false }
  }, [])

  const updateItem = (idx: number, patch: Partial<ReservationItem>) => {
    setItems(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  };

  const addItem = () => {
    setItems(prev => {
      const next = [...prev, { name: '', type: 'entrée', quantity: 1 }];
      setOpenRow(next.length - 1);
      return next;
    });
  };

  async function loadPicker() {
    const res = await api.get('/api/menu-items')
    const arr: MenuItem[] = Array.isArray(res.data) ? res.data : []
    setPickerItems(arr.filter(it => it.active))
  }

  const openPicker = async () => {
    if (!pickerOpen) await loadPicker()
    setPickerOpen(true)
  }

  function addFromPicker(it: MenuItem) {
    setItems(prev => {
      const next = [...prev]
      const idx = next.findIndex(x => (String(x.type).toLowerCase() === String(it.type).toLowerCase()) && String(x.name).trim().toLowerCase() === String(it.name).trim().toLowerCase())
      if (idx >= 0) {
        const q = Number(next[idx].quantity || 0) + 1
        next[idx] = { ...next[idx], quantity: q }
        setOpenRow(idx)
      } else {
        next.push({ type: it.type, name: it.name, quantity: 1 })
        setOpenRow(next.length - 1)
      }
      return next
    })
  }

  function validate(): boolean {
    const errs: {client?:string,date?:string,pax?:string,time?:string} = {};
    if (!client_name.trim()) errs.client = 'Le nom du client est requis';
    if (!service_date) errs.date = 'La date est requise';
    if (!arrival_time) errs.time = "L'heure d'arrivée est requise";
    if (pax < 1) errs.pax = 'Le nombre de personnes doit être supérieur à 0';
    
    setErrs(errs);
    
    // Vérifier les erreurs sur les articles (ignorer les lignes vides)
    const effective = items.filter(it => (it.name || '').trim() !== '' || (it.quantity || 0) > 0);
    if (effective.length === 0) {
      setItemsError('Veuillez ajouter au moins un plat');
      return false;
    }
    // Pour chaque ligne non vide: exiger nom et quantité > 0
    if (effective.some(item => !(item.name || '').trim())) {
      setItemsError('Chaque plat renseigné doit avoir un nom');
      return false;
    }
    if (effective.some(item => (item.quantity || 0) < 1)) {
      setItemsError('Chaque plat renseigné doit avoir une quantité > 0');
      return false;
    }
    // Garde-fou: les totaux par type ne doivent pas dépasser le nombre de couverts (pax)
    const totals: Record<string, number> = { 'entrée': 0, 'plat': 0, 'dessert': 0 };
    for (const it of effective) {
      const t = (it.type || '').toLowerCase();
      const isEntree = t.startsWith('entrée') || t.startsWith('entree');
      if (isEntree) totals['entrée'] += Number(it.quantity || 0);
      else if (t === 'plat') totals['plat'] += Number(it.quantity || 0);
      else if (t === 'dessert') totals['dessert'] += Number(it.quantity || 0);
    }
    const offenders = Object.entries(totals)
      .filter(([_, v]) => v > (Number(pax) || 0))
      .map(([k, v]) => `${k}=${v}`);
    if (offenders.length > 0) {
      setItemsError(`Le total par type dépasse le nombre de couverts (${pax}) : ${offenders.join(', ')}`);
      return false;
    }
    
    setItemsError(null);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    submit();
  };

  const submit = async () => {
    if (submitting) return;
    if (!validate()) return;
    setSubmitting(true);
    try {
      const d = service_date || new Date().toISOString().slice(0, 10);
      let t = arrival_time && arrival_time.length >= 4 ? arrival_time : '00:00';
      if (/^\d{2}:\d{2}$/.test(t)) t = `${t}:00`;
      const name = (client_name || '').trim() || 'Client';
      const validItems = (items || [])
        .filter((it) => (it.name || '').trim() && (it.quantity || 0) > 0)
        .map((it) => ({
          type: it.type,
          name: it.name,
          quantity: it.quantity,
          comment: (it.comment || '').trim() || undefined,
        }));
      await onSubmit({
        client_name: name,
        service_date: d,
        arrival_time: t,
        pax: Number(pax) || 1,
        drink_formula,
        notes,
        status,
        allergens: allergens.join(','),
        final_version: finalVersion,
        on_invoice: onInvoice,
        items: validItems,
      });
    } catch (error) {
      console.error('Erreur lors de la soumission:', error);
      // Afficher le message d'erreur serveur (ex: 422 garde-fou backend)
      try {
        const anyErr: any = error as any;
        const detail = anyErr?.response?.data?.detail || anyErr?.message;
        if (detail) setItemsError(String(detail));
      } catch {}
    } finally {
      setSubmitting(false);
    }
  };

  // Feedback visuel en direct si dépassement pendant la saisie
  useEffect(() => {
    // Ne pas écraser un message d'erreur différent pendant la soumission
    const effective = items.filter(it => (it.name || '').trim() !== '' || (it.quantity || 0) > 0);
    const totals: Record<string, number> = { 'entrée': 0, 'plat': 0, 'dessert': 0 };
    for (const it of effective) {
      const t = (it.type || '').toLowerCase();
      const isEntree = t.startsWith('entrée') || t.startsWith('entree');
      if (isEntree) totals['entrée'] += Number(it.quantity || 0);
      else if (t === 'plat') totals['plat'] += Number(it.quantity || 0);
      else if (t === 'dessert') totals['dessert'] += Number(it.quantity || 0);
    }
    const offenders = Object.entries(totals)
      .filter(([_, v]) => v > (Number(pax) || 0))
      .map(([k, v]) => `${k}=${v}`);
    if (offenders.length > 0) {
      setItemsError(`Le total par type dépasse le nombre de couverts (${pax}) : ${offenders.join(', ')}`);
    } else if (itemsError && itemsError.startsWith('Le total par type dépasse')) {
      // Nettoyer le message si c'était uniquement le garde-fou
      setItemsError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, pax]);

  function drinkVariantOf(label?: string): string {
    const s = (label || '').toLowerCase();
    if (!s || s === 'sans formule') return 'is-none';
    if (s === 'à la carte' || s === 'a la carte') return 'is-a-la-carte';
    if (s.includes('sans alcool') && s.includes('champ')) return 'is-na-champ';
    if (s.includes('avec alcool') && s.includes('champ')) return 'is-alcool-champ';
    if (s.includes('sans alcool') && s.includes('cava')) return 'is-na-cava';
    if (s.includes('avec alcool') && s.includes('cava')) return 'is-alcool-cava';
    if (s.includes('sans alcool')) return 'is-na';
    if (s.includes('avec alcool')) return 'is-alcool';
    return 'is-default';
  }

  function DrinkBadge({ value }: { value?: string }) {
    if (!value) return <span className="drink-badge is-none">—</span>;
    const variant = drinkVariantOf(value);
    return (
      <span className={`drink-badge ${variant}`}>
        <Wine />
        <span className="drink-text">{value}</span>
      </span>
    );
  }

  const activeAllergenOptions = allergens.map(k => allergenOptions.find(a => a.key === k) || { key: k, label: k })
  const effectiveItems = items.filter(it => (it.name || '').trim() !== '' || (it.quantity || 0) > 0)
  const completionChecks = [
    { label: 'Nom du client', ok: Boolean(client_name.trim()) },
    { label: 'Date de service', ok: Boolean(service_date) },
    { label: "Heure d'arrivée", ok: Boolean(arrival_time) },
    { label: 'Au moins un plat', ok: effectiveItems.length > 0 },
  ]

  return (
    <div className="container py-6 pb-28">
      <div className="lg:grid lg:grid-cols-[2fr_1fr] lg:gap-6 lg:items-start">

        {/* ════════════════ LEFT — form ════════════════ */}
        <div className="space-y-5">
          <form id={formId || 'reservation-form'} onSubmit={handleSubmit} className="space-y-5">

            {/* ── Card 1 : Informations ── */}
            <div className="card">
              <div className="card-header">
                <h2 className="text-lg font-medium">Informations</h2>
              </div>
              <div className="card-body space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

                  {/* Nom du client */}
                  <div className="form-group">
                    <label className="label label-required">Nom du client</label>
                    <div className="input-group">
                      <span className="input-group-text"><User className="w-4 h-4 text-gray-500" /></span>
                      <input
                        ref={clientNameRef}
                        className="input"
                        value={client_name}
                        onChange={e => setClient(e.target.value)}
                        placeholder="Nom du client"
                        required
                      />
                    </div>
                    {errs.client && <div className="text-red-500 text-sm mt-1">{errs.client}</div>}
                  </div>

                  {/* Date */}
                  <div className="form-group">
                    <label className="label label-required">Date de service</label>
                    <div className="input-group">
                      <span className="input-group-text"><CalendarDays className="w-4 h-4 text-gray-500" /></span>
                      <input type="date" className="input" value={service_date} onChange={e => setDate(e.target.value)} required />
                    </div>
                    {errs.date && <div className="text-red-500 text-sm mt-1">{errs.date}</div>}
                  </div>

                  {/* Heure + raccourcis */}
                  <div className="form-group">
                    <label className="label label-required">Heure d'arrivée</label>
                    <div className="input-group">
                      <span className="input-group-text"><Clock className="w-4 h-4 text-gray-500" /></span>
                      <input type="time" className="input" value={arrival_time} onChange={e => setTime(e.target.value)} required />
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {TIME_PRESETS.map(t => (
                        <button
                          key={t}
                          type="button"
                          className={`px-2 py-0.5 rounded text-xs border transition-colors ${arrival_time === t ? 'bg-primary text-white border-primary' : 'bg-gray-50 text-gray-600 border-gray-200 hover:bg-gray-100'}`}
                          onClick={() => setTime(t)}
                        >{t}</button>
                      ))}
                    </div>
                    {errs.time && <div className="text-red-500 text-sm mt-1">{errs.time}</div>}
                  </div>

                  {/* Couverts */}
                  <div className="form-group">
                    <label className="label label-required">Couverts</label>
                    <div className="flex items-center">
                      <button type="button" className="btn btn-outline rounded-r-none px-3 border-r-0" onClick={() => setPax(p => Math.max(1, p - 1))} aria-label="Réduire">
                        <Minus className="w-4 h-4" />
                      </button>
                      <input type="number" min="1" className="input text-center rounded-none flex-1" value={pax} onChange={e => setPax(Math.max(1, Number(e.target.value)))} required />
                      <button type="button" className="btn btn-outline rounded-l-none px-3 border-l-0" onClick={() => setPax(p => p + 1)} aria-label="Augmenter">
                        <Plus className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* ── Formule boisson — chips visuels ── */}
                  <div className="form-group md:col-span-2">
                    <label className="label flex items-center gap-1.5">
                      <Wine className="w-4 h-4 text-gray-500" /> Formule boisson
                    </label>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
                      {DRINKS.map(d => (
                        <button
                          key={d}
                          type="button"
                          className={`drink-chip ${drink_formula === d ? 'is-active' : ''}`}
                          onClick={() => setDrink(d)}
                        >{d}</button>
                      ))}
                    </div>
                  </div>

                  {/* ── Statut — contrôle segmenté ── */}
                  <div className="form-group">
                    <label className="label">Statut</label>
                    <div className="flex rounded-lg overflow-hidden border border-gray-200 text-sm">
                      {([['draft', 'Brouillon'], ['confirmed', 'Confirmée'], ['printed', 'Imprimée']] as const).map(([val, lbl]) => (
                        <button
                          key={val}
                          type="button"
                          className={`status-seg-btn flex-1 ${status === val ? `is-${val}` : ''}`}
                          onClick={() => setStatus(val)}
                        >{lbl}</button>
                      ))}
                    </div>
                    <div className="mt-2 flex flex-col gap-1.5">
                      <label className="flex items-center gap-2 cursor-pointer text-sm">
                        <input id="finalVersionInline" type="checkbox" className="form-check-input" checked={finalVersion} onChange={e => setFinalVersion(e.target.checked)} />
                        <span>Tampon PDF : Version finale</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer text-sm">
                        <input id="onInvoiceInline" type="checkbox" className="form-check-input" checked={onInvoice} onChange={e => setOnInvoice(e.target.checked)} />
                        <span>Sur facture</span>
                      </label>
                    </div>
                  </div>

                </div>

                {/* ── Allergènes pleine largeur ── */}
                <div className="form-group border-t pt-4">
                  <div className="flex flex-wrap items-center gap-2 mb-2">
                    <label className="label mb-0 font-medium">Allergènes</label>
                    <input
                      className="input w-44 text-sm"
                      placeholder="Rechercher…"
                      value={allergenQuery}
                      onChange={e => setAllergenQuery(e.target.value)}
                    />
                    <button type="button" className="btn btn-sm btn-outline" onClick={() => setAllergens([])} disabled={allergens.length === 0}>
                      Effacer tout
                    </button>
                  </div>

                  {/* Chips actifs en résumé */}
                  {allergens.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-3 p-2 bg-orange-50 border border-orange-100 rounded-lg">
                      {activeAllergenOptions.map(a => (
                        <button
                          key={a.key}
                          type="button"
                          className="allergen-active-chip"
                          onClick={() => setAllergens(prev => prev.filter(k => k !== a.key))}
                          title={`Retirer ${a.label}`}
                        >
                          <img
                            src={(a as any).icon_url || `/backend-assets/allergens/${a.key}.png`}
                            alt={a.label}
                            className="w-4 h-4 object-contain"
                            onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                          />
                          <span>{a.label}</span>
                          <X className="w-3 h-3 opacity-60" />
                        </button>
                      ))}
                    </div>
                  )}

                  <div className="allergens-grid">
                    {filteredAllergens.map(a => {
                      const active = allergens.includes(a.key)
                      const toggle = () => setAllergens(prev => active ? prev.filter(k => k !== a.key) : [...prev, a.key])
                      return (
                        <div key={a.key} className="allergen-pill" onClick={toggle}>
                          <button
                            type="button"
                            className={`btn btn-sm btn-outline allergen-btn ${active ? 'is-active' : ''}`}
                            onClick={e => { e.preventDefault(); e.stopPropagation(); toggle(); }}
                            aria-pressed={active}
                            title={a.label}
                          >
                            <img
                              src={a.icon_url || `/backend-assets/allergens/${a.key}.png`}
                              alt={a.label}
                              className="allergen-icon"
                              onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                            />
                          </button>
                          <span className="allergen-label" role="button">{a.label}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            </div>

            {/* ── Card 2 : Notes ── */}
            <div className="card">
              <div className="card-header">
                <h2 className="text-lg font-medium">Notes</h2>
              </div>
              <div className="card-body">
                <div className="rich-text-toolbar mb-2">
                  <div className="rich-text-toolbar-group">
                    <button type="button" className="btn btn-sm btn-outline" onClick={formatText('**', '**', 'Gras')} title="Gras">
                      <Bold className="w-4 h-4" />
                    </button>
                    <button type="button" className="btn btn-sm btn-outline" onClick={formatText('_', '_', 'Italique')} title="Italique">
                      <Italic className="w-4 h-4" />
                    </button>
                    <button type="button" className="btn btn-sm btn-outline" onClick={formatText('', '', 'Couleur', true)} title="Couleur">
                      <Palette className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="rich-text-editor-container border rounded-md overflow-hidden">
                  <textarea
                    name="notes"
                    className="rich-text-editor w-full p-3 font-sans text-gray-800 focus:outline-none"
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    placeholder="Saisissez vos notes ici…"
                    rows={5}
                  />
                </div>
                {notes && (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-gray-500 mb-1 uppercase tracking-wide">Aperçu</p>
                    <div
                      className="rich-text-preview p-3 bg-white border border-gray-200 rounded-md text-sm"
                      style={{ minHeight: '48px', maxHeight: '200px', overflowY: 'auto' }}
                      dangerouslySetInnerHTML={{ __html: formatPreview(notes) }}
                    />
                  </div>
                )}
              </div>
            </div>

            {/* ── Card 3 : Plats ── */}
            <div className="card">
              <div className="card-header">
                <div className="flex flex-wrap items-center gap-2 w-full justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-lg font-medium">Plats</h2>
                    <PaxBadge label="Entrées" count={totalsByType.entree} pax={pax} />
                    <PaxBadge label="Plats" count={totalsByType.plat} pax={pax} />
                    <PaxBadge label="Desserts" count={totalsByType.dessert} pax={pax} />
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button type="button" className="btn btn-sm" onClick={addItem}>
                      <Plus className="w-4 h-4" /> Ajouter
                    </button>
                    <button type="button" className="btn btn-sm btn-outline" onClick={openPicker}>Catalogue</button>
                  </div>
                </div>
              </div>
              <div className="card-body space-y-2">
                {itemsError && (
                  <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{itemsError}</div>
                )}
                {items.map((it, idx) => (
                  <ItemRow
                    key={idx}
                    item={it}
                    open={openRow === idx}
                    onFocus={() => setOpenRow(idx)}
                    onClose={() => setOpenRow(prev => prev === idx ? null : prev)}
                    onChange={p => updateItem(idx, p)}
                    onRemove={() => setItems(prev => prev.filter((_, i) => i !== idx))}
                  />
                ))}
              </div>
            </div>

            {/* Catalogue picker modal */}
            {pickerOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
                <div className="card w-[90vw] max-w-2xl max-h-[80vh] overflow-hidden">
                  <div className="card-header flex items-center justify-between">
                    <h2 className="text-lg font-medium">Ajouter depuis le catalogue</h2>
                    <button type="button" className="btn btn-sm btn-outline" onClick={() => setPickerOpen(false)}>Fermer</button>
                  </div>
                  <div className="card-body space-y-3">
                    <div className="flex flex-col sm:flex-row gap-2">
                      <input className="input flex-1" placeholder="Rechercher" value={pickerQ} onChange={e => setPickerQ(e.target.value)} />
                      <div className="flex gap-1 flex-wrap">
                        {(['all', 'entrée', 'plat', 'dessert'] as const).map(t => (
                          <button key={t} type="button" className={`filter-chip ${pickerTypeFilter === t ? 'is-active' : ''}`} onClick={() => setPickerTypeFilter(t)}>
                            {t === 'all' ? 'Tous' : t.charAt(0).toUpperCase() + t.slice(1)}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="border rounded-md overflow-auto max-h-[50vh]">
                      <ul>
                        {filteredPicker.map(it => (
                          <li key={it.id} className="flex items-center justify-between px-3 py-2 border-b last:border-b-0">
                            <div className="flex items-center gap-3">
                              <span className="font-medium text-gray-900">{it.name}</span>
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs ${it.type === 'entrée' ? 'bg-emerald-50 text-emerald-700' : it.type === 'plat' ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700'}`}>{it.type}</span>
                            </div>
                            <button type="button" className="btn btn-sm btn-primary" onClick={() => addFromPicker(it)}>Ajouter</button>
                          </li>
                        ))}
                        {filteredPicker.length === 0 && <li className="px-3 py-6 text-center text-gray-500">Aucun élément</li>}
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            )}

          </form>
        </div>

        {/* ════════════════ RIGHT — panneau récapitulatif (desktop only) ════════════════ */}
        <aside className="hidden lg:block">
          <div className="sticky top-4 card form-summary-panel">
            <div className="card-header py-3 px-4">
              <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Récapitulatif</h3>
            </div>
            <div className="card-body space-y-4 text-sm">

              {/* Checklist complétude */}
              <div className="space-y-1.5">
                {completionChecks.map(c => (
                  <div key={c.label} className="flex items-center gap-2">
                    {c.ok
                      ? <CheckCircle2 className="w-4 h-4 text-green-500 shrink-0" />
                      : <Circle className="w-4 h-4 text-gray-300 shrink-0" />}
                    <span className={c.ok ? 'text-gray-700' : 'text-gray-400'}>{c.label}</span>
                  </div>
                ))}
              </div>

              <div className="border-t" />

              {/* Identité */}
              <div>
                <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">Client</p>
                <p className="font-semibold text-gray-900 truncate">{client_name || <span className="text-gray-300 italic">—</span>}</p>
                <span className={`status-badge mt-1 ${status === 'confirmed' ? 'is-confirmed' : status === 'printed' ? 'is-printed' : 'is-draft'}`}>
                  {status === 'confirmed' ? 'Confirmée' : status === 'printed' ? 'Imprimée' : 'Brouillon'}
                </span>
              </div>

              {/* Date / heure / pax */}
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-400">Date</p>
                  <p className="font-medium text-gray-800 text-xs mt-0.5">{service_date ? new Date(service_date + 'T00:00').toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }) : '—'}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-400">Heure</p>
                  <p className="font-medium text-gray-800 text-xs mt-0.5">{arrival_time || '—'}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2">
                  <p className="text-xs text-gray-400">Couverts</p>
                  <p className="font-medium text-gray-800 text-xs mt-0.5">{pax}</p>
                </div>
              </div>

              {/* Boisson */}
              {drink_formula && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">Boisson</p>
                  <span className={`drink-badge ${drinkVariantOf(drink_formula)}`}>
                    <Wine className="w-3.5 h-3.5" />
                    <span className="drink-text">{drink_formula}</span>
                  </span>
                </div>
              )}

              {/* Allergènes */}
              {allergens.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1.5">Allergènes ({allergens.length})</p>
                  <div className="flex flex-wrap gap-1">
                    {activeAllergenOptions.map(a => (
                      <span key={a.key} className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-orange-50 border border-orange-200 text-orange-700 rounded-full text-xs">
                        <img src={(a as any).icon_url || `/backend-assets/allergens/${a.key}.png`} alt={a.label} className="w-3 h-3 object-contain" onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none' }} />
                        {a.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Plats */}
              {effectiveItems.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1.5">Plats</p>
                  <div className="space-y-1">
                    {effectiveItems.map((it, i) => (
                      <div key={i} className="flex items-center justify-between gap-2">
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${it.type === 'entrée' ? 'bg-emerald-100 text-emerald-700' : it.type === 'plat' ? 'bg-blue-100 text-blue-700' : 'bg-amber-100 text-amber-700'}`}>
                          {it.type === 'entrée' ? 'E' : it.type === 'plat' ? 'P' : 'D'}
                        </span>
                        <span className="flex-1 text-gray-700 text-xs truncate">{it.name}</span>
                        <span className="text-xs font-semibold text-gray-500">×{it.quantity}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-1.5 mt-2 flex-wrap">
                    <PaxBadge label="E" count={totalsByType.entree} pax={pax} />
                    <PaxBadge label="P" count={totalsByType.plat} pax={pax} />
                    <PaxBadge label="D" count={totalsByType.dessert} pax={pax} />
                  </div>
                </div>
              )}

              {/* Notes preview */}
              {notes && (
                <div>
                  <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-1">Notes</p>
                  <p className="text-xs text-gray-600 line-clamp-3">{notes.replace(/\*\*|__|_|\[.+?\]/g, '')}</p>
                </div>
              )}

            </div>
          </div>
        </aside>

      </div>

      {/* ── Barre sticky : navActions + dirty + sauvegarder ── */}
      <div className="fixed bottom-0 left-0 right-0 z-30 bg-white/95 backdrop-blur border-t border-gray-200 shadow-md">
        <div className="container flex items-center gap-2 py-2.5 px-4">
          {navActions && (
            <div className="flex items-center gap-1.5 flex-1 min-w-0 overflow-x-auto">
              {navActions}
            </div>
          )}
          <div className="flex items-center gap-2 ml-auto shrink-0">
            {isDirty && !submitting && (
              <span className="hidden sm:flex items-center gap-1 text-xs text-amber-600 font-medium">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                Non sauvegardé
              </span>
            )}
            {initial?.id && onOpenBilling && (
              <button type="button" className="btn btn-outline btn-sm" onClick={onOpenBilling}>Facturation</button>
            )}
            <button
              type="submit"
              form={formId || 'reservation-form'}
              className="btn btn-primary btn-sm disabled:opacity-60"
              disabled={submitting}
            >
              {submitting ? 'Sauvegarde…' : 'Sauvegarder'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

const ItemRow = React.memo(function ItemRow({
  item,
  onChange,
  open,
  onFocus,
  onClose,
  onRemove,
}: {
  item: ReservationItem;
  onChange: (p: Partial<ReservationItem>) => void;
  open: boolean;
  onFocus: () => void;
  onClose: () => void;
  onRemove: () => void;
}) {
  const [suggest, setSuggest] = useState<{ name: string; type: string }[]>([])
  const [q, setQ] = useState('')
  const [qtyInput, setQtyInput] = useState<string>(item.quantity !== undefined ? String(item.quantity) : '')
  const [activeIdx, setActiveIdx] = useState<number>(-1)
  const [showComment, setShowComment] = useState<boolean>(Boolean(item.comment))
  const inputRef = useRef<HTMLInputElement>(null)
  const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number; width: number } | null>(null)

  async function loadDefault() {
    const res = await api.get('/api/menu-items/search', { params: { type: item.type } })
    setSuggest(res.data)
  }

  useEffect(() => {
    const t = setTimeout(async () => {
      if (!q) { 
        await loadDefault(); 
        return; 
      }
      const res = await api.get('/api/menu-items/search', { params: { q, type: item.type } });
      setSuggest(res.data);
    }, 200);
    return () => clearTimeout(t);
  }, [q, item.type]);

  useEffect(() => {
    setQtyInput(item.quantity !== undefined ? String(item.quantity) : '');
  }, [item.quantity]);

  useEffect(() => {
    if (open && inputRef.current) {
      const rect = inputRef.current.getBoundingClientRect();
      setDropdownPos({ top: rect.bottom + 2, left: rect.left, width: rect.width });
    } else {
      setDropdownPos(null);
    }
  }, [open]);

  const typeColors: Record<string, string> = {
    'entrée': 'bg-emerald-100 text-emerald-700 border-emerald-300',
    'plat': 'bg-blue-100 text-blue-700 border-blue-300',
    'dessert': 'bg-amber-100 text-amber-700 border-amber-300',
  }

  return (
    <div
      className="border border-gray-100 rounded-lg p-2 bg-white shadow-sm space-y-1.5"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) onClose();
      }}
    >
      <div className="flex items-center gap-2">
        {/* Type chips compact */}
        <div className="flex gap-0.5 shrink-0">
          {(['entrée', 'plat', 'dessert'] as const).map(t => (
            <button
              key={t}
              type="button"
              title={t.charAt(0).toUpperCase() + t.slice(1)}
              className={`w-7 h-7 rounded text-xs font-semibold border transition-colors ${item.type === t ? typeColors[t] : 'bg-gray-50 text-gray-400 border-gray-200 hover:bg-gray-100'}`}
              onClick={() => { onChange({ type: t }); setQ(''); }}
            >
              {t === 'entrée' ? 'E' : t === 'plat' ? 'P' : 'D'}
            </button>
          ))}
        </div>

        {/* Nom du plat + autocomplete */}
        <div className="flex-1 min-w-0">
          <input
            ref={inputRef}
            className="input w-full text-sm py-1"
            placeholder="Nom du plat"
            value={item.name}
            onFocus={() => { onFocus(); if (!q) loadDefault(); }}
            onChange={(e) => { onChange({ name: e.target.value }); setQ(e.target.value); }}
            onKeyDown={(e) => {
              if (!open || suggest.length === 0) return;
              if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIdx(i => (i + 1) % suggest.length); }
              else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIdx(i => (i <= 0 ? suggest.length - 1 : i - 1)); }
              else if (e.key === 'Enter') {
                if (activeIdx >= 0 && activeIdx < suggest.length) {
                  e.preventDefault();
                  onChange({ name: suggest[activeIdx].name, type: suggest[activeIdx].type });
                  setSuggest([]); onClose();
                }
              } else if (e.key === 'Escape') { setSuggest([]); onClose(); }
            }}
          />
          {open && suggest.length > 0 && dropdownPos && ReactDOM.createPortal(
            <div
              style={{
                position: 'fixed',
                top: dropdownPos.top,
                left: dropdownPos.left,
                width: dropdownPos.width,
                zIndex: 9999,
              }}
              className="bg-white border border-gray-200 rounded-md shadow-lg max-h-48 overflow-auto"
            >
              {suggest.map((s, i) => (
                <div
                  key={i}
                  className={`px-3 py-2 cursor-pointer text-sm hover:bg-gray-50 ${activeIdx === i ? 'bg-gray-100' : ''}`}
                  onMouseEnter={() => setActiveIdx(i)}
                  onMouseDown={(e) => { e.preventDefault(); onChange({ name: s.name, type: s.type }); setSuggest([]); onClose(); }}
                >
                  {s.name}
                </div>
              ))}
            </div>,
            document.body
          )}
        </div>

        {/* Quantité ± */}
        <div className="flex items-center shrink-0">
          <button
            type="button"
            className="btn btn-outline rounded-r-none px-2 py-1 border-r-0"
            onClick={() => { const n = Math.max(0, (Number(qtyInput) || 0) - 1); setQtyInput(String(n)); onChange({ quantity: n }); }}
            aria-label="Diminuer"
          >
            <Minus className="w-3 h-3" />
          </button>
          <input
            type="text"
            className="input text-center rounded-none w-10 py-1 text-sm"
            value={qtyInput}
            onChange={(e) => { const v = e.target.value; if (/^\d*$/.test(v)) { setQtyInput(v); onChange({ quantity: v === '' ? 0 : parseInt(v, 10) }); } }}
            onBlur={() => { if (qtyInput === '') setQtyInput('0'); }}
          />
          <button
            type="button"
            className="btn btn-outline rounded-l-none px-2 py-1 border-l-0"
            onClick={() => { const n = (Number(qtyInput) || 0) + 1; setQtyInput(String(n)); onChange({ quantity: n }); }}
            aria-label="Augmenter"
          >
            <Plus className="w-3 h-3" />
          </button>
        </div>

        {/* Commentaire toggle */}
        <button
          type="button"
          className={`btn btn-sm btn-outline px-1.5 shrink-0 ${showComment || item.comment ? 'text-primary border-primary' : 'text-gray-400'}`}
          onClick={() => setShowComment(v => !v)}
          title="Ajouter un commentaire"
        >
          <MessageSquare className="w-3.5 h-3.5" />
        </button>

        {/* Supprimer */}
        <button
          type="button"
          className="btn btn-sm btn-outline text-red-500 border-red-200 hover:bg-red-50 px-1.5 shrink-0"
          onClick={onRemove}
          aria-label="Supprimer cette ligne"
          title="Supprimer"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Commentaire (togglable) */}
      {(showComment || Boolean(item.comment)) && (
        <input
          className="input w-full text-sm py-1 text-gray-600"
          placeholder="Commentaire (facultatif)"
          value={item.comment || ''}
          onChange={(e) => onChange({ comment: e.target.value })}
          autoFocus={showComment && !item.comment}
        />
      )}
    </div>
  );
});
