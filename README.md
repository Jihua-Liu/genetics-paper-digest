# Genetics AI Paper Digest

A small Python + GitHub Actions project that automatically searches for recent papers related to AI, machine learning, genetics, genomics, single-cell analysis, epigenomics, 3D genome structure, and related computational biology methods, then sends an organized email digest.

This project was built to help track new papers from:

- bioRxiv
- medRxiv
- arXiv
- PubMed-indexed journals

The digest prioritizes topics such as:

- Genomic foundation models
- DNA language models
- Single-cell AI and foundation models
- Variant effect prediction
- Regulatory genomics
- Multi-omics integration
- DNA methylation and epigenomics
- scHi-C and 3D genome structure
- Graph neural networks
- Variational autoencoders
- Benchmarking and reproducible computational biology tools

## Features

- Searches multiple sources for recent papers.
- Filters papers by AI/ML and genetics/genomics relevance.
- Adds topic labels to each paper.
- Scores papers using a simple relevance and quality heuristic.
- Sends an HTML email digest.
- Runs automatically using GitHub Actions.
- Uses GitHub Secrets for email credentials, so no password is stored in the repository.

## Repository structure

```text
.
├── genetics_ai_updates.py
├── genetics_ml_methods_updates.py
├── requirements.txt
├── .github/
│   └── workflows/
│       └── daily_digest.yml
└── README.md
