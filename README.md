# Anonymiq: Modulaire PII-detectie voor Nederlandse tekst

Anonymiq is een modulaire API-service voor het detecteren en anonimiseren van privacygevoelige informatie (PII) in Nederlandse tekst. De service is gebaseerd op [Microsoft Presidio](https://github.com/microsoft/presidio) en biedt ondersteuning voor verschillende NLP-modellen (zoals spaCy of HuggingFace transformers) zonder dat de API of logica hoeft te worden aangepast.

## Installatie & Gebruik

Zie ook:
- Gebruikshandleiding met Swagger-stappen: `docs/use-cases.md`
- API voorbeelden (curl): `docs/api-examples.md`
- Productie Swagger: https://api.openanonymiser.commonground.nu/api/v1/docs
- Staging Swagger: https://api.openanonymiser.accept.commonground.nu/api/v1/docs

### 1. Lokaal draaien (voor ontwikkeling)

Installeer dependencies en start de API:

```bash
uv venv
uv sync
uv run api.py
```

De API is nu bereikbaar op [http://localhost:8080/api/v1/docs](http://localhost:8080/api/v1/docs) (Swagger UI).

### 2. Docker Compose (aanbevolen)

Start beide services (API + UI) met docker-compose:

```bash
docker-compose up -d
```

Na opstarten zijn de services bereikbaar op:
- **API**: [http://localhost:8001/api/v1/docs](http://localhost:8001/api/v1/docs) (Swagger UI)
- **UI**: [http://localhost:8002](http://localhost:8002) (Web interface)

### Welke modellen voor welke entiteiten?
- Pattern recognizers (regelgebaseerd via Presidio): `IBAN`, `PHONE_NUMBER`, `EMAIL`
- NLP (NER – SpaCy of Transformers): `PERSON`, `LOCATION`, `ORGANIZATION`
- `ADDRESS`: via NLP (best‑effort), geen pattern‑recognizer; dekking is model‑afhankelijk

Kies patterns voor “vormvaste” entiteiten, en NLP voor “vrije‑tekst” entiteiten.

### 3. Individuele Docker containers

Bouw het backend image:

```bash
docker build -t anonymiq .
```

Start alleen de backend container:

```bash
docker run -d -p 8001:8080 --name anonymiq anonymiq
```

API bereikbaar op [http://localhost:8001/api/v1/docs](http://localhost:8001/api/v1/docs)

### 4. Kubernetes met Helm (productie)

**⚠️ KRITIEKE VEREISTE: PERSISTENT STORAGE** 

Anonymiq vereist persistent storage voor:
- SQLite database (`/app/openanonymiser.db` — de bestandsnaam blijft bewust
  ongewijzigd; het bestand staat al op de PVC en een hernoeming zou stilzwijgend
  een lege database aanmaken)
- Geüploade PDF-bestanden (`/app/temp/source/`) 
- Geanonimiseerde bestanden (`/app/temp/anonymized/`)
- Applicatielogs (`/app/logs/`)

**Zonder PVC gaan alle gegevens verloren bij pod restart!**

Installeer de API service in Kubernetes met Helm:

```bash
# Installeer de chart
helm install openanonymiser ./charts/openanonymiser

# Of met custom values
helm install openanonymiser ./charts/openanonymiser -f values-production.yaml

# Upgrade bestaande deployment
helm upgrade openanonymiser ./charts/openanonymiser
```

#### Helm configuratie

Belangrijke configureerbare waarden in `values.yaml`:

```yaml
# Image configuratie
image:
  repository: mwest2020/openanonymiser
  tag: latest

# Ingress voor externe toegang
ingress:
  enabled: true
  className: nginx
  hosts:
    - host: "api.openanonymiser.example.com"

# KRITIEK: Persistent storage configuratie
persistence:
  enabled: true                    # VERPLICHT voor productie!
  storageClass: "fast-ssd"        # Pas aan voor jouw cluster
  size: 50Gi                      # Database + bestanden

# Environment variabelen
app:
  env:
    defaultNlpEngine: "spacy"          # of "transformers"
    defaultSpacyModel: "nl_core_news_md"
    cryptoKey: "your-secret-key"       # Wijzig dit!
  auth:
    existingSecret: "anonymiq-basic-auth"  # Secret met de sleutels username en password
  cors:
    allowedOrigins: ""                 # Leeg = geen CORS (server naar server)

# Resources
resources:
  requests:
    cpu: 500m
    memory: 4Gi
  limits:
    cpu: 1500m
    memory: 8Gi
```

#### Productie setup

Voor productie gebruik:

1. **Authenticatie (verplicht)**: alle routes onder `/api/v1/documents` en de tekstroutes `/api/v1/analyze` en `/api/v1/anonymize` vragen HTTP Basic. Zonder wachtwoord weigert de service elk van die verzoeken met 401; alleen `/api/v1/health` blijft zonder inloggen bereikbaar. Open Register stuurt deze gegevens mee zodra je bij een externe OpenAnonymiser een gebruikersnaam en wachtwoord invult. Zet de gegevens in een Kubernetes secret en verwijs ernaar met `app.auth.existingSecret`:
```bash
kubectl -n <namespace> create secret generic anonymiq-basic-auth \
  --from-literal=username=<gebruiker> \
  --from-literal=password=<lang-willekeurig-wachtwoord>
```
Lokaal en in docker-compose gebruik je `BASIC_AUTH_USERNAME` en `BASIC_AUTH_PASSWORD`.

2. **CORS**: standaard uit. Alleen een browser-frontend op een ander origin heeft het nodig; noem die origins expliciet in `app.cors.allowedOrigins` (of `ALLOWED_ORIGINS`, komma-gescheiden). Een wildcard `*` wordt bij het opstarten geweigerd. De ingress zet zelf geen CORS-headers meer.

3. **TLS**: Enable TLS in ingress configuratie

4. **Monitoring**: Health checks zijn al geconfigureerd op `/health`

### 5. Testen (pytest)

Gebruik de nieuwe use-case tests in `tests/test_usecases.py`. Stel een BASE URL in of laat default (localhost:8080).

```bash
# Tegen lokale server
pytest -q -k usecases

# Tegen staging of productie.
# De hostnames blijven `api.openanonymiser.*` — die DNS-namen zijn live en
# `api.anonymiq.*` bestaat nog niet. De env-var heet nu ANONYMIQ_BASE_URL;
# OPENANONYMISER_BASE_URL wordt nog steeds gelezen zodat bestaande scripts
# blijven werken.
ANONYMIQ_BASE_URL="https://api.openanonymiser.accept.commonground.nu" pytest -q -k usecases
# of
ANONYMIQ_BASE_URL="https://api.openanonymiser.commonground.nu" pytest -q -k usecases
```
