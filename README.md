# Daily Genetics/genomics + ML Paper Deliver

This repository contains Python scripts for automatically collecting recent papers related to AI, machine learning, genetics, genomics, and computational biology, then sending organized email digests.

The project is designed to track both broad AI/genomics trends and more practical machine learning methods that may be useful for genetics and genomics research.

## Main features

* Searches recent papers from multiple sources:

  * bioRxiv
  * medRxiv
  * arXiv
  * PubMed-indexed journals
* Sends HTML email digests.
* Supports local/server execution using `cron`.
* Supports cloud execution using GitHub Actions.
* Uses environment variables for email credentials.
* Filters and scores papers by topic relevance and heuristic quality.
* Adds topic labels and short summaries for easier scanning.

## Topics covered

The current keyword filters prioritize:

* Genomic foundation models
* DNA language models
* Single-cell AI and foundation models
* Variant effect prediction
* Regulatory genomics
* Multi-omics integration
* DNA methylation and epigenomics
* scHi-C and 3D genome structure
* Chromatin conformation and genome folding
* Hi-C contact maps and TADs
* Graph neural networks
* Graph representation learning
* Variational autoencoders
* Generative models
* Benchmarking and reproducible computational biology tools

## Repository structure

```text
.
├── genetics_ai_updates.py
├── genetics_ml_methods_updates.py
├── requirements.txt
├── README.md
├── .gitignore
└── .github/
    └── workflows/
        └── daily_digest.yml
```

## Scripts

### `genetics_ai_updates.py`

Broad AI/genomics digest.

This script searches for recent papers related to AI, machine learning, foundation models, single-cell genomics, epigenomics, methylation, 3D genome structure, graph neural networks, VAEs, and other computational genomics topics.

It searches preprint servers and PubMed-indexed journals, then sends an organized email digest.

### `genetics_ml_methods_updates.py`

Focused digest for ML methods useful in genetics and genomics research.

This script is intended to highlight method papers, benchmarks, tools, and modeling approaches that may be useful for genetics, genomics, single-cell analysis, regulatory genomics, and multi-omics research.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Jihua-Liu/genetics-paper-digest.git
cd genetics-paper-digest
```

### 2. Create a conda environment

```bash
conda create -n paper_digest python=3.11 -y
conda activate paper_digest
pip install -r requirements.txt
```

Alternatively, if you already have a Python 3.10+ environment:

```bash
pip install -r requirements.txt
```

### 3. Create a `.env` file

Create a `.env` file in the repository folder:

```bash
EMAIL_SENDER=your_sender_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
EMAIL_RECEIVER=your_receiver_email@example.com
```

For Gmail, use a Gmail App Password rather than your normal Gmail password.

The `.env` file should not be committed to GitHub. It is ignored by `.gitignore`.

## Local testing

After creating the environment and `.env` file, test manually:

```bash
python genetics_ai_updates.py
python genetics_ml_methods_updates.py
```

If the setup works, you should receive email digests.

## Option 1: Run on a server with cron

This is the recommended option if you have access to a lab server that stays on.

Example server path:

```bash
/lstore1/jliu787/resource/genetics-paper-digest
```

Example conda Python path:

```bash
/u/j/i/jihua/anaconda3/envs/paper_digest/bin/python
```

Edit crontab:

```bash
crontab -e
```

Add:

```bash
0 14 * * * cd /lstore1/jliu787/resource/genetics-paper-digest && /u/j/i/jihua/anaconda3/envs/paper_digest/bin/python genetics_ai_updates.py >> genetics_ai_updates.log 2>&1
5 14 * * * cd /lstore1/jliu787/resource/genetics-paper-digest && /u/j/i/jihua/anaconda3/envs/paper_digest/bin/python genetics_ml_methods_updates.py >> genetics_ml_methods_updates.log 2>&1
```

This sends:

* `genetics_ai_updates.py` every day at 2:00 PM server time
* `genetics_ml_methods_updates.py` every day at 2:05 PM server time

Check cron jobs:

```bash
crontab -l
```

Check logs:

```bash
tail -50 genetics_ai_updates.log
tail -50 genetics_ml_methods_updates.log
```

## Option 2: Run with GitHub Actions

GitHub Actions can run the workflow on GitHub-hosted runners instead of a local machine or lab server.

Add these repository secrets:

```text
EMAIL_SENDER
EMAIL_PASSWORD
EMAIL_RECEIVER
```

In GitHub:

```text
Repository → Settings → Secrets and variables → Actions → New repository secret
```

The workflow file is located at:

```text
.github/workflows/daily_digest.yml
```

Example daily schedule:

```yaml
on:
  schedule:
    - cron: "20 14 * * *"
  workflow_dispatch:
```

GitHub Actions cron uses UTC time. During daylight saving time in Madison/Chicago, `14:20 UTC` is `9:20 AM` Central Time.

## Server vs GitHub Actions

| Option            | Pros                                                               | Cons                                                             |
| ----------------- | ------------------------------------------------------------------ | ---------------------------------------------------------------- |
| Lab server + cron | Reliable if server is always on; easy logs; uses your local `.env` | Depends on server policy and SMTP access                         |
| GitHub Actions    | Does not depend on laptop/server; easy manual runs                 | Requires GitHub Secrets; scheduled runs can sometimes be delayed |
| Laptop + cron     | Simple for local testing                                           | Fails if laptop is asleep or closed                              |

For regular use, running on a lab server or GitHub Actions is better than running cron on a laptop.

## Security notes

* Never commit `.env`.
* Never commit Gmail App Passwords.
* Use GitHub Secrets if running with GitHub Actions.
* Check tracked files before making the repository public:

```bash
git ls-files | grep .env
git log --all -- .env
```

Both should return nothing.

## Disclaimer

This project uses keyword filtering and heuristic scoring. It is meant for literature monitoring and paper discovery, not for systematic review or complete literature coverage.
