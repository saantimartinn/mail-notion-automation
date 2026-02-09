# Mail → Notion Automation (Refactor Example)

This repository contains a **refactored version of a project originally designed and implemented by me**, which is currently running in production within a real company environment.

For **privacy and confidentiality reasons**, the original production codebase cannot be shared publicly.  
This repository provides a **functionally equivalent refactor**, preserving the overall architecture, patterns, and technical decisions, while removing or abstracting any company-specific, sensitive, or identifying information.

The purpose of this refactor is to **demonstrate the technical approach, design decisions, and integration patterns** used in the original system—without exposing private business logic, credentials, or data.

⚠️ **Important note**  
This code is intended as a **technical reference and portfolio example**. It does not contain credentials, secrets, or confidential information.

---

## 🧩 What does this service do?

- Connects to a **Gmail inbox via IMAP**
- Detects new incoming emails based on UID tracking
- Filters emails by sender and basic content rules
- Parses structured data from the email body
- Creates entries in a **Notion database**
- Prevents duplicate processing using email UID
- Stores execution logs and state in **Google Cloud Storage**
- Exposes an **HTTP endpoint (Flask)** for remote execution (e.g. Cloud Run)

---

## 📁 Project structure

```text
.
├── main.py            # Main application (Flask + email / Notion logic)
├── gcs_helpers.py     # Google Cloud Storage helpers
├── requirements.txt   # Python dependencies
├── Dockerfile         # Docker image definition
├── .dockerignore      # Docker build exclusions
├── .gitignore         # Git exclusions
```

---

## 🔐 Secret management

This project **does NOT include secrets in the codebase**.

All sensitive configuration is loaded from **Google Secret Manager**, using:

- Application Default Credentials (ADC)
- An environment variable pointing to the secret resource

The secret is expected to contain a JSON payload with at least:

- A Gmail account (email + app password)
- A Notion API token
- A Notion database ID
- Email filtering configuration (allowed sender, etc.)

---

## 🌍 Environment variables

### Required

```bash
GCP_SECRET_NAME=<secret-resource-name>
```

Example:

```
projects/123456/secrets/my-secret/versions/latest
```

### Optional

```bash
DRY_RUN=1
LOG_LEVEL=INFO
GCS_BUCKET_NAME=<bucket-name>
```

---

## ▶️ Run locally

**Requirements:**
- Python 3.10+
- Google Cloud SDK (`gcloud`)
- Application Default Credentials enabled

```bash
gcloud auth application-default login
pip install -r requirements.txt
export GCP_SECRET_NAME="projects/.../secrets/.../versions/latest"
python main.py
```

---

## 🐳 Run with Docker

```bash
docker build -t mail-notion-automation .
docker run -p 8080:8080 \
  -e GCP_SECRET_NAME="projects/.../secrets/.../versions/latest" \
  mail-notion-automation
```

---

## ☁️ Recommended deployment

This service is designed to run on:

- Google Cloud Run
- Google Compute Engine
- Any environment with Application Default Credentials enabled

---

## 🧪 DRY RUN mode

To test the full workflow without writing to Notion or Google Cloud Storage:

```bash
export DRY_RUN=1
```

All external operations will be simulated and only logs will be generated.

---

## 📌 Disclaimer

This repository is a **refactored technical example** created for demonstration and portfolio purposes.  
It does not expose real production data, credentials, or confidential company information.

---

## 📄 License

Free to use for educational and reference purposes.
