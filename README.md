# Système de Gestion d'Entreprise (Flask)

Application API Flask pour la gestion des employés, départements, rôles/permissions (RBAC), paie, présences, congés, contrats et reporting.

## Stack

- Flask
- SQLite (Flask-SQLAlchemy)
- pandas (statistiques)
- pydantic (validation)
- JWT + bcrypt (sécurité)
- reportlab (export PDF fiche de paie)

## Fonctionnalités couvertes

- Gestion des employés: CRUD, statut, département, rôle, contacts, photo
- Gestion des départements: création, budget, assignation manager, listing employés
- Gestion des rôles & permissions: rôles + mapping permissions
- Gestion des salaires: calcul automatique du salaire net + historique
- Gestion des présences: check-in/check-out + heures travaillées
- Gestion des congés: demande + validation manager
- Gestion des contrats: CDI/CDD/Stage + document
- Reporting & statistiques: masse salariale, salaire moyen, employés/département, taux d'absentéisme
- Sécurité: JWT, hash bcrypt, logs d’activité
- Comptes agents automatiques: matricule généré + compte utilisateur lié
- Politique mot de passe: mot de passe par défaut commun + changement obligatoire à la première connexion

## Architecture POO

- **Encapsulation**: entités métier avec attributs privés dans `app/models/entities.py`
- **Héritage**: `EmployeeEntity` hérite de `Person`, spécialisations `DeveloperEntity`, `ManagerEntity`, `HREntity`
- **Agrégation**: `DepartmentEntity` agrège des employés, `PayrollEntity` agrège un employé

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

L'API démarre sur `http://127.0.0.1:5000`.

## Interface Web avancée

Une interface professionnelle animée est disponible à l'adresse:

- `http://127.0.0.1:5000/dashboard`

Fonctionnalités UI:

- Login JWT intégré
- Tableau de bord KPI animé
- Graphiques dynamiques (départements + congés)
- Interfaces complètes: employés, départements, rôles, salaires, présences, congés, contrats, reporting
- Formulaires d'actions métier connectés à l'API (création rapide)
- Interface dynamique par rôle/permissions (RBAC frontend + backend)
- Effets visuels avancés (glassmorphism, micro-interactions, transitions)

## Gestion des comptes agents

- Lorsqu'un agent est créé (`POST /api/employees`), le système génère automatiquement:
  - un `matricule` (utilisé comme identifiant de connexion),
  - un compte utilisateur lié à l'employé,
  - le rôle de sécurité basé sur le rôle de l'employé.
- Mot de passe par défaut (configurable): `DEFAULT_AGENT_PASSWORD` (par défaut: `Agent@123`).
- Au premier login, l'utilisateur doit changer son mot de passe via `POST /api/auth/change-password`.

Nouveaux endpoints Auth:

- `GET /api/auth/me` (profil + rôle + permissions + état de changement mot de passe)
- `POST /api/auth/change-password`

## Lancement rapide (PowerShell)

Script prêt à l'emploi:

- `scripts/start_app.ps1`

Commandes:

```powershell
# Vérifier l'environnement
.\scripts\start_app.ps1 -CheckOnly

# Lancer en mode normal
.\scripts\start_app.ps1

# Lancer en mode debug
.\scripts\start_app.ps1 -DebugMode

# Lancer en mode clean (stop anciennes instances + suppression .run.lock)
.\scripts\start_app.ps1 -Clean
```

## Lancement rapide (double-clic / CMD)

- `start_app.bat` : mode normal (clean start)
- `start_app.bat debug` : mode debug (clean start)

## Seed de données

Pour charger un jeu de données complet (départements, employés, utilisateurs, paie, présences, congés, contrats):

```bash
.venv\Scripts\python.exe scripts\seed_data.py
```

Comptes générés:

- `superadmin / superadmin123`
- `adminrh / adminrh123`
- `manager1 / manager123`
- `employe1 / employe123`

## Collection Postman

Importer le fichier:

- `postman/Enterprise-Management.postman_collection.json`
- `postman/Enterprise-Management-Full.postman_collection.json` (version CRUD complète)

Ordre conseillé:

1. Health Check
2. Login SuperAdmin (stocke automatiquement le token)
3. Tests des modules (Employees, Payrolls, Reports...)

## Endpoints principaux

### Auth

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/change-password`

### Comptes Agents

- `GET /api/accounts`
- `PATCH /api/accounts/<user_id>/reset-password`
- `PATCH /api/accounts/<user_id>/role`
- `PATCH /api/accounts/<user_id>/status`
- `GET /api/accounts/activity` (filtres: `username`, `action`, `start_date`, `end_date`)
- `GET /api/accounts/activity/export.csv` (mêmes filtres)
- `GET /api/accounts/activity/export.pdf` (mêmes filtres)

### Employés

- `GET /api/employees`
- `POST /api/employees`
- `PUT /api/employees/<id>`
- `DELETE /api/employees/<id>`

### Départements

- `GET /api/departments`
- `POST /api/departments`
- `PATCH /api/departments/<department_id>/manager/<manager_id>`

### Rôles

- `GET /api/roles`
- `POST /api/roles`
- `PATCH /api/roles/<role_id>/permissions`

### Paie

- `GET /api/payrolls`
- `POST /api/payrolls`
- `GET /api/payrolls/<payroll_id>/payslip`

### Présences

- `GET /api/attendances`
- `POST /api/attendances/checkin`
- `POST /api/attendances/checkout`

### Congés

- `GET /api/leaves`
- `POST /api/leaves`
- `PATCH /api/leaves/<leave_id>/approval`

### Contrats

- `GET /api/contracts`
- `POST /api/contracts`

### Reporting

- `GET /api/reports/stats`

## Permissions RBAC seedées

- Voir employés
- Modifier employés
- Voir salaires
- Exporter rapports
- Valider congés

Rôles seedés automatiquement: `SuperAdmin`, `Admin RH`, `Manager`, `Employé`.

## Exemple de flux rapide

1. Créer un utilisateur:
```json
POST /api/auth/register
{
  "username": "admin",
  "password": "admin123",
  "role_name": "SuperAdmin"
}
```

2. Se connecter et récupérer `access_token`.
3. Utiliser `Authorization: Bearer <token>` pour les appels protégés.

## Base de données

Fichier SQLite: `enterprise.db` (créé automatiquement au premier démarrage).
