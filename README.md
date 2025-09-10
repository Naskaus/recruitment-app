# OS Agency — Master README (v1.1)

## 1) Overview / Purpose
OS Agency est une application SaaS pour agences de talents (recruitment, dispatch, payroll, performance). Objectif: livrer une v1.0 robuste, rapide et documentée, et poser les bases d’une plateforme scalable.

Rôles du “Triangle IA”
- Seb (Grand Architecte): vision, arbitrages, décisions finales.
- Gemini (Stratège SaaS): organise, priorise, aide aux décisions, rédige ce README maître.
- Windsurf (Implémenteur IDE): exécute les mini-prompts, code, et fournit les diffs/analyses.

Ce README est cumulatif: à chaque session, on enrichit, sans rien perdre. Il sert aussi de “prompt mémoire” permanent du projet.

Statuts
- Current Version: v1.0 Candidate
- Immediate Goal: audit final et lancement
- Ultimate Goal: produit SaaS prêt pour la prod (rapide, sécurisé, scalable)

---

## 2) Architecture & Tech Stack

### Backend
- Python 3.10+
- Flask (Application Factory + Blueprints)
- SQLAlchemy + Flask-Migrate
- Services métier: `app/services/payroll_service.py`, `app/services/agency_management_service.py`

### Frontend
- Jinja2 templates
- CSS custom principal: `app/static/css/style.css`
- JS: centralisé (refactor en modules planifié post-v1)

### Base de données
- Dev: SQLite (config via `SQLALCHEMY_DATABASE_URI`)
- Prod: Postgres

### Déploiement
- PythonAnywhere (web server)
- Variables d’environnement: `.env` (prod) / `.env.local` (dev)

### Structure (extraits pertinents)
- `app/admin/routes.py`
- `app/payroll/routes.py`
- `app/services/agency_management_service.py`
- `app/templates/admin/manage_agencies.html`
- `app/templates/payroll.html`
- `app/templates/payroll/dashboard.html`
- `app/templates/payroll/_dashboard_content.html`
- `app/static/css/style.css`
- `docs/` (notes techniques)

---

## 3) Installation & Démarrage

### Prérequis
- Python 3.10+
- Virtualenv recommandé

### Étapes
- Créer l’environnement virtuel et installer:
  - Windows: `py -m venv .venv && .venv\Scripts\activate && pip install -r requirements.txt`
- Configurer `.env.local` (dev) ou `.env` (prod):
  - `SQLALCHEMY_DATABASE_URI=sqlite:///data/recruitment-dev.db` (exemple)
  - `SECRET_KEY=...`
  - `UPLOAD_FOLDER=...` (utilisé pour exports)
- Lancer:
  - `flask run` ou `python run.py`
- Accès:
  - App: `http://127.0.0.1:5000`

---

## 4) Fonctionnalités & Endpoints Clés

### Manage Agencies
- Page: `GET /admin/manage_agencies` (rôle webdev requis)
- Export JSON (fichier + download):
  - `POST /admin/api/agencies/<agency_id>/export`
  - `GET  /admin/api/agencies/<agency_id>/export/download/<filename>`
- Export & Download immédiat (JSON inline):
  - `GET /admin/download_agency_db/<agency_id>`
- Import JSON:
  - `POST /admin/api/agencies/import`
- Soft delete / Reactivation:
  - `POST /admin/delete_agency/<agency_id>`
  - `POST /admin/reactivate_agency/<agency_id>`
- Force delete (purge définitive avec sauvegarde sqlite si applicable):
  - `POST /admin/force_delete_agency/<agency_id>`

#### Correctif critique “download DB”
- Fichier: `app/services/agency_management_service.py`
- Méthode: `export_agency_data_to_json()`
- Bug d’origine: échec d’écriture du fichier si le répertoire complet n’existait pas → téléchargement impossible.
- Fix ajouté: création explicite du répertoire parent du fichier exporté avant l’écriture:
  - `export_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'exports')`
  - `os.makedirs(export_dir, exist_ok=True)`
  - `export_dir_from_path = os.path.dirname(filepath); os.makedirs(export_dir_from_path, exist_ok=True)`

#### Snippet bouton HTML (Manage Agencies)
- Fichier: `app/templates/admin/manage_agencies.html`
```html
<a href="{{ url_for('admin.download_agency_db', agency_id=agency.id) }}"
   class="btn btn-sm btn-outline-info mx-1" title="Download DB">
  <!-- Icône SVG -->
</a>
```

