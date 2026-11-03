import { FormEvent, useEffect, useState } from 'react'
import { api } from '../api'
import { Champ, EnTete, Erreur, useAction } from '../composants/ui'

type Params = Record<string, string | number | string[]>

const CHAMPS: { cle: string; libelle: string; aide?: string; long?: boolean }[] = [
  { cle: 'restaurant_nom', libelle: 'Nom du restaurant' },
  { cle: 'restaurant_adresse', libelle: 'Adresse', aide: 'Imprimée en haut des devis et des bons.' },
  { cle: 'restaurant_telephone', libelle: 'Téléphone' },
  { cle: 'restaurant_email', libelle: 'E-mail' },
  { cle: 'restaurant_tva', libelle: 'N° TVA du restaurant' },
  { cle: 'conditions_paiement_defaut', libelle: 'Conditions de paiement par défaut' },
  { cle: 'mentions_devis', libelle: 'Mentions en bas des devis', long: true },
]

export default function Parametres() {
  const [p, setP] = useState<Params | null>(null)
  const [ok, setOk] = useState(false)
  const { enCours, erreur, setErreur, lancer } = useAction()

  useEffect(() => { api.get<Params>('/api/parametres').then(setP).catch((e) => setErreur(e.message)) }, [setErreur])
  if (!p) return <Erreur message={erreur} />

  const enregistrer = async (e: FormEvent) => {
    e.preventDefault()
    const heures = String(p.heures_proposees).split(',').map((h) => h.trim()).filter(Boolean)
    const r = await lancer(() => api.patch<Params>('/api/parametres', { ...p, heures_proposees: heures }))
    if (r) { setP(r); setOk(true); setTimeout(() => setOk(false), 2000) }
  }

  return (
    <form onSubmit={enregistrer}>
      <EnTete titre="Paramètres"><button className="principal" disabled={enCours}>{ok ? 'Enregistré ✓' : 'Enregistrer'}</button></EnTete>
      <Erreur message={erreur} />
      <section className="carte">
        <div className="ligne-champs">
          {CHAMPS.map(({ cle, libelle, aide, long }) => (
            <Champ key={cle} libelle={libelle} aide={aide} large={long}>
              {long
                ? <textarea rows={3} value={String(p[cle] ?? '')} onChange={(e) => setP({ ...p, [cle]: e.target.value })} />
                : <input value={String(p[cle] ?? '')} onChange={(e) => setP({ ...p, [cle]: e.target.value })} />}
            </Champ>
          ))}
          <Champ libelle="Validité d'un devis (jours)">
            <input type="number" min={1} max={365} value={Number(p.validite_devis_jours)} onChange={(e) => setP({ ...p, validite_devis_jours: Number(e.target.value) })} />
          </Champ>
          <Champ libelle="Heures proposées sur la fiche" aide="Séparées par des virgules.">
            <input value={Array.isArray(p.heures_proposees) ? p.heures_proposees.join(', ') : String(p.heures_proposees)}
              onChange={(e) => setP({ ...p, heures_proposees: e.target.value })} />
          </Champ>
        </div>
      </section>
    </form>
  )
}
