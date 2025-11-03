import * as React from 'react';
import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Reservation, ReservationCreate, ReservationItem } from '../types';
import { User, CalendarDays, Clock, Users, Wine, StickyNote, Utensils, Trash2, Plus, Minus, X } from 'lucide-react';

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

  // État pour la taille de police
  const [fontSize, setFontSize] = useState('text-base');

  // Options de taille de police
  const fontSizes = [
    { value: 'text-xs', label: 'Petit' },
    { value: 'text-sm', label: 'Normal' },
    { value: 'text-base', label: 'Moyen' },
    { value: 'text-lg', label: 'Grand' },
    { value: 'text-xl', label: 'Très grand' },
    { value: 'text-2xl', label: 'Énorme' },
  ];

  // Fonction pour appliquer la taille de police
  const applyFontSize = (size: string) => {
    setFontSize(size);
  };

  // Fonction pour formater le texte sélectionné
  const formatText = (prefix: string, suffix: string, title: string, showColorPicker = false, sizeTag = '') => {
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
          // Si du texte est sélectionné, on l'entoure des balises de couleur
          if (selectedText) {
            setNotes(`${before}[color=${color}]${selectedText}[/color]${after}`);
            setTimeout(() => {
              textarea.focus();
              textarea.setSelectionRange(start, end + 15 + color.length);
            }, 0);
          } else {
            // Sinon, on insère juste les balises et on place le curseur entre elles
            const newPosition = start + `[color=${color}][/color]`.length;
            setNotes(`${before}[color=${color}][/color]${after}`);
            setTimeout(() => {
              textarea.focus();
              textarea.setSelectionRange(newPosition - 8, newPosition - 8);
            }, 0);
          }
        };
        colorPicker.click();
      } else if (sizeTag) {
        // Gestion des tailles de police
        if (selectedText) {
          setNotes(`${before}[size=${sizeTag}]${selectedText}[/size]${after}`);
          setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(start, end + 13 + sizeTag.length);
          }, 0);
        } else {
          const newPosition = start + `[size=${sizeTag}][/size]`.length;
          setNotes(`${before}[size=${sizeTag}][/size]${after}`);
          setTimeout(() => {
            textarea.focus();
            textarea.setSelectionRange(newPosition - 8, newPosition - 8);
          }, 0);
        }
      } else {
        // Formatage standard (gras, italique, etc.)
        setNotes(`${before}${prefix}${selectedText}${suffix}${after}`);
        setTimeout(() => {
          textarea.focus();
          if (selectedText) {
            // Si du texte était sélectionné, on sélectionne le texte + les balises
            textarea.setSelectionRange(start, end + prefix.length + suffix.length);
          } else {
            // Si pas de sélection, on place le curseur entre les balises
            textarea.setSelectionRange(start + prefix.length, start + prefix.length);
          }
        }, 0);
      }
    };
  };
  
  // Fonction pour échapper les caractères HTML
  const escapeHtml = (unsafe: string) => {
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
    
    // Fonction pour échapper le HTML tout en préservant les balises de formatage
    const escapeHtmlButKeepTags = (unsafe: string) => {
      // D'abord, protéger nos balises personnalisées
      const protectedText = unsafe
        .replace(/\[color=([^\]]+)\]/g, 'color=$1')
        .replace(/\[\/color\]/g, '/color')
        .replace(/\[size=([^\]]+)\]/g, 'size=$1')
        .replace(/\[\/size\]/g, '/size');
      
      // Puis échapper le HTML
      const escaped = protectedText
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
      
      // Enfin, restaurer nos balises personnalisées
      return escaped
        .replace(/\uE000color=(.+?)\uE001/g, '[color=$1]')
        .replace(/\uE000\/color\uE001/g, '[/color]')
        .replace(/\uE000size=(.+?)\uE001/g, '[size=$1]')
        .replace(/\uE000\/size\uE001/g, '[/size]');
    };
    
    // Échapper le HTML tout en préservant nos balises
    let html = escapeHtmlButKeepTags(text);
    
    // Fonction pour traiter les balises de manière récursive
    const processTags = (input: string): string => {
      // D'abord, traiter les balises les plus internes (couleur et taille)
      const tagRegex = /\[(\/?(?:color|size)(?:=([^\]]+))?)\](.*?)(?=\[\/?(?:color|size)|$)/gs;
      
      let result = '';
      let lastIndex = 0;
      let match;
      
      while ((match = tagRegex.exec(input)) !== null) {
        const [fullMatch, tag, value, content] = match;
        const tagName = tag.startsWith('/') ? tag.substring(1) : tag.split('=')[0];
        
        // Ajouter le texte avant la balise
        result += input.substring(lastIndex, match.index);
        lastIndex = match.index + fullMatch.length;
        
        if (tag.startsWith('/')) {
          // Balise de fermeture
          result += `</span>`;
        } else if (tagName === 'color' && value) {
          // Balise d'ouverture de couleur
          result += `<span style="color: ${value}">`;
        } else if (tagName === 'size' && value) {
          // Balise d'ouverture de taille
          result += `<span class="${value}">`;
        }
        
        // Traiter récursivement le contenu
        if (content) {
          result += processTags(content);
        }
      }
      
      // Ajouter le texte restant
      result += input.substring(lastIndex);
      
      return result;
    };
    
    // Fonction pour traiter les tailles de police
    const processSizeTags = (input: string): string => {
      const sizeRegex = /\[size=([^\]]+)\](.*?)\[\/size\]/g;
      let result = input;
      let match;
      
      while ((match = sizeRegex.exec(input)) !== null) {
        const fullMatch = match[0];
        const size = match[1];
        const content = match[2];
        
        // Vérifier si la taille est valide
        const validSizes = ['text-xs', 'text-sm', 'text-base', 'text-lg', 'text-xl', 'text-2xl'];
        const safeSize = validSizes.includes(size) ? size : 'text-base';
        
        result = result.replace(fullMatch, `<span class="${safeSize}">${content}</span>`);
        
        // Réinitialiser lastIndex pour éviter les boucles infinies
        sizeRegex.lastIndex = 0;
      }
      
      return result;
    };
    
    // Appliquer le traitement des balises (couleurs et tailles)
    html = processTags(html);
    
    // Traiter les autres formats
    html = html
      // Gras avec **texte** ou *texte*
      .replace(/\*\*([^*]+)\*\*|\*([^*]+)\*/g, (match, p1, p2) => {
        return `<strong>${p1 || p2}</strong>`;
      })
      // Italique avec _texte_
      .replace(/_([^_]+)_/g, '<em>$1</em>')
      // Listes à puces
      .replace(/\n-\s+/g, '<br/>• ')
      // Retours à la ligne
      .replace(/\n/g, '<br/>')
      // Échapper à nouveau pour les caractères spéciaux qui auraient pu être ajoutés
      .replace(/&amp;(?=#?\w+;)/g, '&');
    
    return html;
  };

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
          <div className="space-y-2">
            <label className="label flex items-center gap-2">
              <StickyNote className="h-4 w-4"/> Notes cuisine
            </label>
            
            {/* Barre d'outils moderne */}
            <div className="flex items-center gap-2 p-2 bg-gray-50 rounded-t-lg border border-b-0 border-gray-200">
              <div className="flex items-center divide-x divide-gray-200">
                <button
                  type="button"
                  className="p-2 text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
                  onClick={formatText('*', '*', 'Gras')}
                  title="Gras (Ctrl+B)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                </button>
                
                <button
                  type="button"
                  className="p-2 text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
                  onClick={formatText('_', '_', 'Italique')}
                  title="Italique (Ctrl+I)"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                  </svg>
                </button>
                
                <button
                  type="button"
                  className="p-2 text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
                  onClick={formatText('[color=#000000]', '[/color]', 'Couleur du texte', true)}
                  title="Couleur du texte"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.486M7 17h.01" />
                  </svg>
                </button>
                
                {/* Bouton liste à puces */}
                <button
                  type="button"
                  className="p-2 text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
                  onClick={() => {
                    const textarea = document.querySelector('textarea[name="notes"]') as HTMLTextAreaElement;
                    if (!textarea) return;
                    const start = textarea.selectionStart;
                    const end = textarea.selectionEnd;
                    const selectedText = notes.substring(start, end);
                    const before = notes.substring(0, start);
                    const after = notes.substring(end);
                    
                    if (selectedText) {
                      // Si du texte est sélectionné, ajouter des puces à chaque ligne
                      const lines = selectedText.split('\n').map(line => `- ${line}`).join('\n');
                      setNotes(`${before}${lines}${after}`);
                      setTimeout(() => {
                        textarea.setSelectionRange(start, start + lines.length);
                        textarea.focus();
                      }, 0);
                    } else {
                      // Si pas de sélection, ajouter une puce simple
                      setNotes(`${before}- ${after}`);
                      setTimeout(() => {
                        textarea.setSelectionRange(start + 2, start + 2);
                        textarea.focus();
                      }, 0);
                    }
                  }}
                  title="Liste à puces"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
                  </svg>
                </button>
                
                {/* Sélecteur de taille de police */}
                <div className="relative group">
                  <button
                    type="button"
                    className="p-2 text-gray-700 hover:bg-gray-100 rounded-md transition-colors flex items-center gap-1"
                    title="Taille du texte"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6h18M3 12h18m-9 6h9" />
                    </svg>
                    <span className="text-xs">Taille</span>
                  </button>
                  <div className="absolute z-10 hidden group-hover:block bg-white rounded-md shadow-lg border border-gray-200 p-2 min-w-[120px]">
                    <div className="text-xs text-gray-500 px-2 py-1">Taille du texte</div>
                    {fontSizes.map((size) => (
                      <button
                        key={size.value}
                        type="button"
                        className={`w-full text-left px-2 py-1 text-sm hover:bg-gray-100 rounded ${fontSize === size.value ? 'bg-blue-50 text-blue-600' : ''}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          applyFontSize(size.value);
                          formatText(`[size=${size.value}]`, '[/size]', `Taille ${size.label}`, false, size.value);
                        }}
                      >
                        {size.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
              
              <div className="ml-auto flex items-center space-x-2">
                <span className="text-sm text-gray-500">
                  {notes.length} caractères
                </span>
              </div>
            </div>
            
            {/* Zone de texte */}
            <div className="relative">
              <textarea
                name="notes"
                className="input min-h-[120px] w-full font-sans text-gray-800 border-t-0 rounded-t-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-colors"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                placeholder="Saisissez vos notes ici..."
                style={{ 
                  whiteSpace: 'pre-wrap',
                  lineHeight: '1.5',
                  padding: '1rem',
                  fontSize: '0.9375rem'
                }}
              />
              
              {/* Aperçu du formatage en temps réel */}
              {notes && (
                <div className="mt-2 p-3 text-sm bg-white rounded border border-gray-200">
                  <p className="font-medium text-gray-700 mb-1">Aperçu :</p>
                  <div 
                    className="rich-text-preview min-h-[60px] p-2 bg-white border rounded"
                    style={{ 
                      whiteSpace: 'pre-wrap',
                      lineHeight: '1.5',
                      fontSize: '0.9375rem',
                      overflowY: 'auto',
                      maxHeight: '200px'
                    }}
                    dangerouslySetInnerHTML={{ 
                      __html: formatPreview(notes) 
                    }} 
                  />
                </div>
              )}
            </div>
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
