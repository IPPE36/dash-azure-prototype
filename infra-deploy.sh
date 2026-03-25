#!/usr/bin/env bash
set -euo pipefail

APP_NAME="suite"
APP_VERSION="1.0"
APP_ID=""  # Optional: set to an existing AAD appId to reuse strictly
SUBSCRIPTION_NAME="Azure subscription 1"
ENVIRONMENT="dev"  # dev | pro
LOCATION="northeurope"
REGION_SHORT="neu"

if [ "${DEBUG:-false}" = "true" ]; then
  set -x
fi

: "${AZURE_CORE_ONLY_SHOW_ERRORS:=1}"
export AZURE_CORE_ONLY_SHOW_ERRORS
echo "Starting deployment for ${APP_NAME} (${ENVIRONMENT}) in ${LOCATION}"

# Prevent Git-Bash/MSYS path rewriting (e.g., /app -> C:/Program Files/Git/app).
case "$(uname -s 2>/dev/null || true)" in
  MINGW*|MSYS*|CYGWIN*)
    export MSYS_NO_PATHCONV=1
    export MSYS2_ARG_CONV_EXCL="*"
    ;;
esac

ensure_provider() {
  local provider="$1"
  local state
  state="$(az provider show --namespace "$provider" --query registrationState -o tsv 2>/dev/null || echo NotRegistered)"
  if [ "$state" != "Registered" ]; then
    az provider register --namespace "$provider" >/dev/null 2>&1 || true
    until [ "$state" = "Registered" ]; do
      sleep 10
      state="$(az provider show --namespace "$provider" --query registrationState -o tsv)"
      echo "${provider} registrationState: $state"
    done
  else
    echo "${provider} is already registered."
  fi
}

az_exists() {
  az "$@" >/dev/null 2>&1
}

# ---- Login ----
az account show >/dev/null 2>&1 || az login
az account list --output table  # shows all info
az account set --subscription "${SUBSCRIPTION_NAME}"
echo "Subscription: ${SUBSCRIPTION_NAME}"

# --- Ensure Providers ---
ensure_provider "Microsoft.App"
ensure_provider "Microsoft.Cache"
ensure_provider "Microsoft.DBforPostgreSQL"
ensure_provider "Microsoft.OperationalInsights"
ensure_provider "Microsoft.ContainerRegistry"
echo "Providers ensured."

# --- Add extensions ---
az extension add --name containerapp --upgrade --allow-preview true
az extension add --name redisenterprise --upgrade
echo "Azure CLI extensions updated."

# ---- Azure AD App Registration (for msal) ----
TENANT_ID="$(az account show --query tenantId -o tsv)"
if [ -n "${APP_ID}" ]; then
  if az_exists ad app show --id "$APP_ID"; then
    CLIENT_ID="$APP_ID"
    echo "Using configured AAD app: ${CLIENT_ID}"
  else
    echo "ERROR: APP_ID not found: ${APP_ID}" >&2
    exit 1
  fi
else
  APP_MATCH_COUNT="$(az ad app list --display-name "$APP_NAME" --query "length(@)" -o tsv)"
  if [ "${APP_MATCH_COUNT}" -gt 1 ]; then
    echo "ERROR: Multiple AAD apps named '${APP_NAME}'. Set APP_ID to select one." >&2
    exit 1
  fi
  EXISTING_APP_ID="$(az ad app list --display-name "$APP_NAME" --query "[0].appId" -o tsv)"
  if [ -n "${EXISTING_APP_ID}" ]; then
    CLIENT_ID="${EXISTING_APP_ID}"
    echo "Using existing AAD app: ${CLIENT_ID}"
  else
    CLIENT_ID="$(az ad app create \
      --display-name "$APP_NAME" \
      --query appId -o tsv)"
    echo "Created AAD app: ${CLIENT_ID}"
  fi
fi
CLIENT_SECRET="$(az ad app credential reset \
  --id "$CLIENT_ID" \
  --append \
  --display-name "${APP_NAME}-containerapp-web" \
  --years 1 \
  --query password -o tsv)"
