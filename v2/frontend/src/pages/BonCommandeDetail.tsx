import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, formatInstant, ouvrirPdf } from '../api'
import { Champ, EnTete, Erreur, Statut, useAction, useCharger } from '../composants/ui'
import { STATUT_COULEUR, type BonCommande } from './Achats'

type Ligne = { boisson_id: string | null; nom: string; unite: string | null; quantite: number; prix_achat: string }

const ACTIONS: Record<string, [string, string, boolean?][]> = {
  brouillon: [['envoye', 'Marquer « envoyé au fournisseur »', true], ['annule', 'Annuler']],
  envoye: [['recu', 'Marquer « reçu »', true], ['brouillon', 'Repasser en brouillon'], ['annule', 'Annuler']],
  recu: [['envoye', 'Annuler la réception']],
  annule: [['brouillon', 'Rétablir en brouillon']],
}

export default function BonCommandeDetail() {
  const { id } = useParams()
  const nouveau = id === 'nouveau'
  const naviguer = useNavigate()
  const [bon, setBon] = useState<BonCommande | null>(null)
  const [lignes, setLignes] = useState<Ligne[]>([])
  const [fournisseurId, setFournisseurId] = useState('')
  const [note, setNote] = useState('')
  const { donnees: fournisseurs } = useCharger(() => api.get<{ id: string; nom: string }[]>('/api/achats/fournisseurs'))
  const { donnees: boissons } = useCharger(() => api.get<{ id: string; nom: string; unite: string | null }[]>('/api/achats/boissons'))
  const { enCours, erreur, setErreur, lancer } = useAction()

  const appliquer = (b: BonCommande) => {
    setBon(b)
    setFournisseurId(b.fournisseur_id ?? '')
    setNote(b.note ?? '')
    setLignes(b.lignes.map((l) => ({ boisson_id: l.boisson_id, nom: l.libelle, unite: l.unite, quantite: l.quantite, prix_achat: l.prix_achat?.replace(/[^\d,]/g, '') ?? '' })))
  }
  useEffect(() => {
    if (!nouveau) api.get<BonCommande>(`/api/achats/commandes/${id}`).then(appliquer).catch((e) => setErreur(e.message))
  }, [id, nouveau, setErreur])

  const modifiable = nouveau || bon?.statut === 'brouillon'
  const corps = { fournisseur_id: fournisseurId || null, note, lignes: lignes.filter((l) => l.nom.trim() && l.quantite > 0).map((l) => ({ boisson_id: l.boisson_id, nom: l.nom, unite: l.unite, quantite: l.quantite, prix_achat: l.prix_achat })) }
  const enregistrer = async () => {
    const r = await lancer(() => nouveau ? api.post<BonCommande>('/api/achats/commandes', corps)
      : api.patch<BonCommande>(`/api/achats/commandes/${id}`, { ...corps, version: bon!.version }))
    if (r) { if (nouveau) naviguer(`/achats/commandes/${r.id}`, { replace: true }); else appliquer(r) }
  }
  const statut = async (cible: string) => { const r = await lancer(() => api.post<BonCommande>(`/api/achats/commandes/${id}/statut`, { statut: cible })); if (r) appliquer(r) }
  const choisirBoisson = (i: number, nom: string) => {
    const b = boissons?.find((x) => x.nom === nom)
    setLignes(lignes.map((l, j) => (j === i ? { ...l, nom, boisson_id: b?.id ?? null, unite: b?.unite ?? l.unite } : l)))
  }

  return (
    <>
      <EnTete titre={nouveau ? 'Nouveau bon de commande' : `Bon de commande ${bon?.numero ?? ''}`}
        sousTitre={bon && <><Statut statut={STATUT_COULEUR[bon.statut]} libelle={bon.statut_libelle} />{bon.envoye_le && ` envoyé le ${formatInstant(bon.envoye_le)}`}{bon.recu_le && ` · reçu le ${formatInstant(bon.recu_le)}`}</>}>
        {bon && <>
          <button onClick={() => ouvrirPdf(`/api/achats/commandes/${bon.id}/pdf`)}>PDF</button>
          <button onClick={() => ouvrirPdf(`/api/achats/commandes/${bon.id}/csv`)}>CSV</button>
          {bon.fournisseur_email && <a className="bouton" href={`mailto:${bon.fournisseur_email}?subject=${encodeURIComponent(`Commande ${bon.numero}`)}`}>Écrire au fournisseur</a>}
        </>}
        {modifiable && <button className="principal" onClick={enregistrer} disabled={enCours}>Enregistrer</button>}
      </EnTete>
      <Erreur message={erreur} />
      <section className="carte">
        <div className="ligne-champs">
          <Champ libelle="Fournisseur">
            <select value={fournisseurId} disabled={!modifiable} onChange={(e) => setFournisseurId(e.target.value)}>
              <option value="">— à choisir —</option>
              {fournisseurs?.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
            </select>
          </Champ>
          <Champ libelle="Remarques pour le fournisseur" large><textarea rows={2} value={note} disabled={!modifiable} onChange={(e) => setNote(e.target.value)} /></Champ>
        </div>
        <datalist id="boissons">{boissons?.map((b) => <option key={b.id} value={b.nom} />)}</datalist>
        <table className="tableau lignes">
          <thead><tr><th>Article</th><th>Unité</th><th className="droite">Quantité</th><th className="droite">Prix d'achat unitaire</th><th /></tr></thead>
          <tbody>
            {lignes.map((l, i) => (
              <tr key={i}>
                <td><input list="boissons" value={l.nom} disabled={!modifiable} onChange={(e) => choisirBoisson(i, e.target.value)} /></td>
                <td><input value={l.unite ?? ''} disabled={!modifiable} onChange={(e) => setLignes(lignes.map((x, j) => (j === i ? { ...x, unite: e.target.value } : x)))} /></td>
                <td className="etroit"><input type="number" min={1} value={l.quantite} disabled={!modifiable} onChange={(e) => setLignes(lignes.map((x, j) => (j === i ? { ...x, quantite: Number(e.target.value) } : x)))} /></td>
                <td className="etroit"><input inputMode="decimal" placeholder="auto" value={l.prix_achat} disabled={!modifiable} onChange={(e) => setLignes(lignes.map((x, j) => (j === i ? { ...x, prix_achat: e.target.value } : x)))} /></td>
                <td>{modifiable && <button className="lien" onClick={() => setLignes(lignes.filter((_, j) => j !== i))}>retirer</button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {modifiable && <button onClick={() => setLignes([...lignes, { boisson_id: null, nom: '', unite: null, quantite: 1, prix_achat: '' }])}>+ Ligne</button>}
        {bon && <p className="droite">Total d'achat : <strong>{bon.total_achat}</strong>{bon.prix_manquants && <span className="muet"> (certains prix d'achat manquent)</span>}</p>}
        <p className="aide">Le prix d'achat vide est repris de la fiche boisson pour ce fournisseur.</p>
      </section>
      {bon && (
        <section className="carte">
          <h2>Suivi</h2>
          <div className="ligne-champs">
            {(ACTIONS[bon.statut] ?? []).map(([cible, libelle, principal]) => (
              <button key={cible} className={principal ? 'principal' : ''} disabled={enCours} onClick={() => statut(cible)}>{libelle}</button>
            ))}
          </div>
          <p className="aide">L'outil n'envoie rien : envoyer le PDF ou le CSV au fournisseur, puis marquer le bon « envoyé ».</p>
        </section>
      )}
    </>
  )
}
