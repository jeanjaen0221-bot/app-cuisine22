import * as React from 'react';
import { useState, useEffect } from 'react';
import { api } from '../lib/api';
import { Reservation, ReservationCreate, ReservationItem } from '../types';
import { 
  User, 
  CalendarDays, 
  Clock, 
  Wine, 
  Plus, 
  Minus, 
  Bold, 
  Italic, 
  Palette
} from 'lucide-react';

const DRINKS = [
  'Sans alcool', 'Vin au verre', 'Accords mets & vins', 'Soft + Café', 'Eau + Café'
]

const ALLERGENS = [
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
  const [finalVersion, setFinalVersion] = useState<boolean>(Boolean(initial?.final_version))
  const [allergens, setAllergens] = useState<string[]>(initial?.allergens ? String(initial.allergens).split(',').map(s=>s.trim()).filter(Boolean) : [])
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
    // Taille
    const validSizes = ['text-xs', 'text-sm', 'text-base', 'text-lg', 'text-xl', 'text-2xl'];
    do {
      prev = html;
      html = html.replace(/\[size=([^\]]+)\]([\s\S]*?)\[\/size\]/g, (_m, size, inner) => {
        const safe = validSizes.includes(size) ? size : 'text-base';
        return `<span class="${safe}">${inner}</span>`;
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

  const updateItem = (idx: number, patch: Partial<ReservationItem>) => {
    setItems(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  };

  const addItem = () => {
    setItems(prev => {
      const next = [...prev, { name: '', type: 'plat', quantity: 1 }];
      setOpenRow(next.length - 1);
      return next;
    });
  };

  function validate(): boolean {
    const errs: {client?:string,date?:string,pax?:string,time?:string} = {};
    if (!client_name.trim()) errs.client = 'Le nom du client est requis';
    if (!service_date) errs.date = 'La date est requise';
    if (!arrival_time) errs.time = "L'heure d'arrivée est requise";
    if (pax < 1) errs.pax = 'Le nombre de personnes doit être supérieur à 0';
    
    setErrs(errs);
    
    // Vérifier les erreurs sur les articles
    if (items.length === 0) {
      setItemsError('Veuillez ajouter au moins un plat');
      return false;
    } else if (items.some(item => !item.name.trim())) {
      setItemsError('Tous les plats doivent avoir un nom');
      return false;
    } else if (items.some(item => (item.quantity || 0) < 1)) {
      setItemsError('La quantité doit être supérieure à 0 pour tous les plats');
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
        items: validItems,
      });
    } catch (error) {
      console.error('Erreur lors de la soumission:', error);
      // Gérer les erreurs de soumission ici
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container py-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          {initial?.id ? 'Modifier la réservation' : 'Nouvelle réservation'}
        </h1>
        <div className="flex items-center space-x-2">
          <span className={`status-badge ${
            status === 'confirmed' ? 'is-confirmed' :
            status === 'printed' ? 'is-printed' :
            'is-draft'
          }`}>
            {status === 'confirmed' ? 'Confirmée' : 
             status === 'printed' ? 'Imprimée' : 'Brouillon'}
          </span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-medium">Informations générales</h2>
          </div>
          <div className="card-body">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="form-group">
                <label className="label label-required">Nom du client</label>
                <div className="input-group">
                  <span className="input-group-text">
                    <User className="w-4 h-4 text-gray-500" />
                  </span>
                  <input 
                    className="input" 
                    value={client_name} 
                    onChange={e => setClient(e.target.value)} 
                    placeholder="Entrez le nom du client"
                    required
                  />
                </div>
                {errs.client && <div className="text-red-500 text-sm mt-1">{errs.client}</div>}
              </div>

              <div className="form-group">
                <label className="label label-required">Date de service</label>
                <div className="input-group">
                  <span className="input-group-text">
                    <CalendarDays className="w-4 h-4 text-gray-500" />
                  </span>
                  <input 
                    type="date" 
                    className="input" 
                    value={service_date} 
                    onChange={e => setDate(e.target.value)}
                    required
                  />
                </div>
                {errs.date && <div className="text-red-500 text-sm mt-1">{errs.date}</div>}
              </div>

              <div className="form-group">
                <label className="label label-required">Heure d'arrivée</label>
                <div className="input-group">
                  <span className="input-group-text">
                    <Clock className="w-4 h-4 text-gray-500" />
                  </span>
                  <input 
                    type="time" 
                    className="input" 
                    value={arrival_time} 
                    onChange={e => setTime(e.target.value)}
                    required
                  />
                </div>
                {errs.time && <div className="text-red-500 text-sm mt-1">{errs.time}</div>}
              </div>

              <div className="form-group">
                <label className="label label-required">Nombre de couverts</label>
                <div className="flex items-center">
                  <button 
                    type="button" 
                    className="btn btn-outline rounded-r-none px-3 border-r-0"
                    onClick={() => setPax(p => Math.max(1, p - 1))}
                    aria-label="Réduire le nombre de couverts"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <div className="relative flex-1">
                    <input 
                      type="number" 
                      min="1"
                      className="input text-center rounded-none"
                      value={pax} 
                      onChange={e => setPax(Math.max(1, Number(e.target.value)))}
                      required
                    />
                  </div>
                  <button 
                    type="button" 
                    className="btn btn-outline rounded-l-none px-3 border-l-0"
                    onClick={() => setPax(p => p + 1)}
                    aria-label="Augmenter le nombre de couverts"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label className="label">Formule boisson</label>
                <div className="input-group">
                  <span className="input-group-text">
                    <Wine className="w-4 h-4 text-gray-500" />
                  </span>
                  <select 
                    className="input" 
                    value={drink_formula} 
                    onChange={e => setDrink(e.target.value)}
                  >
                    {DRINKS.map(drink => (
                      <option key={drink} value={drink}>{drink}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label className="label">Allergènes</label>
                <div className="flex flex-wrap gap-2">
                  {ALLERGENS.map(a => {
                    const active = allergens.includes(a.key)
                    return (
                      <button
                        key={a.key}
                        type="button"
                        className={`btn btn-sm ${active ? '' : 'btn-outline'}`}
                        onClick={() => setAllergens(prev => active ? prev.filter(k => k !== a.key) : [...prev, a.key])}
                      >
                        <span className="inline-flex items-center gap-2">
                          <img
                            src={`/backend-assets/allergens/${a.key}.png`}
                            alt={a.label}
                            title={a.label}
                            className="h-5 w-5 object-contain"
                            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none' }}
                          />
                          <span>{a.label}</span>
                        </span>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="form-group">
                <label className="label">Statut</label>
                <select 
                  className="input" 
                  value={status} 
                  onChange={e => setStatus(e.target.value as Reservation['status'])}
                >
                  <option value="draft">Brouillon</option>
                  <option value="confirmed">Confirmée</option>
                  <option value="printed">Imprimée</option>
                </select>
                <div className="mt-2 flex items-center gap-2">
                  <input
                    id="finalVersionInline"
                    type="checkbox"
                    className="form-check-input"
                    checked={finalVersion}
                    onChange={e => setFinalVersion(e.target.checked)}
                  />
                  <label htmlFor="finalVersionInline" className="form-check-label text-sm">Tampon PDF: Version finale</label>
                </div>
              </div>
              <div className="form-group">
                <label className="label">Version finale</label>
                <div className="flex items-center gap-2">
                  <input
                    id="finalVersion"
                    type="checkbox"
                    className="form-check-input"
                    checked={finalVersion}
                    onChange={e => setFinalVersion(e.target.checked)}
                  />
                  <label htmlFor="finalVersion" className="form-check-label">Afficher le tampon « Version finale » en bas du PDF</label>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h2 className="text-lg font-medium">Détails supplémentaires</h2>
          </div>
          <div className="card-body">
            <div className="form-group">
              <div className="flex justify-between items-center mb-2">
                <label className="label">Notes</label>
              </div>
              <div className="rich-text-toolbar">
                <div className="rich-text-toolbar-group">
                  <button 
                    type="button" 
                    className="btn btn-sm btn-outline"
                    onClick={formatText('**', '**', 'Gras')}
                    title="Gras"
                    aria-label="Mettre en gras"
                  >
                    <Bold className="w-4 h-4" />
                  </button>
                  <button 
                    type="button" 
                    className="btn btn-sm btn-outline"
                    onClick={formatText('_', '_', 'Italique')}
                    title="Italique"
                    aria-label="Mettre en italique"
                  >
                    <Italic className="w-4 h-4" />
                  </button>
                  <button 
                    type="button" 
                    className="btn btn-sm btn-outline"
                    onClick={formatText('', '', 'Couleur', true)}
                    title="Couleur"
                    aria-label="Changer la couleur du texte"
                  >
                    <Palette className="w-4 h-4" />
                  </button>
                </div>
                <select 
                  className="input input-sm w-auto" 
                  value={fontSize} 
                  onChange={e => applyFontSize(e.target.value)}
                  title="Taille de police"
                  aria-label="Taille de police"
                >
                  {fontSizes.map(size => (
                    <option key={size.value} value={size.value}>{size.label}</option>
                  ))}
                </select>
              </div>
              <div className="relative">
                <div className="rich-text-editor-container border rounded-md overflow-hidden">
                  <textarea
                    name="notes"
                    className="rich-text-editor w-full p-4 font-sans text-gray-800 focus:outline-none"
                    value={notes}
                    onChange={e => setNotes(e.target.value)}
                    placeholder="Saisissez vos notes ici..."
                    rows={6}
                  />
                </div>
                {notes && (
                  <div className="mt-4">
                    <p className="text-sm font-medium text-gray-700 mb-2">Aperçu :</p>
                    <div 
                      className="rich-text-preview p-4 bg-white border border-gray-200 rounded-md"
                      style={{ 
                        minHeight: '80px',
                        maxHeight: '200px',
                        overflowY: 'auto'
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

        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-primary">Plats</h3>
          <button type="button" className="btn" onClick={addItem}>+ Ajouter un plat</button>
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
                onRemove={() => {
                  setItems(prev => prev.filter((item, index) => index !== idx));
                }}
              />
            </div>
          ))}
        </div>
        <div className="card-footer">
          <button type="submit" className="btn btn-primary disabled:opacity-60" disabled={submitting}>
            {submitting ? 'Sauvegarde…' : 'Sauvegarder'}
          </button>
        </div>
      </form>
    </div>
  );
}

const ItemRow = React.memo(function ItemRow({ 
  item, 
  onChange, 
  open, 
  onFocus, 
  onClose, 
  onRemove 
}: { 
  item: ReservationItem; 
  onChange: (p: Partial<ReservationItem>) => void; 
  open: boolean; 
  onFocus: () => void;
  onClose: () => void;
  onRemove: () => void;
}) {
  const [suggest, setSuggest] = useState<{name:string,type:string}[]>([])
  const [q, setQ] = useState('')
  const [qtyInput, setQtyInput] = useState<string>(item.quantity !== undefined ? String(item.quantity) : '')
  const [activeIdx, setActiveIdx] = useState<number>(-1)

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

  return (
    <div 
      className="grid grid-cols-12 gap-2" 
      onBlur={(e) => { 
        if (!e.currentTarget.contains(e.relatedTarget as Node)) onClose(); 
      }}
    >
      <select 
        className="input col-span-2" 
        value={item.type} 
        onChange={(e) => { 
          onChange({ type: e.target.value }); 
          setQ(''); 
        }}
      >
        <option>entrée</option>
        <option>plat</option>
        <option>dessert</option>
      </select>
      <div className="col-span-8 relative">
        <input 
          className="input w-full" 
          placeholder="Nom du plat" 
          value={item.name} 
          onFocus={() => { 
            onFocus(); 
            if (!q) loadDefault(); 
          }} 
          onChange={(e) => { 
            onChange({ name: e.target.value }); 
            setQ(e.target.value); 
          }} 
          onKeyDown={(e) => {
            if (!open || suggest.length === 0) return;
            if (e.key === 'ArrowDown') {
              e.preventDefault();
              setActiveIdx(idx => (idx + 1) % suggest.length);
            } else if (e.key === 'ArrowUp') {
              e.preventDefault();
              setActiveIdx(idx => (idx <= 0 ? suggest.length - 1 : idx - 1));
            } else if (e.key === 'Enter') {
              if (activeIdx >= 0 && activeIdx < suggest.length) {
                e.preventDefault();
                const s = suggest[activeIdx];
                onChange({ name: s.name, type: s.type });
                setSuggest([]);
                onClose();
              }
            } else if (e.key === 'Escape') {
              setSuggest([]);
              onClose();
            }
          }}
        />
        {open && suggest.length > 0 && (
          <div className="absolute z-10 bg-white border rounded-md mt-1 max-h-48 overflow-auto w-full">
            {suggest.map((s, i) => (
              <div
                key={i}
                className={`px-3 py-2 cursor-pointer menu-item ${activeIdx === i ? 'active' : ''}`}
                onMouseEnter={() => setActiveIdx(i)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange({ name: s.name, type: s.type });
                  setSuggest([]);
                  onClose();
                }}
              >
                {s.name}
              </div>
            ))}
          </div>
        )}
      </div>
      <input
        type="number"
        min={0}
        className="input col-span-2"
        value={qtyInput}
        onChange={(e) => {
          const v = e.target.value;
          if (/^\d*$/.test(v)) {
            setQtyInput(v);
            onChange({ quantity: v === '' ? 0 : parseInt(v, 10) });
          }
        }}
        onBlur={() => { 
          if (qtyInput === '') setQtyInput('0'); 
        }}
      />
    </div>
  );
});
