docker compose up --build  (run locally)

winget install Microsoft.AzureCLI  (installs)
az --version  (checks installation)
az login --use-device-code  (open browser, put in code from terminal)
https://login.microsoft.com/device
az account show  (shows account info)
az group create --name <resource-group-name> --location <location>  (create a recource group)
e.g. rg-mweapp-dev-weu  (dev environment, western europe)
e.g. westeurope

docker compose run --rm web alembic revision --autogenerate -m "initial schema"

# ========================================
# CONFIGURATION
# ========================================

# ---- General ----
APP_NAME="myapp"
ENVIRONMENT="dev"                  # dev | staging | prod
LOCATION="westeurope"             # e.g. westeurope, eastus
REGION_SHORT="weu"                # short code for naming

# ---- Resource Group ----
RG="rg-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"

# ---- PostgreSQL ----
POSTGRES_SERVER="pg-${APP_NAME}-${ENVIRONMENT}-${RANDOM}${RANDOM}"  # must be globally unique
POSTGRES_DB="${APP_NAME}"
POSTGRES_ADMIN="pgadmin"
POSTGRES_PASSWORD="$(openssl rand -base64 24 | tr -d '=+/' | cut -c1-20)"

POSTGRES_SKU="Standard_B1ms"      # cheapest flexible server
POSTGRES_TIER="Burstable"
POSTGRES_VERSION="16"

# ---- Redis ----
REDIS_NAME="redis-${APP_NAME}-${ENVIRONMENT}-${RANDOM}${RANDOM}"   # must be globally unique
REDIS_SKU="Basic"
REDIS_SIZE="c0"                  # cheapest

# ---- Container Apps ----
CONTAINER_ENV="cae-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"
CONTAINER_APP="ca-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"

APP_IMAGE="mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
APP_PORT="80"

MIN_REPLICAS=1
MAX_REPLICAS=1

# ---- Logging ----
LOG_ANALYTICS_WS="log-${APP_NAME}-${ENVIRONMENT}-${REGION_SHORT}"

# ---- Tags (optional but recommended) ----
TAGS="env=${ENVIRONMENT} app=${APP_NAME} owner=me"

# ---- Derived (usually don’t touch) ----
DATABASE_URL=""   # will be constructed later
REDIS_URL=""      # will be constructed later


#!/usr/bin/env bash
set -euo pipefail

# ----------------------------
# Change these values
# ----------------------------
LOCATION="westeurope"
RG="rg-myapp-dev-weu"

POSTGRES_SERVER="pgmyapp$RANDOM$RANDOM"   # must be globally unique
POSTGRES_DB="appdb"
POSTGRES_ADMIN="pgadminuser"
POSTGRES_PASSWORD="$(openssl rand -base64 24 | tr -d '=+/' | cut -c1-20)"

REDIS_NAME="redismyapp$RANDOM$RANDOM"      # must be globally unique
CONTAINER_ENV="cae-myapp-dev-weu"
CONTAINER_APP="ca-myapp-dev-weu"

# Demo image only. Replace with your own image later.
APP_IMAGE="mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"



# Optional if you have multiple subscriptions:
# az account set --subscription "<subscription-id-or-name>"

# Container Apps commands are available in Azure CLI; the extension is also used for newer features.
az extension add --name containerapp --upgrade --allow-preview true >/dev/null 2>&1 || true

# ----------------------------
# 1) Resource group
# ----------------------------
az group create \
  --name "$RG" \
  --location "$LOCATION"

# ----------------------------
# 2) PostgreSQL Flexible Server
# Public access is enabled and limited to Azure services ("All" is broader internet; avoid that).
# The CLI supports --public-access with values like Enabled, Disabled, All, None, or an IP/range.
# ----------------------------
az postgres flexible-server create \
  --resource-group "$RG" \
  --name "$POSTGRES_SERVER" \
  --location "$LOCATION" \
  --admin-user "$POSTGRES_ADMIN" \
  --admin-password "$POSTGRES_PASSWORD" \
  --database-name "$POSTGRES_DB" \
  --public-access Enabled \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --version 16 \
  --yes

# Get Postgres host
POSTGRES_HOST="$(az postgres flexible-server show \
  --resource-group "$RG" \
  --name "$POSTGRES_SERVER" \
  --query fullyQualifiedDomainName \
  -o tsv)"

DATABASE_URL="postgresql://${POSTGRES_ADMIN}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/${POSTGRES_DB}?sslmode=require"

# ----------------------------
# 3) Redis
# Basic C0 is the cheapest/smallest Azure Cache for Redis SKU.
# ----------------------------
az redis create \
  --resource-group "$RG" \
  --name "$REDIS_NAME" \
  --location "$LOCATION" \
  --sku Basic \
  --vm-size c0

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

# ----------------------------
# 4) Container Apps environment
# Log Analytics settings can be provided to the environment; newer CLI flows may create defaults,
# but explicit workspace creation is the safer path.
# ----------------------------
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

# ----------------------------
# 5) Container App
# Secrets are stored in Container Apps, and env vars can reference them with secretref:...
# ----------------------------
az containerapp create \
  --name "$CONTAINER_APP" \
  --resource-group "$RG" \
  --environment "$CONTAINER_ENV" \
  --image "$APP_IMAGE" \
  --target-port 80 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 1 \
  --secrets \
    db-url="$DATABASE_URL" \
    redis-url="$REDIS_URL" \
  --env-vars \
    DATABASE_URL=secretref:db-url \
    REDIS_URL=secretref:redis-url \
    PORT=80

# ----------------------------
# 6) Output useful values
# ----------------------------
APP_FQDN="$(az containerapp show \
  --name "$CONTAINER_APP" \
  --resource-group "$RG" \
  --query properties.configuration.ingress.fqdn \
  -o tsv)"

echo
echo "Done."
echo "Resource group:   $RG"
echo "Postgres server:  $POSTGRES_SERVER"
echo "Postgres host:    $POSTGRES_HOST"
echo "Redis cache:      $REDIS_NAME"
echo "Container env:    $CONTAINER_ENV"
echo "Container app:    $CONTAINER_APP"
echo "App URL:          https://$APP_FQDN"
echo
echo "Injected app secrets/env vars:"
echo "  DATABASE_URL"
echo "  REDIS_URL"