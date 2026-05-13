# Weather Monitor Dashboard

Dashboard Streamlit déployé sur Google Cloud Run pour monitorer les données météo indoor/outdoor en temps réel.

## Structure

```
dashboard/
├── app.py              # Interface Streamlit principale
├── bigquery_client.py  # Requêtes BigQuery
├── weather_api.py      # API OpenWeatherMap
├── config.py           # Variables de configuration
├── requirements.txt    # Dépendances Python
└── Dockerfile          # Pour Cloud Run
```

## Variables d'environnement

À configurer dans Cloud Run (ne jamais mettre dans le code) :

| Variable | Description | Exemple |
|---|---|---|
| `GCP_PROJECT_ID` | ID du projet Google Cloud | `project-weather-494814` |
| `BQ_DATASET_ID` | Dataset BigQuery | `weather_data` |
| `BQ_TABLE_ID` | Table BigQuery | `sensor_data` |
| `OPENWEATHER_API_KEY` | Clé API OpenWeatherMap | `abc123...` |
| `CITY` | Ville pour la météo | `Lausanne` |
| `COUNTRY_CODE` | Code pays ISO | `CH` |

## Déploiement sur Google Cloud Run

### 1. Authentification
```bash
gcloud auth login
gcloud config set project project-weather-494814
```

### 2. Build & Deploy (en une commande)
```bash
cd dashboard/

gcloud run deploy weather-dashboard \
  --source . \
  --region europe-west6 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=project-weather-494814,BQ_DATASET_ID=weather_data,BQ_TABLE_ID=sensor_data,OPENWEATHER_API_KEY=VOTRE_CLE,CITY=Lausanne,COUNTRY_CODE=CH \
  --memory 512Mi \
  --cpu 1
```

### 3. Vérifier le déploiement
```bash
gcloud run services describe weather-dashboard --region europe-west6
```

## Fonctionnalités

- ✅ Données temps réel depuis BigQuery (refresh auto 60s)
- ✅ Alertes si humidité < 40% ou AQI > 150
- ✅ Météo extérieure via OpenWeatherMap
- ✅ Prévisions 5 jours
- ✅ Graphiques historiques (6h / 12h / 24h / 48h / 7 jours)
- ✅ Statistiques journalières (7 derniers jours)
- ✅ Design sombre responsive

## Développement local

```bash
pip install -r requirements.txt

# Avec un fichier .env ou en exportant les variables :
export OPENWEATHER_API_KEY=votre_cle
export GCP_PROJECT_ID=project-weather-494814

streamlit run app.py
```
