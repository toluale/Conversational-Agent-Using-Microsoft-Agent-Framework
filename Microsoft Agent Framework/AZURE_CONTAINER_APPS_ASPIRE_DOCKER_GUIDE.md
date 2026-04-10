---
title: Azure Container Apps and Aspire Docker Guide
description: Step-by-step Azure Container Apps deployment guide plus local Aspire observability setup with Docker Engine
author: Copilot
ms.date: 2026-03-22
ms.topic: how-to
keywords:
  - azure
  - azd
  - container apps
  - aspire dashboard
  - docker engine
  - deployment
  - troubleshooting
estimated_reading_time: 10
---

## Purpose

Use this guide to deploy this project to Azure Container Apps and run Aspire Dashboard locally for observability using Docker Engine.

## Prerequisites

Install and verify the following tools before starting.

* Azure CLI
* Azure Developer CLI (`azd`)
* Docker Desktop (running)
* Python 3.12
* `uv`

Run these checks.

```bash
az version
azd version
docker version
python --version
uv --version
```

## Step 1: Sign in to Azure

Authenticate with your Azure account.

```bash
az login
```

If you use multiple tenants or subscriptions, select the right context.

```bash
az account list --output table
az account set --subscription "<subscription-id-or-name>"
az account show --output table
```

If needed, refresh authentication for Azure Developer CLI.

```bash
azd auth login
```

## Step 2: Prepare local environment

From the repo root, activate the virtual environment and validate local run.

```bash
source .venv/bin/activate
uv run ./workflow_conditional.py --devui
```

Stop the local process after confirming it starts successfully.

## Step 3: Configure deployment mode in azure.yaml

Ensure [azure.yaml](azure.yaml) uses Dockerfile mode for the service.

```yaml
services:
  agent-framework:
    project: .
    host: containerapp
    language: python
    docker:
      path: ./Dockerfile
      context: .
```

Use neutral naming values to avoid Azure reserved word validation errors.

```yaml
name: agent-framework-demo
services:
  agent-framework:
resources:
  agent-framework:
```

## Step 4: Build image with Dockerfile

Use this Dockerfile setup in [Dockerfile](Dockerfile).

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv

COPY . .
RUN uv sync --frozen

EXPOSE 80
ENV PORT=80

CMD ["uv", "run", "python", "workflow_conditional.py"]
```

The `git` package is required because this project installs Git-based dependencies during `uv sync`.

## Step 5: Package and deploy

Package first to validate build output.

```bash
azd package --all --debug
```

Deploy after package succeeds.

```bash
azd up --debug
```

A successful deployment ends with a message similar to this.

```text
SUCCESS: Your up workflow to provision and deploy to Azure completed in <time>.
```

## Step 6: Validate deployment

Show current environment outputs.

```bash
azd show
```

If an endpoint is listed, test it with curl.

```bash
curl -i "<app-url>"
```

## Step 7: Run Aspire observability locally with Docker Engine

Start Aspire Dashboard with Docker Compose.

```bash
docker compose -f docker-compose.aspire-dashboard.yml up -d
```

Open the dashboard.

```text
http://localhost:18888
```

Run the app with OTel enabled so traces are sent to Aspire.

```bash
source .venv/bin/activate
uv run ./workflow_conditional.py --otel
```

Stop Aspire when you are done.

```bash
docker compose -f docker-compose.aspire-dashboard.yml down
```

If telemetry does not appear, verify these environment values.

```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
```

## Troubleshooting and bypasses used

### Problem: Docker API client too old (buildpacks path)

Symptom:

```text
client version 1.38 is too old
```

Bypass used:

* Switched service build path to Dockerfile mode in [azure.yaml](azure.yaml)
* Avoided buildpacks analyzer path entirely

### Problem: Analyzer previous-image failure

Symptom:

* Buildpacks/analyzer fails while checking previous image metadata

Bypass used:

* Continued with Dockerfile mode (`docker.path` + `docker.context`) and packaged with Docker directly

### Problem: Git executable missing during uv sync

Symptom:

```text
Git executable not found
```

Bypass used:

* Added `git` installation in [Dockerfile](Dockerfile)

### Problem: ReservedResourceName during Azure validation

Symptom:

```text
ReservedResourceName
The resource name ... is a trademarked or reserved word
```

Bypass used:

* Renamed project/service/resource identifiers in [azure.yaml](azure.yaml)
* Removed `microsoft` from generated naming path

## Operational checklist for future deployments

Run this exact sequence for repeatable results.

```bash
az login
az account set --subscription "<subscription-id-or-name>"
azd auth login
source .venv/bin/activate
azd package --all --debug
azd up --debug
azd show
```

## Notes

* If deployment fails, rerun with `--debug` and inspect the first explicit `ERROR:` block.
* Keep [azure.yaml](azure.yaml) and [Dockerfile](Dockerfile) aligned when changing service names, ports, or startup commands.
* If you rename the project, check whether `.azure/<env-name>/` values need to be reinitialized.