AUTHORITY="https://login.microsoftonline.com/${TENANT_ID}"
echo "Authority: ${AUTHORITY}"
echo "TenantID: ${TENANT_ID}"
echo "ClientID: ${CLIENT_ID}"
echo "ClientSecret: ${CLIENT_SECRET}"
echo "AAD app ready."
LOCAL_REDIRECT_URI="http://localhost:${PORT:-8050}/getAToken"
az ad app update --id "$CLIENT_ID" --web-redirect-uris "$LOCAL_REDIRECT_URI"
echo "AAD redirect URI added: ${LOCAL_REDIRECT_URI}"

# ---- Resource Group ----
RG="rg-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"
az group create --name "$RG" --location "$LOCATION"
echo "ResourceGroup: ${RG}"

# ---- PostgreSQL ----
# Public access is enabled and limited to Azure services ("All" is broader internet; avoid that).
POSTGRES_SERVER="pg-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"
POSTGRES_DB="${APP_NAME}"
POSTGRES_ADMIN="pgadmin"
POSTGRES_PASSWORD="tKELn3cWe3P8yPVIJ6eu"  # "$(openssl rand -base64 24 | tr -d '=+/' | cut -c1-20)"
echo "PostgresPassword (STORE!): ${POSTGRES_PASSWORD}"
echo "Creating Postgre Flexible Server..."
if az_exists postgres flexible-server show --resource-group "$RG" --name "$POSTGRES_SERVER"; then
  echo "PostgreSQL server exists: ${POSTGRES_SERVER}"
else
  az postgres flexible-server create \
    --resource-group "$RG" \
    --name "$POSTGRES_SERVER" \
    --location "$LOCATION" \
    --admin-user "$POSTGRES_ADMIN" \
    --admin-password "$POSTGRES_PASSWORD" \
    --public-access Enabled \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --storage-size 32 \
    --backup-retention 7 \
    --storage-auto-grow Disabled \
    --zonal-resiliency Disabled \
    --version 16 \
    --yes
fi
az postgres flexible-server firewall-rule create \
  --resource-group "$RG" \
  --name "$POSTGRES_SERVER" \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
# After may 2026:
# az postgres flexible-server firewall-rule create \
#     --resource-group "$RG" \
#     --server-name "$POSTGRES_SERVER" \
#     --name "AllowAzureServices" \
#     --start-ip-address 0.0.0.0 \
#     --end-ip-address 0.0.0.0
if az_exists postgres flexible-server db show --resource-group "$RG" --server-name "$POSTGRES_SERVER" --database-name "$POSTGRES_DB"; then
  echo "PostgreSQL database exists: ${POSTGRES_DB}"
else
  echo "Creating Postgre DB: ${POSTGRES_SERVER} "
  az postgres flexible-server db create \
    --resource-group "$RG" \
    --server-name "$POSTGRES_SERVER" \
    --database-name "$POSTGRES_DB"
fi
POSTGRES_HOST="$(az postgres flexible-server show \
  --resource-group "$RG" \
  --name "$POSTGRES_SERVER" \
  --query fullyQualifiedDomainName \
  -o tsv)"
DATABASE_URL="postgresql://${POSTGRES_ADMIN}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"
echo "PostgresServer: ${POSTGRES_SERVER}"
echo "PostgresURL: ${DATABASE_URL}"
echo "PostgreSQL ready."

# ---- Redis ----
# DEPRECATED; NEEDS TO BE CHANGED TO "Managed Redis" BY 2028!!!
REDIS_NAME="redis-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"
echo "Creating Redis..."
if az_exists redis show --resource-group "$RG" --name "$REDIS_NAME"; then
  echo "Redis exists: ${REDIS_NAME}"
else
  az redis create \
    --resource-group "$RG" \
    --name "$REDIS_NAME" \
    --location "$LOCATION" \
    --sku Basic \
    --vm-size c0
fi
REDIS_HOST="$(az redis show \
  --resource-group "$RG" \
  --name "$REDIS_NAME" \
  --query hostName \
  -o tsv)"
REDIS_KEY="$(az redis list-keys \
  --resource-group "$RG" \
  --name "$REDIS_NAME" \
  --query primaryKey \
  -o tsv)"
REDIS_URL="rediss://:${REDIS_KEY}@${REDIS_HOST}:6380?ssl_cert_reqs=required"
echo "Redis: ${REDIS_NAME}"
echo "RedisURL: ${REDIS_URL}"
echo "Redis ready."

