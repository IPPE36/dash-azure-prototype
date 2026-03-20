Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------- variables ----------
$RG = "mwe"
$LOC = "switzerlandnorth"
$ACR_NAME = "mweacr"          # must be globally unique
$ENV_NAME = "mwe-env"
$APP_WEB = "mwe-web"
$APP_WORKER_DEFAULT = "mwe-worker-default"
$APP_WORKER_LONG = "mwe-worker-long"

# Update these to strong values
$POSTGRES_ADMIN = "pgadmin"
$POSTGRES_PASSWORD = "REPLACE_WITH_STRONG_PASSWORD"
$POSTGRES_DB = "appdb"
$REDIS_NAME = "mwe-redis"

# ---------- resource group ----------
az group create -n $RG -l $LOC

# ---------- container registry ----------
az acr create -g $RG -n $ACR_NAME --sku Basic

# ---------- postgres flexible server ----------
az postgres flexible-server create `
  -g $RG -n "$RG-pg" `
  -l $LOC `
  --admin-user $POSTGRES_ADMIN `
  --admin-password $POSTGRES_PASSWORD `
  --storage-size 32 `
  --tier Burstable `
  --sku-name Standard_B1ms `
  --public-access 0.0.0.0 `
  --database-name $POSTGRES_DB

# OPTIONAL: restrict access later to Container Apps outbound IPs or use private networking
# (we can tighten firewall once apps are up)

# ---------- azure cache for redis ----------
az redis create `
  -g $RG -n $REDIS_NAME -l $LOC `
  --sku Basic --vm-size C0

# ---------- container apps environment ----------
az containerapp env create -g $RG -n $ENV_NAME -l $LOC

# ---------- build and push images to ACR ----------
az acr login -n $ACR_NAME
az acr build -r $ACR_NAME -t dash-azure-web:latest --build-arg REQUIREMENTS=requirements/web.txt .
az acr build -r $ACR_NAME -t dash-azure-worker:latest --build-arg REQUIREMENTS=requirements/worker.txt .

# ---------- get connection values ----------
$PG_FQDN = az postgres flexible-server show -g $RG -n "$RG-pg" --query "fullyQualifiedDomainName" -o tsv
$REDIS_HOST = az redis show -g $RG -n $REDIS_NAME --query "hostName" -o tsv
$REDIS_KEY = az redis list-keys -g $RG -n $REDIS_NAME --query "primaryKey" -o tsv

# Build DATABASE_URL and REDIS URLs
$DATABASE_URL = "postgresql+psycopg://$POSTGRES_ADMIN:$POSTGRES_PASSWORD@$PG_FQDN:5432/$POSTGRES_DB"
$REDIS_URL = "rediss://:$REDIS_KEY@$REDIS_HOST:6380/0"

# ---------- web container app (public) ----------
az containerapp create `
  -g $RG -n $APP_WEB --environment $ENV_NAME `
  --image "$ACR_NAME.azurecr.io/dash-azure-web:latest" `
  --target-port 8050 --ingress external `
  --registry-server "$ACR_NAME.azurecr.io" `
  --env-vars `
    DATABASE_URL=$DATABASE_URL `
    CELERY_BROKER_URL=$REDIS_URL `
    CELERY_RESULT_BACKEND=$REDIS_URL `
    SECRET=REPLACE_ME `
    CLIENT_ID=REPLACE_ME `
    CLIENT_SECRET=REPLACE_ME `
    TENANT_ID=REPLACE_ME

# ---------- worker-default (no ingress) ----------
az containerapp create `
  -g $RG -n $APP_WORKER_DEFAULT --environment $ENV_NAME `
  --image "$ACR_NAME.azurecr.io/dash-azure-worker:latest" `
  --registry-server "$ACR_NAME.azurecr.io" `
  --command "celery" `
  --args "-A" "shared.celery_app:celery_app" "worker" "--loglevel=INFO" "-Q" "default" "--concurrency=1" "-n" "default@%h" `
  --env-vars `
    DATABASE_URL=$DATABASE_URL `
    CELERY_BROKER_URL=$REDIS_URL `
    CELERY_RESULT_BACKEND=$REDIS_URL `
    SECRET=REPLACE_ME `
    CLIENT_ID=REPLACE_ME `
    CLIENT_SECRET=REPLACE_ME `
    TENANT_ID=REPLACE_ME

# ---------- worker-long (no ingress) ----------
az containerapp create `
  -g $RG -n $APP_WORKER_LONG --environment $ENV_NAME `
  --image "$ACR_NAME.azurecr.io/dash-azure-worker:latest" `
  --registry-server "$ACR_NAME.azurecr.io" `
  --command "celery" `
  --args "-A" "shared.celery_app:celery_app" "worker" "--loglevel=INFO" "-Q" "background" "--concurrency=1" "-n" "long@%h" `
  --env-vars `
    DATABASE_URL=$DATABASE_URL `
    CELERY_BROKER_URL=$REDIS_URL `
    CELERY_RESULT_BACKEND=$REDIS_URL `
    SECRET=REPLACE_ME `
    CLIENT_ID=REPLACE_ME `
    CLIENT_SECRET=REPLACE_ME `
    TENANT_ID=REPLACE_ME
