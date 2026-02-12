# Budgeting App (100% local / offline)

Application locale de gestion de budget personnel basée sur **Flask + SQLite**.

## Fonctionnalités

- Dashboard avec:
  - total dépenses
  - total revenus
  - solde
  - répartition par catégorie
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

L'import essaie de détecter automatiquement les colonnes suivantes (insensibles à la casse):

- Date: `date`, `operation date`, `transaction date`
- Description: `description`, `label`, `libellé`, `libelle`
- Montant: `amount`, `montant`, `value`
- Catégorie (optionnelle): `category`, `catégorie`, `categorie`

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
