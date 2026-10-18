# Google Cloud Infrastructure Details

- **Project ID:** pocket-lawyer-431614
- **Primary Region:** europe-west3 (Frankfurt, Germany / EU)
- **Primary Account / Owner:** leskivmr@gmail.com
- **Current GCP services:**
  - Cloud Run available in `europe-west3`
  - Cloud Storage available in `europe-west3` / `eu` multi-region
  - Vertex AI / Gemini in EU endpoint (`europe-west3` / `eu`)
- **Authentication:**
  - Google Cloud CLI authenticated under `leskivmr@gmail.com`.
  - For ADC in runner environments: run `gcloud auth application-default login` or export `GOOGLE_APPLICATION_CREDENTIALS` service account key if configured.
