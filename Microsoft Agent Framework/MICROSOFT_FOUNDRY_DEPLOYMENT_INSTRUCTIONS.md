---
title: Microsoft Foundry Hosted Agent Deployment Instructions
description: Step-by-step guide to deploy this restaurant ordering multi-agent workflow to Microsoft Foundry as a hosted agent
author: Copilot
ms.date: 2026-03-22
ms.topic: how-to
keywords:
  - microsoft foundry
  - hosted agent
  - deployment
  - acr
  - docker
estimated_reading_time: 12
---

## Purpose

Use this guide to deploy this repository to Microsoft Foundry as a hosted agent backed by a container image.

## What you deploy

This deployment publishes your application code from `workflow_conditional.py` into a container image, pushes the image to Azure Container Registry (ACR), and configures a Foundry hosted agent to run that image.

## Prerequisites

Install and verify these tools first.

* Azure CLI
* Docker Desktop (running)
* Python 3.12 and `uv`

Run checks.

```bash
az version
docker version
python --version
uv --version
```

You also need these Azure resources.

* Azure AI Foundry project
* Azure Container Registry
* A model deployment in your Foundry project for LLM calls

## Step 1: Sign in and select subscription

```bash
az login
az account list --output table
az account set --subscription "<subscription-id-or-name>"
az account show --output table
```

## Step 2: Set deployment variables

Set shell variables once for the session.

```bash
export SUBSCRIPTION_ID="4b941d98-cdb0-4da1-8655-7328bab2487f"
export RESOURCE_GROUP="rg-tolu_agent_framework_demo"
export LOCATION="eastus2"
export ACR_NAME="crubnjxburycjhe"
export IMAGE_REPO="restaurant_order_agent"
export TAG="azd-env-name : tolu_agent_framework_demo"
export IMAGE_URI="crubnjxburycjhe.azurecr.io/azd-env-name : tolu_agent_framework_demo"
```
4b941d9restaurantorderagentf967acr.azurecr.io
Set your Foundry project endpoint.

```bash
export FOUNDRY_PROJECT_ENDPOINT="https://tolua-mmwk21na-eastus2.services.ai.azure.com/api/projects/tolua-mmwk21na-eastus2_project"
```

## Step 3: Validate app configuration

Ensure your local `.env` has the values required by this app before containerizing.

* `API_HOST=azure`
* `AZURE_OPENAI_ENDPOINT=<your-azure-openai-endpoint>`
* `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<your-model-deployment-name>`

Optional values for telemetry.

* `APPLICATIONINSIGHTS_CONNECTION_STRING`
* `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`

## Step 4: Build and push container image to ACR

Use ACR cloud build so local Docker architecture mismatches do not block deployment.

```bash
az acr build \
  --registry "crubnjxburycjhe" \
  --image "azd-env-name : tolu_agent_framework_demo" \
  --platform linux/amd64 \
  --file Dockerfile \
  .
```

Verify the image exists.

```bash
az acr repository show-tags \
  --name "rubnjxburycjhe" \
  --repository "azd-env-name : tolu_agent_framework_demo" \
  --output table
```

## Step 5: Gather hosted agent runtime settings

Collect the environment variables your hosted agent container must receive.

Required minimum values for this project.

* `API_HOST`
* `AZURE_OPENAI_ENDPOINT`
* `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`

Recommended values.

* `APPLICATIONINSIGHTS_CONNECTION_STRING`
* `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING`

## Step 6: Create hosted agent in Foundry

Open Microsoft Foundry in the browser.

```text
https://ai.azure.com
```

In your target project:

1. Open `Build`.
2. Open `Agents`.
3. Create a new agent.
4. Choose `Hosted agent`.
5. Set agent name to something unique, for example `restaurant-ordering-hosted`.
6. Set container image to `$IMAGE_URI`.
7. Set CPU and memory sizing that fits your workload, for example `1 vCPU` and `2 GiB`.
8. Add container environment variables from Step 5.
9. Save the agent definition.

## Step 7: Start container runtime

From the agent details page in Foundry:

1. Open `Runtime` or `Container control`.
2. Select `Start`.
3. Wait for status to become `Running`.

If startup fails, check container logs from the same page and fix missing environment variables first.

## Step 8: Invoke a smoke test

Use the Foundry agent Playground and send a basic message.

```text
Hi, I want to order a large pepperoni pizza and a coke.
```

Validate that the agent responds and maintains order context across at least two turns.

## Step 9: Verify observability

If `APPLICATIONINSIGHTS_CONNECTION_STRING` is set:

1. Open Application Insights for your workspace.
2. Confirm request, dependency, and custom event telemetry is arriving.
3. Search for tool-call spans and workflow spans from this agent.

## Step 10: Persist deployment metadata in repo

Create or update `.foundry/agent-metadata.yaml` so future deployment and evaluation workflows can reuse the same environment settings.

Suggested values to store.

* `projectEndpoint`
* `agentName`
* `azureContainerRegistry`
* `imageUri`

## Step 11: Redeploy after code changes

When code changes, build a new image tag and update the hosted agent image.

```bash
export TAG="$(date +%Y%m%d%H%M%S)"
az acr build \
  --registry "$ACR_NAME" \
  --image "$IMAGE_REPO:$TAG" \
  --platform linux/amd64 \
  --file Dockerfile \
  .
```

Then update the hosted agent image in Foundry and restart the container.

## Troubleshooting

### Container starts but model calls fail

* Check `AZURE_OPENAI_ENDPOINT` value format. It should be your resource root, not a `/openai/...` path.
* Check `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` matches a deployed model name.

### Container fails on startup

* Open hosted agent container logs in Foundry.
* Confirm all required environment variables are set.
* Confirm image tag exists in ACR.

### Telemetry not visible

* Confirm `APPLICATIONINSIGHTS_CONNECTION_STRING` is set in hosted agent environment variables.
* Confirm network and identity permissions allow telemetry export.

## Quick redeploy checklist

```bash
az login
az account set --subscription "<subscription-id-or-name>"
export TAG="$(date +%Y%m%d%H%M%S)"
az acr build --registry "$ACR_NAME" --image "$IMAGE_REPO:$TAG" --platform linux/amd64 --file Dockerfile .
```

After the build finishes:

1. Update hosted agent image URI in Foundry.
2. Restart container runtime.
3. Run a smoke test in Playground.