# ---- Container Apps Environment ----
CONTAINER_ENV="cae-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"
LAW="log-${RG}"
if az_exists monitor log-analytics workspace show --resource-group "$RG" --workspace-name "$LAW"; then
  echo "Log Analytics workspace exists: ${LAW}"
else
  az monitor log-analytics workspace create \
    --resource-group "$RG" \
    --workspace-name "$LAW" \
    --location "$LOCATION"
fi
LAW_ID="$(az monitor log-analytics workspace show \
  --resource-group "$RG" \
  --workspace-name "$LAW" \
  --query customerId \
  -o tsv)"
LAW_KEY="$(az monitor log-analytics workspace get-shared-keys \
  --resource-group "$RG" \
  --workspace-name "$LAW" \
  --query primarySharedKey \
  -o tsv)"
if az_exists containerapp env show --name "$CONTAINER_ENV" --resource-group "$RG"; then
  echo "Container Apps environment exists: ${CONTAINER_ENV}"
else
  az containerapp env create \
    --name "$CONTAINER_ENV" \
    --resource-group "$RG" \
    --location "$LOCATION" \
    --logs-workspace-id "$LAW_ID" \
    --logs-workspace-key "$LAW_KEY"
fi
echo "Container Apps environment ready: ${CONTAINER_ENV}"

# ---- App Container Registry (ACR) ----
ACR_NAME="acr${APP_NAME}${ENVIRONMENT}${REGION_SHORT}"
ACR_NAME="${ACR_NAME,,}"
if az_exists acr show --resource-group "$RG" --name "$ACR_NAME"; then
  echo "ACR exists: ${ACR_NAME}"
else
  az acr create \
    --resource-group "$RG" \
    --name "$ACR_NAME" \
    --sku Basic
fi
az acr login --name "$ACR_NAME"
echo "ACR ready: ${ACR_NAME}"

WEB_IMAGE="${APP_NAME}-web:latest"
WORKER_IMAGE="${APP_NAME}-worker:latest"
WEB_IMAGE_FULL="$ACR_NAME.azurecr.io/$WEB_IMAGE"
WORKER_IMAGE_FULL="$ACR_NAME.azurecr.io/$WORKER_IMAGE"

# NOTE: Models are baked into the image via MODEL_DIR.
# Pros: fast startup, no external download dependency.
# Cons: larger images + rebuild/redeploy required for model updates.
docker build -t "$WEB_IMAGE_FULL" --build-arg REQUIREMENTS=requirements/web.txt --build-arg MODEL_DIR=ml/models/artifacts .
docker build -t "$WORKER_IMAGE_FULL" --build-arg REQUIREMENTS=requirements/worker.txt --build-arg MODEL_DIR=ml/models/artifacts .
docker push "$WEB_IMAGE_FULL"
docker push "$WORKER_IMAGE_FULL"
echo "Images built and pushed: ${WEB_IMAGE_FULL}, ${WORKER_IMAGE_FULL}"

# ---- Container Apps (web + workers) ----
APP_WEB_NAME="ca-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}-web"
APP_WORKER_DEFAULT_NAME="ca-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}-worker-default"
APP_WORKER_BACKGROUND_NAME="ca-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}-worker-long"
CELERY_REDIS_URL="rediss://:${REDIS_KEY}@${REDIS_HOST}:6380/0?ssl_cert_reqs=required"
CELERY_BROKER_URL="$CELERY_REDIS_URL"
CELERY_RESULT_BACKEND="$CELERY_REDIS_URL"
DATABASE_URL="postgresql+psycopg://${POSTGRES_ADMIN}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"
DEV="false"
LOGIN_MODE="msal"
SCOPE=""  # "openid,profile"

