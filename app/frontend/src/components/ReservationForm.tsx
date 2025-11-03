import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { Reservation, ReservationCreate, ReservationItem } from '../types'
import { User, CalendarDays, Clock, Users, Wine, StickyNote } from 'lucide-react'

const DRINKS = [
  'Sans alcool', 'Vin au verre', 'Accords mets & vins', 'Soft + Café', 'Eau + Café'
]

type Props = {
  initial?: Partial<Reservation>
  onSubmit: (payload: Partial<ReservationCreate>) => Promise<void>
}

export default function ReservationForm({ initial, onSubmit }: Props) {
  const [client_name, setClient] = useState(initial?.client_name || '')
  const [service_date, setDate] = useState(initial?.service_date || '')
  const [arrival_time, setTime] = useState(initial?.arrival_time || '')
  const [pax, setPax] = useState(initial?.pax || 2)
  const [drink_formula, setDrink] = useState(initial?.drink_formula || DRINKS[0])
  const [notes, setNotes] = useState(initial?.notes || '')
  const [status, setStatus] = useState<Reservation['status']>(initial?.status || 'draft')
  const [items, setItems] = useState<ReservationItem[]>(initial?.items || [])
  const [openRow, setOpenRow] = useState<number | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [errs, setErrs] = useState<{client?:string,date?:string,pax?:string,time?:string}>({})
  const [itemsError, setItemsError] = useState<string | null>(null)

  // Sync when initial changes (e.g., when loading an existing reservation)
  useEffect(() => {
    if (!initial) return
    setClient(initial.client_name || '')
    setDate((initial.service_date || '').slice(0,10))
    setTime((initial.arrival_time || '').slice(0,5))
    setPax(initial.pax ?? 2)
    setDrink(initial.drink_formula || DRINKS[0])
    setNotes(initial.notes || '')
    setStatus((initial.status as Reservation['status']) || 'draft')
    setItems(initial.items || [])
  }, [initial])

  useEffect(() => {
    if (!items.length) {
      setItems([
        { type: 'entrée', name: '', quantity: 0 },
        { type: 'plat', name: '', quantity: 0 },
        { type: 'dessert', name: '', quantity: 0 },
      ])
    }
  }, [])

  function updateItem(idx: number, patch: Partial<ReservationItem>) {
    setItems(prev => prev.map((it, i) => i===idx ? { ...it, ...patch } : it))
  }

  function addItem() {
    setItems(prev => [...prev, { type: 'plat', name: '', quantity: 1 }])
  }

  function validate(): boolean {
    const e: {client?:string,date?:string,pax?:string,time?:string} = {}
    if (!client_name.trim()) e.client = 'Nom requis'
    if (!service_date) e.date = 'Date requise'
    if (!pax || pax < 1) e.pax = 'Min 1'
    if (arrival_time && !/^\d{2}:\d{2}(:\d{2})?$/.test(arrival_time)) e.time = 'Format HH:MM'
    // Guard: per-type totals must not exceed pax
    const totals: Record<string, number> = { 'entrée': 0, 'plat': 0, 'dessert': 0 }
    for (const it of items || []) {
      if (it && it.type in totals) totals[it.type] += (Number(it.quantity) || 0)
    }
    let ok = Object.keys(e).length === 0
    let itemsErr: string | null = null
    const offenders: string[] = []
    const px = Number(pax) || 0
    for (const k of Object.keys(totals)) {
      if (totals[k] > px) offenders.push(`${k}=${totals[k]}`)
    }
    if (offenders.length > 0) { ok = false; itemsErr = `Le total par type dépasse le nombre de couverts (${pax}): ${offenders.join(', ')}` }
    setErrs(e)
    setItemsError(itemsErr)
    return ok
  }

  async function submit() {
    if (submitting) return
    if (!validate()) return
    setSubmitting(true)
    try {
      const d = service_date || new Date().toISOString().slice(0,10)
      let t = arrival_time && arrival_time.length >= 4 ? arrival_time : '00:00'
      if (/^\d{2}:\d{2}$/.test(t)) t = `${t}:00`
      const name = (client_name || '').trim() || 'Client'
      const validItems = (items || [])
        .filter(it => (it.name || '').trim() && (it.quantity || 0) > 0)
        .map(it => ({ type: it.type, name: it.name, quantity: it.quantity }))
      await onSubmit({ client_name: name, service_date: d, arrival_time: t, pax: Number(pax) || 1, drink_formula, notes, status, items: validItems })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="card">
      {itemsError && (
        <div className="mb-3 p-3 rounded-md bg-red-50 border border-red-200 text-red-700 text-sm">{itemsError}</div>
      )}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="label flex items-center gap-2"><User className="h-4 w-4"/> Nom du client</label>
          <input className={`input ${errs.client ? 'border-red-300' : ''}`} value={client_name} onChange={e=>{ setClient(e.target.value); if (errs.client) setErrs({...errs, client: undefined}) }} />
          {errs.client && <div className="text-xs text-red-600 mt-1">{errs.client}</div>}
        </div>
        <div>
          <label className="label flex items-center gap-2"><CalendarDays className="h-4 w-4"/> Date du service</label>
          <input type="date" className={`input ${errs.date ? 'border-red-300' : ''}`} value={service_date} onChange={e=>{ setDate(e.target.value); if (errs.date) setErrs({...errs, date: undefined}) }} />
          {errs.date && <div className="text-xs text-red-600 mt-1">{errs.date}</div>}
        </div>
        <div>
          <label className="label flex items-center gap-2"><Clock className="h-4 w-4"/> Heure d’arrivée</label>
          <input type="time" className={`input ${errs.time ? 'border-red-300' : ''}`} value={arrival_time} onChange={e=>{ setTime(e.target.value); if (errs.time) setErrs({...errs, time: undefined}) }} />
          {errs.time && <div className="text-xs text-red-600 mt-1">{errs.time}</div>}
        </div>
        <div>
          <label className="label flex items-center gap-2"><Users className="h-4 w-4"/> Nombre de couverts</label>
          <input type="number" min={1} className={`input ${errs.pax ? 'border-red-300' : ''}`} value={pax} onChange={e=>{ setPax(Number(e.target.value)); if (errs.pax) setErrs({...errs, pax: undefined}) }} />
          {errs.pax && <div className="text-xs text-red-600 mt-1">{errs.pax}</div>}
        </div>
        <div>
          <label className="label flex items-center gap-2"><Wine className="h-4 w-4"/> Formule boisson</label>
          <select className="input" value={drink_formula} onChange={e=>setDrink(e.target.value)}>
            {DRINKS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Statut</label>
          <select className="input" value={status} onChange={e=>setStatus(e.target.value as Reservation['status'])}>
            <option value="draft">Brouillon</option>
            <option value="confirmed">Confirmée</option>
            <option value="printed">Imprimée</option>
          </select>
        </div>
        <div className="md:col-span-2">
          <div>
            <label className="label flex items-center gap-2"><StickyNote className="h-4 w-4"/> Notes cuisine</label>
            <div className="flex gap-1 mb-1 flex-wrap">
              <button 
                type="button" 
                className="px-2 py-1 text-sm border rounded hover:bg-gray-100"
                onClick={() => {
                  const textarea = document.querySelector('textarea[name="notes"]') as HTMLTextAreaElement;
                  if (!textarea) return;
                  const start = textarea.selectionStart;
                  const end = textarea.selectionEnd;
                  const selectedText = notes.substring(start, end);
                  const before = notes.substring(0, start);
                  const after = notes.substring(end);
                  setNotes(`${before}*${selectedText}*${after}`);
                  // Replace the selection with the formatted text
                  setTimeout(() => {
                    textarea.setSelectionRange(start, end + 2);
                    textarea.focus();
                  }, 0);
                }}
                title="Gras"
              >
                <strong>B</strong>
              </button>
              <button 
                type="button" 
                className="px-2 py-1 text-sm border rounded hover:bg-gray-100 italic"
                onClick={() => {
                  const textarea = document.querySelector('textarea[name="notes"]') as HTMLTextAreaElement;
                  if (!textarea) return;
                  const start = textarea.selectionStart;
                  const end = textarea.selectionEnd;
                  const selectedText = notes.substring(start, end);
                  const before = notes.substring(0, start);
                  const after = notes.substring(end);
                  setNotes(`${before}_${selectedText}_${after}`);
                  // Replace the selection with the formatted text
                  setTimeout(() => {
                    textarea.setSelectionRange(start, end + 2);
                    textarea.focus();
                  }, 0);
                }}
                title="Italique"
              >
                I
              </button>
              <div className="relative inline-block">
                <button 
                  type="button" 
                  className="px-2 py-1 text-sm border rounded hover:bg-gray-100 flex items-center gap-1"
                  title="Couleur du texte"
                  onClick={(e) => {
                    const colorPicker = document.getElementById('color-picker') as HTMLInputElement;
                    if (colorPicker) colorPicker.click();
                  }}
                >
                  <span>A</span>
                  <span className="text-xs">▼</span>
                </button>
                <input 
                  type="color" 
                  id="color-picker" 
                  className="absolute opacity-0 w-0 h-0" 
                  onChange={(e) => {
                    const color = e.target.value;
                    const textarea = document.querySelector('textarea[name="notes"]') as HTMLTextAreaElement;
                    if (!textarea) return;
                    const start = textarea.selectionStart;
                    const end = textarea.selectionEnd;
                    const selectedText = notes.substring(start, end);
                    const before = notes.substring(0, start);
                    const after = notes.substring(end);
                    setNotes(`${before}[color=${color}]${selectedText}[/color]${after}`);
                    // Replace the selection with the formatted text
                    setTimeout(() => {
                      textarea.setSelectionRange(start, end + 15 + color.length);
                      textarea.focus();
                    }, 0);
                  }}
                />
              </div>
              <button 
                type="button" 
                className="px-2 py-1 text-sm border rounded hover:bg-gray-100"
                onClick={() => {
                  const textarea = document.querySelector('textarea[name="notes"]') as HTMLTextAreaElement;
                  if (!textarea) return;
                  const start = textarea.selectionStart;
                  const end = textarea.selectionEnd;
                  const selectedText = notes.substring(start, end);
                  const before = notes.substring(0, start);
                  const after = notes.substring(end);
                  setNotes(`${before}- ${selectedText}\n${after}`);
                  // Place cursor at the end of the new list item
                  setTimeout(() => {
                    const newPosition = start + 2 + selectedText.length;
                    textarea.setSelectionRange(newPosition, newPosition);
                    textarea.focus();
                  }, 0);
                }}
                title="Liste à puces"
              >
                •
              </button>
            </div>
            <textarea 
              name="notes"
              className="input min-h-[100px] w-full font-mono" 
              value={notes} 
              onChange={e => setNotes(e.target.value)} 
              placeholder="Entrez vos notes ici..."
            />
            <style dangerouslySetInnerHTML={{
              __html: `
                textarea[name="notes"] {
                  white-space: pre-wrap;
                }
                textarea[name="notes"]::placeholder {
                  color: #9CA3AF;
                  opacity: 1;
                }
              `
            }} />
          </div>
        </div>
      </div>

      <div className="mt-6">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-primary">Plats</h3>
          <button className="btn" onClick={addItem}>+ Ajouter un plat</button>
        </div>
        {itemsError && (
          <div className="mt-2 text-xs text-red-600">{itemsError}</div>
        )}
        <div className="mt-3 space-y-2">
          {items.map((it, idx) => (
            <div key={idx}>
              <ItemRow
                item={it}
                open={openRow === idx}
                onFocus={()=>setOpenRow(idx)}
                onClose={()=>setOpenRow(prev => prev === idx ? null : prev)}
                onChange={(p)=>updateItem(idx,p)}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 flex gap-2">
        <button className="btn disabled:opacity-60" disabled={submitting} onClick={submit}>{submitting ? 'Sauvegarde…' : 'Sauvegarder'}</button>
      </div>
    </div>
  )
}

function ItemRow({ item, onChange, open, onFocus, onClose }: { item: ReservationItem, onChange: (p: Partial<ReservationItem>)=>void, open: boolean, onFocus: ()=>void, onClose: ()=>void }) {
  const [suggest, setSuggest] = useState<{name:string,type:string}[]>([])
  const [q, setQ] = useState('')
  const [qtyInput, setQtyInput] = useState<string>(item.quantity !== undefined ? String(item.quantity) : '')

  async function loadDefault() {
    const res = await api.get('/api/menu-items/search', { params: { type: item.type } })
    setSuggest(res.data)
  }

  useEffect(() => {
    const t = setTimeout(async () => {
      if (!q) { await loadDefault(); return }
      const res = await api.get('/api/menu-items/search', { params: { q, type: item.type } })
      setSuggest(res.data)
    }, 200)
    return () => clearTimeout(t)
  }, [q, item.type])

  useEffect(() => {
    setQtyInput(item.quantity !== undefined ? String(item.quantity) : '')
  }, [item.quantity])

  return (
    <div className="grid grid-cols-12 gap-2" onBlur={(e)=>{ if (!e.currentTarget.contains(e.relatedTarget as Node)) onClose() }}>
      <select className="input col-span-2" value={item.type} onChange={e=>{ onChange({ type: e.target.value }); setQ(''); }}>
        <option>entrée</option>
        <option>plat</option>
        <option>dessert</option>
      </select>
      <div className="col-span-8 relative">
        <input className="input w-full" placeholder="Nom du plat" value={item.name} onFocus={()=>{ onFocus(); if (!q) loadDefault() }} onChange={e=>{ onChange({ name: e.target.value }); setQ(e.target.value) }} />
        {open && suggest.length>0 && (
          <div className="absolute z-10 bg-white border rounded-md mt-1 max-h-48 overflow-auto w-full">
            {suggest.map((s, i) => (
              <div key={i} className="px-3 py-2 hover:bg-gray-100 cursor-pointer" onMouseDown={(e)=>{ e.preventDefault(); onChange({ name: s.name, type: s.type }); setSuggest([]); onClose(); }}>{s.name}</div>
            ))}
          </div>
        )}
      </div>
      <input
        type="number"
        min={0}
        className="input col-span-2"
        value={qtyInput}
        onChange={e=>{
          const v = e.target.value
          if (/^\d*$/.test(v)) {
            setQtyInput(v)
            onChange({ quantity: v === '' ? 0 : parseInt(v, 10) })
          }
        }}
        onBlur={()=>{ if (qtyInput === '') setQtyInput('0') }}
      />
    </div>
  )
}
