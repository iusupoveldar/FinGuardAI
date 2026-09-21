---
title: FinGuardAI
emoji: 🛡️
sdk: docker
app_port: 7860
suggested_hardware: cpu-basic
models:
  - sentence-transformers/all-MiniLM-L6-v2
---

# FinGuardAI

FinGuardAI is an interactive portfolio demo of a financial transaction review
workflow. It lets visitors explore sample customer accounts, inspect transaction
activity, see an operational risk score, and open an investigation summary with
relevant policy references. It is built for people to try in a browser and to
show the engineering behind the workflow.

**All customer and transaction data is synthetic.** The transaction dataset was
generated with IBM AMLSim. The policy documents are examples written for this
demo. Risk scores help prioritize a review; they do not establish that fraud
occurred. FinGuardAI is not a production compliance system or a substitute for
a human investigator.

## What to try

1. Open **Overview** and select a customer to inspect accounts, transactions,
   and any saved risk score.
2. Choose **Investigate** to generate or reuse a summary of that customer's
   available evidence. The result lists risk factors and suggested next steps.
3. Open **Past investigations** to review saved results, or **Policies** to read
   the sample source documents.
4. Open **About this demo** in the app for a short explanation of the project.

The first request to a sleeping demo backend may take a little longer. If a
customer has no score, the UI shows an unscored state. DeepSeek can generate a
validated explanation when explicitly configured; otherwise the backend uses a
deterministic summary and records the reason for that fallback.

## How it works

```text
Synthetic AMLSim data -> PostgreSQL -> Python feature builder and risk model
                                      -> customer risk snapshots
Sample policy documents -> local search index -> relevant policy passages
Risk snapshot + policy passages -> investigation summary -> React dashboard
```

The frontend uses React and Vite. FastAPI provides the API and stores customer,
transaction, score, and investigation data in PostgreSQL. The scoring pipeline
uses scikit-learn. Policy retrieval uses sentence embeddings and Chroma. The
optional DeepSeek call explains existing evidence; it does not assign the score.

The public frontend can be hosted on **Cloudflare Pages**. The interactive demo
also needs a separate Python backend and PostgreSQL database; Cloudflare Pages
serves the frontend, not those services. The Dockerfile packages the backend for
a container host.

## Run locally on Windows

You need Python 3.11 or newer, Node.js with npm, and Docker Desktop with Docker
Compose. From the repository root:

```bat
.\backend\setup_backend.bat
.\backend\prepare_demo.bat
.\backend\start_backend.bat
```

`setup_backend.bat` creates `backend\.env` from the example when needed,
creates a virtual environment, installs dependencies, starts local PostgreSQL,
applies migrations, and imports the synthetic dataset. The import is safe to
rerun. `prepare_demo.bat` trains the model, writes customer risk scores, and
builds the policy index. This step can take time on the full dataset.
`start_backend.bat` starts the API with auto reload at
<http://127.0.0.1:9000>; API docs are at <http://127.0.0.1:9000/docs>.

In a second terminal, start the frontend:

```bat
cd frontend
npm ci
npm run dev
```

Open <http://localhost:4444>. Vite proxies `/api` to the local backend on port
9000. `.\backend\setup_backend.bat --no-docker` and
`.\backend\start_backend.bat --no-docker` use the PostgreSQL server specified by
`DATABASE_URL` in `backend\.env` instead of starting the local container. DeepSeek
is disabled in the example configuration; leave it disabled for a predictable
demo or configure its key, pricing, and daily budget intentionally.

For a manual setup, other platforms, and database commands, see
[backend/how_to.md](backend/how_to.md).

## Deploy the backend to Hugging Face

Create a **Docker Space** once, configure its `DATABASE_URL` secret and frontend
CORS origin, then install and log in to the Hugging Face CLI. From the repository
root, run:

```bat
.\deploy_huggingface.bat YOUR_HF_USERNAME/finguardai-api
```

The script uploads only the backend Docker build inputs and sample policy files.
It does not upload the frontend, local environment files, database data, or model
training artifacts. Check the Space build logs after upload, then set the
Cloudflare Pages frontend's `VITE_API_URL` to the Space's public `.hf.space` URL.
The one-time Space and database setup is described in
[docs/hugging-face-backend-deployment.md](docs/hugging-face-backend-deployment.md).