# Web (public)
if az_exists containerapp show --name "$APP_WEB_NAME" --resource-group "$RG"; then
  echo "Updating web app: ${APP_WEB_NAME}"
  WEB_APP_FQDN="$(az containerapp show \
    --name "$APP_WEB_NAME" \
    --resource-group "$RG" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)"
  REDIRECT_URI=""
  if [ -n "$WEB_APP_FQDN" ]; then
    REDIRECT_URI="https://${WEB_APP_FQDN}/getAToken"
  fi
  az containerapp secret set \
    --name "$APP_WEB_NAME" \
    --resource-group "$RG" \
    --secrets \
      db-url="$DATABASE_URL" \
      redis-url="$REDIS_URL" \
      client-id="$CLIENT_ID" \
      client-secret="$CLIENT_SECRET" \
      tenant-id="$TENANT_ID"
  az containerapp update \
    --name "$APP_WEB_NAME" \
    --resource-group "$RG" \
    --image "$WEB_IMAGE_FULL" \
    --set-env-vars \
      APP_NAME="$APP_NAME" \
      APP_VERSION="$APP_VERSION" \
      AUTHORITY="$AUTHORITY" \
      SCOPE="$SCOPE" \
      DEV="$DEV" \
      LOGIN_MODE="$LOGIN_MODE" \
      REDIRECT_URI="$REDIRECT_URI" \
      DATABASE_URL=secretref:db-url \
      CELERY_BROKER_URL=secretref:redis-url \
      CLIENT_ID=secretref:client-id \
      CLIENT_SECRET=secretref:client-secret \
      TENANT_ID=secretref:tenant-id
else
  echo "Creating web app: ${APP_WEB_NAME}"
  az containerapp create \
    --name "$APP_WEB_NAME" \
    --resource-group "$RG" \
    --environment "$CONTAINER_ENV" \
    --image "$WEB_IMAGE_FULL" \
    --registry-server "$ACR_NAME.azurecr.io" \
    --target-port 8050 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 1 \
    --secrets \
      db-url="$DATABASE_URL" \
      redis-url="$REDIS_URL" \
      client-id="$CLIENT_ID" \
      client-secret="$CLIENT_SECRET" \
      tenant-id="$TENANT_ID" \
    --env-vars \
      APP_NAME="$APP_NAME" \
      APP_VERSION="$APP_VERSION" \
      AUTHORITY="$AUTHORITY" \
      SCOPE="$SCOPE" \
      DEV="$DEV" \
      LOGIN_MODE="$LOGIN_MODE" \
      DATABASE_URL=secretref:db-url \
      CELERY_BROKER_URL=secretref:redis-url \
      CLIENT_ID=secretref:client-id \
      CLIENT_SECRET=secretref:client-secret \
      TENANT_ID=secretref:tenant-id
  WEB_APP_FQDN="$(az containerapp show \
    --name "$APP_WEB_NAME" \
    --resource-group "$RG" \
    --query properties.configuration.ingress.fqdn \
    -o tsv)"
  if [ -n "$WEB_APP_FQDN" ]; then
    REDIRECT_URI="https://${WEB_APP_FQDN}/getAToken"
    az containerapp update \
      --name "$APP_WEB_NAME" \
      --resource-group "$RG" \
      --set-env-vars \
        REDIRECT_URI="$REDIRECT_URI"
  fi
fi
echo "Web app ready: ${APP_WEB_NAME}"

# worker-default
if az_exists containerapp show --name "$APP_WORKER_DEFAULT_NAME" --resource-group "$RG"; then
  echo "Updating worker (default): ${APP_WORKER_DEFAULT_NAME}"
  az containerapp secret set \
    --name "$APP_WORKER_DEFAULT_NAME" \
    --resource-group "$RG" \
    --secrets \
      db-url="$DATABASE_URL" \
      redis-url="$REDIS_URL"
  az containerapp update \
    --name "$APP_WORKER_DEFAULT_NAME" \
    --resource-group "$RG" \
    --image "$WORKER_IMAGE_FULL" \
    --command "/app/src/worker/entrypoint.sh" \
    --min-replicas 1 \
    --max-replicas 1 \
    --set-env-vars \
      APP_VERSION="$APP_VERSION" \
      DEV="$DEV" \
      MODEL_PATH="/app/models" \
      WORKER_QUEUE="default" \
      WORKER_NAME="default@%h" \
      WORKER_LOGLEVEL="INFO" \
      WORKER_CONCURRENCY="1" \
      DATABASE_URL=secretref:db-url \
      CELERY_BROKER_URL=secretref:redis-url \
      CELERY_RESULT_BACKEND=secretref:redis-url
