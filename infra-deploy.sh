#!/usr/bin/env bash
set -euo pipefail

APP_NAME="suite"
APP_VERSION="1.0"
SUBSCRIPTION_NAME="Azure subscription 1"
ENVIRONMENT="dev"  # dev | pro
LOCATION="northeurope"
REGION_SHORT="neu"

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

# --- Add extensions ---
az extension add --name containerapp --upgrade --allow-preview true
az extension add --name redisenterprise --upgrade

# ---- Azure AD App Registration (for msal) ----
TENANT_ID="$(az account show --query tenantId -o tsv)"
CLIENT_ID="$(az ad app create \
  --display-name "$APP_NAME" \
  --query appId -o tsv)"
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

# ---- Recource Group ----
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
# az postgres flexible-server create \
#   --resource-group "$RG" \
#   --name "$POSTGRES_SERVER" \
#   --location "$LOCATION" \
#   --admin-user "$POSTGRES_ADMIN" \
#   --admin-password "$POSTGRES_PASSWORD" \
#   --public-access Enabled \
#   --sku-name Standard_B1ms \
#   --tier Burstable \
#   --storage-size 32 \
#   --backup-retention 7 \
#   --storage-auto-grow Disabled \
#   --zonal-resiliency Disabled \
#   --version 16 \
#   --yes
# echo "Creating Postgre DB: ${POSTGRES_SERVER} "
# az postgres flexible-server db create \
#   --resource-group "$RG" \
#   --server-name "$POSTGRES_SERVER" \
#   --database-name "$POSTGRES_DB"
POSTGRES_HOST="$(az postgres flexible-server show \
  --resource-group "$RG" \
  --name "$POSTGRES_SERVER" \
  --query fullyQualifiedDomainName \
  -o tsv)"
DATABASE_URL="postgresql://${POSTGRES_ADMIN}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"
echo "PostgresServer: ${POSTGRES_SERVER}"
echo "PostgresURL: ${DATABASE_URL}"

# ---- Redis ----
# DEPRECATED; NEEDS TO BE CHANGED TO "Managed Redis" BY 2028!!!
REDIS_NAME="redis-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"
echo "Creating Redis..."
# az redis create \
#   --resource-group "$RG" \
#   --name "$REDIS_NAME" \
#   --location "$LOCATION" \
#   --sku Basic \
#   --vm-size c0
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
REDIS_URL="rediss://:${REDIS_KEY}@${REDIS_HOST}:6380"
echo "Redis: ${REDIS_NAME}"
echo "RedisURL: ${REDIS_URL}"

# ---- Container Apps environment ----
CONTAINER_ENV="cae-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"
LAW="log-${RG}"
az monitor log-analytics workspace create \
  --resource-group "$RG" \
  --workspace-name "$LAW" \
  --location "$LOCATION"
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
az containerapp env create \
  --name "$CONTAINER_ENV" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --logs-workspace-id "$LAW_ID" \
  --logs-workspace-key "$LAW_KEY"

# ---- Container Registry (ACR) ----
ACR_NAME="acr${APP_NAME}${ENVIRONMENT}${REGION_SHORT}"
ACR_NAME="${ACR_NAME,,}"
az acr create \
  --resource-group "$RG" \
  --name "$ACR_NAME" \
  --sku Basic
az acr login --name "$ACR_NAME"

WEB_IMAGE="${APP_NAME}-web:latest"
WORKER_IMAGE="${APP_NAME}-worker:latest"
az acr build -r "$ACR_NAME" -t "$WEB_IMAGE" --build-arg REQUIREMENTS=requirements/web.txt .
az acr build -r "$ACR_NAME" -t "$WORKER_IMAGE" --build-arg REQUIREMENTS=requirements/worker.txt .

# ---- Container Apps (web + workers) ----
APP_WEB_NAME="ca-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}-web"
APP_WORKER_DEFAULT_NAME="ca-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}-worker-default"
APP_WORKER_BACKGROUND_NAME="ca-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}-worker-long"
APP_SECRET="pifSKhaKhzNAClyb172Y"  # "$(openssl rand -base64 24 | tr -d '=+/' | cut -c1-20)"
CELERY_REDIS_URL="rediss://:${REDIS_KEY}@${REDIS_HOST}:6380/0"
CELERY_BROKER_URL="$CELERY_REDIS_URL"
CELERY_RESULT_BACKEND="$CELERY_REDIS_URL"
DATABASE_URL="postgresql+psycopg://${POSTGRES_ADMIN}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"
DEV="false"
SCOPE="openid,profile"

# Web (public)
az containerapp create \
  --name "$APP_WEB_NAME" \
  --resource-group "$RG" \
  --environment "$CONTAINER_ENV" \
  --image "$ACR_NAME.azurecr.io/$WEB_IMAGE" \
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
    DATABASE_URL=secretref:db-url \
    CELERY_BROKER_URL=secretref:redis-url \
    SECRET=secretref:app-secret \
    CLIENT_ID=secretref:client-id \
    CLIENT_SECRET=secretref:client-secret \
    TENANT_ID=secretref:tenant-id

# worker-default
az containerapp create \
  --name "$APP_WORKER_DEFAULT_NAME" \
  --resource-group "$RG" \
  --environment "$CONTAINER_ENV" \
  --image "$ACR_NAME.azurecr.io/$WORKER_IMAGE" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --command "celery" \
  --args "-A" "shared.celery_app:celery_app" "worker" "--loglevel=INFO" "-Q" "default" "--concurrency=1" "-n" "default@%h" \
  --min-replicas 1 \
  --max-replicas 1 \
  --secrets \
    db-url="$DATABASE_URL" \
    redis-url="$REDIS_URL" \
  --env-vars \
    APP_VERSION="$APP_VERSION" \
    DEV="$DEV" \
    DATABASE_URL=secretref:db-url \
    CELERY_BROKER_URL=secretref:redis-url \
    CELERY_RESULT_BACKEND=secretref:redis-url

# worker-backround
az containerapp create \
  --name "$APP_WORKER_BACKGROUND" \
  --resource-group "$RG" \
  --environment "$CONTAINER_ENV" \
  --image "$ACR_NAME.azurecr.io/$WORKER_IMAGE" \
  --registry-server "$ACR_NAME.azurecr.io" \
  --command "celery" \
  --args "-A" "shared.celery_app:celery_app" "worker" "--loglevel=INFO" "-Q" "background" "--concurrency=1" "-n" "long@%h" \
  --min-replicas 1 \
  --max-replicas 1 \
  --secrets \
    db-url="$DATABASE_URL" \
    redis-url="$REDIS_URL" \
    app-secret="$APP_SECRET" \
  --env-vars \
    APP_VERSION="$APP_VERSION" \
    DEV="$DEV" \
    DATABASE_URL=secretref:db-url \
    CELERY_BROKER_URL=secretref:redis-url \
    CELERY_RESULT_BACKEND=secretref:redis-url

exit
