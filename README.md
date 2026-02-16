# Budgeting App (100% local / offline)

Application locale de gestion de budget personnel basée sur **Flask + SQLite**.

## Fonctionnalités

- Dashboard avec:
  - total dépenses
  - total revenus
  - solde
  - répartition par catégories principales (ou secondaires)
  - drill-down par clic sur catégorie principale
  - histogramme mensuel
- Import CSV bancaire avec mapping automatique (`date`, `description`, `montant`, `catégorie`).
- Catégorisation modifiable transaction par transaction ou en masse.
- Exclusion des transactions des statistiques.
- Split ratio (0-100%) pour ne prendre en compte qu'une partie d'un montant.
- Persistance locale SQLite (`data/budget.db`).
- Export CSV filtré et backup JSON.
- Reset base.
- Mode sombre optionnel.

## Architecture

- `app.py` : serveur Flask + endpoints API.
- `db.py` : schéma et connexion SQLite.
- `services.py` : logique métier (import, filtres, stats, updates).
- `categorization.py` : catégorisation automatique via mots-clés.
- `categorization_rules.json` : règles éditables.
- `templates/index.html`, `static/*` : UI.

## Installation

```bash
./install.sh
```

## Lancement

```bash
./run.sh
```

Puis ouvrir `http://127.0.0.1:5000`.

## Format CSV attendu

Le format bancaire principal pris en charge est un CSV **séparé par `;`** avec en-têtes de type :

- `Date de l'opération`
- `Catégorie`
- `Sous catégorie`
- `Montant`
- `Commentaire` + `Détail 1..6` (utilisés pour construire la description)

L'import gère aussi la détection automatique de variantes de noms de colonnes (date/amount/category...).

## Règles de catégorisation

Éditez `categorization_rules.json` pour ajouter/modifier des mots-clés.

Exemple:

```json
{
  "loyer": "Logement",
  "uber": "Transport"
}
```

## Persistance et sauvegarde

- Base: `data/budget.db`
- Backup JSON via l'interface (`Import > Backup JSON`) dans `data/backup.json`
- Export CSV filtré via l'interface (`Import > Exporter CSV filtré`)

## Contraintes offline

- Aucune donnée n'est envoyée à un service externe.
- Aucune dépendance cloud côté runtime.
- Toutes les données restent en local.

## Notes performance

- Index SQLite sur date/catégorie/exclusion.
- Liste transactions limitée à 1000 lignes en affichage pour garder l'UI réactive.
- Le backend reste compatible avec des volumes >10k transactions.


## Gestion des catégories

- Onglet **Catégories** pour ajouter/supprimer des catégories principales et secondaires.
- Une sous-catégorie est stockée sous la forme `Parent / Enfant`.
- La suppression d'une catégorie réaffecte automatiquement les transactions concernées à `À catégoriser`.