else
  echo "Creating worker (default): ${APP_WORKER_DEFAULT_NAME}"
  az containerapp create \
    --name "$APP_WORKER_DEFAULT_NAME" \
    --resource-group "$RG" \
    --environment "$CONTAINER_ENV" \
    --image "$WORKER_IMAGE_FULL" \
    --registry-server "$ACR_NAME.azurecr.io" \
    --command "/app/src/worker/entrypoint.sh" \
    --min-replicas 1 \
    --max-replicas 1 \
    --secrets \
      db-url="$DATABASE_URL" \
      redis-url="$REDIS_URL" \
    --env-vars \
      APP_VERSION="$APP_VERSION" \
      DEV="$DEV" \
      MODEL_PATH="/app/models" \
      WORKER_QUEUE="default" \
      WORKER_NAME="default@%h" \
      WORKER_LOGLEVEL="INFO" \
      WORKER_CONCURRENCY="1" \
      DATABASE_URL=secretref:db-url \
      CELERY_BROKER_URL=secretref:redis-url \
      CELERY_RESULT_BACKEND=secretref:redis-url
fi
echo "Worker (default) ready: ${APP_WORKER_DEFAULT_NAME}"

# worker-background
if az_exists containerapp show --name "$APP_WORKER_BACKGROUND_NAME" --resource-group "$RG"; then
  echo "Updating worker (background): ${APP_WORKER_BACKGROUND_NAME}"
  az containerapp secret set \
    --name "$APP_WORKER_BACKGROUND_NAME" \
    --resource-group "$RG" \
    --secrets \
      db-url="$DATABASE_URL" \
      redis-url="$REDIS_URL"
  az containerapp update \
    --name "$APP_WORKER_BACKGROUND_NAME" \
    --resource-group "$RG" \
    --image "$WORKER_IMAGE_FULL" \
    --command "/app/src/worker/entrypoint.sh" \
    --min-replicas 1 \
    --max-replicas 1 \
    --set-env-vars \
      APP_VERSION="$APP_VERSION" \
      DEV="$DEV" \
      MODEL_PATH="/app/models" \
      WORKER_QUEUE="background" \
      WORKER_NAME="long@%h" \
      WORKER_LOGLEVEL="INFO" \
      WORKER_CONCURRENCY="1" \
      DATABASE_URL=secretref:db-url \
      CELERY_BROKER_URL=secretref:redis-url \
      CELERY_RESULT_BACKEND=secretref:redis-url
else
  echo "Creating worker (background): ${APP_WORKER_BACKGROUND_NAME}"
  az containerapp create \
    --name "$APP_WORKER_BACKGROUND_NAME" \
    --resource-group "$RG" \
    --environment "$CONTAINER_ENV" \
    --image "$WORKER_IMAGE_FULL" \
    --registry-server "$ACR_NAME.azurecr.io" \
    --command "/app/src/worker/entrypoint.sh" \
    --min-replicas 1 \
    --max-replicas 1 \
    --secrets \
      db-url="$DATABASE_URL" \
      redis-url="$REDIS_URL" \
    --env-vars \
      APP_VERSION="$APP_VERSION" \
      DEV="$DEV" \
      MODEL_PATH="/app/models" \
      WORKER_QUEUE="background" \
      WORKER_NAME="long@%h" \
      WORKER_LOGLEVEL="INFO" \
      WORKER_CONCURRENCY="1" \
      DATABASE_URL=secretref:db-url \
      CELERY_BROKER_URL=secretref:redis-url \
      CELERY_RESULT_BACKEND=secretref:redis-url
fi
echo "Worker (background) ready: ${APP_WORKER_BACKGROUND_NAME}"

# ---- Web App URL ----
WEB_APP_FQDN="$(az containerapp show \
  --name "$APP_WEB_NAME" \
  --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn \
  -o tsv)"
if [ -n "$WEB_APP_FQDN" ]; then
  echo "Web app URL: https://${WEB_APP_FQDN}"
  REDIRECT_URI="https://${WEB_APP_FQDN}/getAToken"
  az ad app update --id "$CLIENT_ID" --web-redirect-uris "$REDIRECT_URI" "$LOCAL_REDIRECT_URI"
  echo "AAD redirect URI set: ${REDIRECT_URI}"
else
  echo "WARN: Could not resolve web app FQDN. Check ingress settings for ${APP_WEB_NAME}."
fi
echo "Deployment complete."

exit
