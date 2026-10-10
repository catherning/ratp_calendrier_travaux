# Déploiement GCP

Sans Terraform ni Cloud Scheduler. Exécuter les commandes depuis la racine du
dépôt avec Bash, Python 3.10+, `gcloud`, curl et un moteur de conteneurs.
Le projet doit exister et être rattaché à un compte de facturation.

## Pourquoi Bash et Python ?

Bash orchestre les commandes `gcloud` ; Python valide le JSON et construit
les requêtes des API d'alertes. Cela évite de manipuler du JSON à coups de
substitutions shell. Les points d'entrée restent les scripts `.sh` :

| Script | Rôle |
|---|---|
| `bootstrap-wif.sh` | Accès GitHub et identité du provisionneur |
| `provision.sh` | Ressources puis création des deux services |
| `release.sh` | Déploiement des images et smoke tests |
| `upload-graphs.sh` | Validation et import des graphes |
| `alerts.sh` | Budget et alertes |

`common.sh` mutualise configuration, contrôles et commandes de déploiement.
Chaque script expose une fonction `main` qui résume ses étapes.

## Architecture

- **Frontend public** : Next.js, port 3000, `NEXT_PUBLIC_API_URL=/api`.
  Le proxy serveur appelle le backend avec un jeton OIDC et n'expose pas `/admin/*`.
- **Backend protégé par IAM** : FastAPI, port 8000, secrets `NAVITIA_API_KEY`
  et `ADMIN_API_KEY` dans Secret Manager.
- **Bucket privé et versionné** : graphes JSON, téléchargés à la demande dans
  `/tmp/line_graphs`. Artifact Registry stocke les images.
- **GitHub Actions via WIF** : comptes distincts pour provisionnement et releases,
  sans clé de compte de service. Le frontend n'a pas accès aux secrets.

## 1. Configuration et accès GitHub

```bash
cp deploy/config.example.json deploy/config.json
# Remplacer tous les REPLACE_* : projet, région, dépôt GitHub, budget, email…
python3 deploy/config.py deploy/config.json
gcloud auth login
bash deploy/bootstrap-wif.sh deploy/config.json
```

Le bootstrap nécessite un opérateur autorisé à gérer les ressources, IAM et
le budget. La confiance WIF est limitée au dépôt, à la branche et aux
environnements configurés.

Dans GitHub :

- Créer les environnements **provisioning** et **production**, avec approbation
  et restriction à la branche de déploiement.
- Définir la variable du dépôt `DEPLOY_BRANCH`.
- Définir `DEPLOY_CONFIG_JSON` dans les deux environnements, avec le même JSON.
- Définir `NEXT_PUBLIC_CARTO_API_KEY` dans **production** : clé publique,
  restreinte au domaine du site chez le fournisseur.
- Si la branche n'est pas `main`, modifier aussi `push.branches` dans
  [release-gcp.yml](../.github/workflows/release-gcp.yml).

La configuration ne contient aucun secret. Ne pas y ajouter de clés API.

## 2. Premier provisionnement

Lancer le workflow **Provision GCP**, phase `resources`, ou :

```bash
bash deploy/provision.sh deploy/config.json resources
```

Cette étape configure les API, comptes/IAM, bucket, registre, conteneurs de
secrets, alertes et budget. Ajouter ensuite les versions des deux secrets via
Secret Manager ou `gcloud secrets versions add --data-file=...`, depuis une
source locale protégée. Ne pas transmettre leur contenu dans les arguments,
la configuration ou les entrées GitHub.

Valider et charger les graphes, dont la **ligne 2** utilisée par le smoke test :

```bash
python3 deploy/validate-graphs.py line_graphs
bash deploy/upload-graphs.sh deploy/config.json line_graphs
```

Les noms SHA-256 et enveloppes JSON sont conservés. Un objet existant fait
échouer l'import ; ajouter `--replace` pour un remplacement intentionnel,
protégé par une précondition de génération.

Construire et pousser les premières images applicatives :

- Backend : `Dockerfile` à la racine.
- Frontend : `frontend/Dockerfile`, arguments `NEXT_PUBLIC_API_URL=/api` et
  `NEXT_PUBLIC_CARTO_API_KEY`.
- Registre : `REGION-docker.pkg.dev/PROJECT/REPOSITORY`.
- Tags : `backend:COMMIT_SHA` et `frontend:COMMIT_SHA`, puis récupérer les digests.

Créer les services via le workflow **Provision GCP**, phase `services`, ou :

```bash
bash deploy/provision.sh deploy/config.json services \
  REGION-docker.pkg.dev/PROJECT/REPOSITORY/backend@sha256:DIGEST \
  REGION-docker.pkg.dev/PROJECT/REPOSITORY/frontend@sha256:DIGEST
```

Les scripts peuvent être relancés pour réconcilier les ressources gérées.
Ils ne nettoient pas les permissions préexistantes : vérifier les accès larges
ou publics, particulièrement dans un projet partagé.

## 3. Releases

Pousser sur la branche configurée ou lancer **Release GCP** manuellement.
Le workflow construit les images, puis déploie le backend et le frontend par
digest. Les tags sont immuables : une modification des paramètres de build
nécessite un nouveau commit. Après rotation d'un secret, redéployer.

Les smoke tests vérifient IAM, frontend, proxy, graphe de ligne 2 et rejet des
routes admin, sans appeler Navitia. Le déploiement n'est pas atomique ; pour
revenir à des images connues :

```bash
bash deploy/release.sh deploy/config.json "$BACKEND_DIGEST" "$FRONTEND_DIGEST"
```

## Alertes et limites

- Budget mensuel sur **tout le projet** : dépenses réelles à 50/80/100 %,
  prévision à 100 %, notifications email.
- Trafic frontend et erreurs 5xx des deux services : seuils en
  **requêtes/seconde**, agrégés sur toutes les révisions, dépassés pendant 5 min.
- Pour les reconfigurer : `bash deploy/alerts.sh deploy/config.json`.
  Vérifier la réception des emails. Les alertes ne sont **pas un plafond de dépenses**.
- Le cache local est éphémère et **sans revalidation**. Après remplacement externe
  des graphes, créer une nouvelle révision backend. Éviter les refreshs admin
  concurrents : verrou distribué et écritures conditionnelles applicatives différés.
- L'ancien workflow [configure-cloud-scheduler.yml](../.github/workflows/configure-cloud-scheduler.yml)
  est obsolète : ne pas l'utiliser. Aucun Scheduler n'est modifié.

## Validation hors ligne

```bash
for file in deploy/*.sh; do bash -n "$file"; done
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s deploy -p 'test_*.py'
```

Ces tests n'appellent pas GCP. Provisionnement réel, WIF, images et notifications
restent à vérifier dans le projet cible ; aucun déploiement cloud n'a été effectué.