#### Snippet route Flask (Download DB direct)
- Fichier: `app/admin/routes.py`, fonction `download_agency_db()`
  - Vérifie l’agence (active, non supprimée)
  - Exécute `AgencyManagementService.export_agency_data_to_json(agency_id)`
  - Retourne le JSON en pièce jointe via `Content-Disposition`

### Payroll & Performance
- Page principale Payroll: `GET /payroll/`
  - Filtres: manager, venue, type de contrat, statut, période
  - Export PDF: `GET /payroll/pdf`
  - “Performance Report” (Dashboard): `GET /payroll/dashboard` et `/payroll/dashboard/pdf`
- Optimisation majeure N+1:
  - Traitement par lot des `ContractCalculations`
  - Réduction drastique des requêtes (cf. Section Performance)
- UI mobile:
  - Table “cardifiée” en mobile: `thead` masqué + `data-label`
  - Actions sur mobile: boutons en 2 colonnes tap-friendly

### Performance Dashboard
- KPI Cards responsive: Mobile 2x2, ≥1024px 4 colonnes
- Detailed Contracts:
  - Table compacte, overflow horizontal conditionnel
  - Dates “2 lignes” (ex: “10” / “SEP”)

---

## 5) Sécurité & Permissions
- Auth via Flask-Login
- Décorateurs: `@login_required`, `@webdev_required`, `@role_required('WEBDEV')`
- “Manage Agencies” réservé aux webdev

---

## 6) Performance & Diagnostics

### N+1 / Optimisations (Payroll)
- Contexte: lazy-loading multiples + recalculs redondants
- Corrections: batch processing des `ContractCalculations`; pré-chargements ciblés
- Résultat: réduction majeure des requêtes (jusqu’à ~99% dans certains scénarios)

### Endpoint diagnostic
- `GET /admin/debug-vitals` → hash de déploiement + latence DB de base

---

## 7) UI/UX – Améliorations Mobiles

### Dashboard (`app/static/css/style.css`)
- `.summary-cards`:
  - Mobile: `grid-template-columns: repeat(2, 1fr); gap: 1rem;`
  - ≥1024px: `repeat(4, 1fr); gap: 2rem;`
- `.detailed-table` compaction:
  - ≤992px: `font-size: 0.7rem`, `padding: 4px 6px`, headers plus petits
  - ≤768px: `font-size: 0.6rem`, `padding: 3px 5px`, badges réduits
- Dates 2 lignes: `.date-2line` (jour) + `.date-2line-mon` (mois)
- Overflow horizontal: wrapper `div.overflow-x-auto` autour de la table

### Payroll
- “Cardification” mobile: `thead` masqué, `data-label` sur `td`
- Actions: `.actions .button { flex: 1 1 45%; min-height: 44px; }`
- Filtres: `.filter-actions` mobile-friendly
- Note: 2 blocs CSS proches pour `.payroll-table`; le dernier prévaut (à fusionner plus tard)

---

## 8) Version History & Sprint Notes (extraits)
- v0.9.9.x → v1.0 (candidate):
  - Performance / Latence Payroll: corrigée
  - Dashboard + PDF
  - Manage Agencies: export/import JSON, soft/force delete, download DB
  - Déploiement PythonAnywhere: check-lists et WSGI validés

---

## 9) Déploiement (PythonAnywhere)
- `.env` à configurer (non commit)
- Onglet Web: vérifier Source code, Working directory, Venv, WSGI
- WSGI: voir exemple historique dans `app/README.md.bak` (ou docs)
- En cas de corruption: recréer l’app (Phoenix Plan)

---

## 10) Tests & Qualité
- `pytest` (tests à étendre post-v1)
- Lints templates: quelques inline-styles déclenchent des warnings (non bloquants)
- Conventions: Blueprints, Services métier dédiés, CSS structuré

---

## 11) Roadmap (post-v1)
- Refactor JS modulaire (split `app.js`)
- Unifier CSS responsive Payroll (supprimer doublons)
- Alias CSS `.overflow-x-auto` si nécessaire
- CI/CD + suite de tests
- Modernisation UI/UX progressive

---

## 12) Annexes — Extraits utiles

### Export JSON (service)
- `app/services/agency_management_service.py` → `export_agency_data_to_json()`

### Export via API (routes)
- `POST /admin/api/agencies/<agency_id>/export` → JSON `{ success, filename, filepath, statistics }`
- `GET  /admin/api/agencies/<agency_id>/export/download/<filename>` → téléchargement

### Download DB direct (JSON inline)
- `GET /admin/download_agency_db/<agency_id>`

### Dashboard — Detailed Contracts
- `_dashboard_content.html` + `style.css` (media queries, dates 2 lignes)

### Payroll
- `payroll.html` (table principale + wrapper, actions, cardification mobile)
