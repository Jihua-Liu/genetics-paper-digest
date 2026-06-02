import os
import re
import smtplib
import html
import requests
import feedparser
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv


# =========================
# User settings
# =========================

DAYS_BACK = 2
MAX_ARXIV_RESULTS = 30
MAX_BIORXIV_RESULTS_PER_SERVER = 75

MAX_PAPERS_PER_EMAIL = 20
SUMMARY_SENTENCES = 2

TOPICS = {
    "Variant Effect Prediction / Variant Interpretation": [
        "variant effect prediction", "variant interpretation", "variant pathogenicity",
        "pathogenic variant", "missense variant", "noncoding variant",
        "regulatory variant", "variant prioritization", "variant annotation",
        "VUS", "variants of uncertain significance"
    ],

    "Regulatory Genomics / Sequence-to-Function Models": [
        "regulatory genomics", "sequence-to-function", "gene regulation",
        "enhancer", "promoter", "transcription factor binding",
        "chromatin accessibility", "ATAC-seq", "ChIP-seq",
        "cis-regulatory", "noncoding regulatory", "motif discovery"
    ],

    "Single-cell ML / Cell Foundation Models": [
        "single-cell", "single cell", "scRNA-seq", "scATAC-seq",
        "single-cell foundation model", "cell foundation model",
        "cell type annotation", "cell state", "cell embedding",
        "perturbation prediction", "cell fate", "geneformer", "scGPT",
        "UCE", "scFoundation"
    ],

    "Multi-omics / Data Integration": [
        "multi-omics", "multiomics", "multimodal omics", "data integration",
        "joint embedding", "cross-modal", "spatial transcriptomics",
        "transcriptomics", "proteomics", "epigenomics",
        "single-cell multiomics"
    ],

    "Epigenomics / Methylation ML": [
        "DNA methylation", "methylation", "epigenomic", "epigenetic",
        "bisulfite sequencing", "methylome", "chromatin state",
        "single-cell methylation", "methylation prediction"
    ],

    "GWAS / Polygenic Risk / Statistical Genetics ML": [
        "GWAS", "genome-wide association", "polygenic risk score",
        "PRS", "fine-mapping", "eQTL", "sQTL", "colocalization",
        "heritability", "genetic architecture", "gene prioritization"
    ],

    "Causal ML / Perturbation / Gene Networks": [
        "causal inference", "causal machine learning", "causal discovery",
        "perturbation", "CRISPR screen", "gene regulatory network",
        "network inference", "graph neural network", "GNN",
        "Bayesian network"
    ],

    "Benchmarking / Reproducibility / Useful Tools": [
        "benchmark", "benchmarking", "reproducibility", "evaluation",
        "software", "tool", "pipeline", "dataset", "database",
        "domain shift", "batch effect", "generalization",
        "interpretability", "explainable AI", "uncertainty"
    ]
}

GENERAL_INCLUDE_TERMS = [
    # ML method terms
    "machine learning", "deep learning", "artificial intelligence",
    "foundation model", "large language model", "transformer",
    "self-supervised", "contrastive learning", "representation learning",
    "generative model", "diffusion model", "graph neural network",
    "neural network", "autoencoder", "variational autoencoder",
    "random forest", "xgboost", "causal inference", "causal discovery",
    "bayesian", "uncertainty", "interpretability",

    # Genetics/genomics application terms
    "genomics", "genetics", "genome", "DNA", "RNA",
    "variant", "GWAS", "polygenic risk", "eQTL", "fine-mapping",
    "gene regulation", "regulatory genomics", "single-cell",
    "single cell", "methylation", "epigenomics", "chromatin",
    "transcriptomics", "multi-omics", "spatial transcriptomics",
    "CRISPR", "perturbation"
]

GENERAL_EXCLUDE_TERMS = [
    "clinical trial protocol",
    "case report",
    "survey only"
]


# =========================
# Helpers
# =========================

def normalize_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<.*?>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def make_two_sentence_summary(title: str, abstract: str) -> str:
    """
    Simple extractive two-sentence summary.
    It picks the most informative sentences from the abstract.
    No OpenAI API needed.
    """
    abstract = normalize_text(abstract)

    if not abstract:
        return "No abstract was available. Check the paper directly for details."

    # Split abstract into sentences
    sentences = re.split(r'(?<=[.!?])\s+', abstract)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

    if len(sentences) <= 2:
        return " ".join(sentences)

    priority_terms = [
        "foundation model", "single-cell", "single cell", "genomic",
        "methylation", "epigenomic", "variant", "regulatory",
        "transformer", "deep learning", "machine learning",
        "multi-omics", "benchmark", "prediction", "perturbation",
        "gene expression", "chromatin"
    ]

    def sentence_score(sentence: str) -> int:
        lower = sentence.lower()
        score = 0

        for term in priority_terms:
            if term in lower:
                score += 2

        # Prefer sentences that mention the main method/result
        for term in ["we propose", "we present", "we introduce", "we develop", "we show", "our results"]:
            if term in lower:
                score += 3

        # Avoid super short or super long sentences
        if 80 <= len(sentence) <= 300:
            score += 1

        return score

    ranked = sorted(
        enumerate(sentences),
        key=lambda x: sentence_score(x[1]),
        reverse=True
    )

    # Pick top 2, then restore original order
    selected_indices = sorted([idx for idx, sent in ranked[:2]])
    selected = [sentences[i] for i in selected_indices]

    return " ".join(selected)

def contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def assign_topics(title: str, abstract: str) -> list[str]:
    combined = f"{title} {abstract}".lower()
    matched = []

    for topic, terms in TOPICS.items():
        if any(term.lower() in combined for term in terms):
            matched.append(topic)

    if not matched:
        matched.append("Other Relevant Papers")

    return matched

def score_paper(title: str, abstract: str) -> int:
    combined = f"{title} {abstract}".lower()
    score = 0

    very_high_value_terms = [
        "variant effect prediction",
        "regulatory variant",
        "single-cell foundation model",
        "cell foundation model",
        "multi-omics integration",
        "perturbation prediction",
        "gene regulatory network",
        "methylation prediction",
        "causal inference",
        "fine-mapping",
        "polygenic risk",
        "benchmark"
    ]

    high_value_terms = [
        "foundation model", "transformer", "self-supervised",
        "representation learning", "graph neural network",
        "single-cell", "single cell", "genomic", "methylation",
        "epigenomic", "variant", "regulatory genomics",
        "gene expression", "chromatin", "gwas", "eqtl",
        "interpretability", "uncertainty"
    ]

    for term in very_high_value_terms:
        if term in combined:
            score += 5

    for term in high_value_terms:
        if term in combined:
            score += 3

    # Prefer papers that sound like usable tools/methods
    for term in ["we present", "we introduce", "we developed", "software", "tool", "pipeline", "benchmark"]:
        if term in combined:
            score += 2

    return score


def is_relevant(title: str, abstract: str) -> bool:
    combined = f"{title} {abstract}".lower()

    if contains_any(combined, GENERAL_EXCLUDE_TERMS):
        return False

    has_ml_method = contains_any(combined, [
        "machine learning", "deep learning", "artificial intelligence",
        "foundation model", "large language model", "transformer",
        "neural network", "self-supervised", "contrastive learning",
        "representation learning", "generative model", "diffusion",
        "graph neural network", "gnn", "autoencoder", "bayesian",
        "causal inference", "causal discovery", "xgboost",
        "random forest", "benchmark", "software", "tool"
    ])

    has_genetics_application = contains_any(combined, [
        "genomics", "genetics", "genome", "dna", "rna",
        "variant", "gwas", "polygenic", "eqtl", "fine-mapping",
        "gene regulation", "regulatory", "single-cell", "single cell",
        "methylation", "epigenomic", "chromatin", "transcriptomics",
        "multi-omics", "spatial transcriptomics", "crispr",
        "perturbation", "gene expression"
    ])

    has_useful_research_task = contains_any(combined, [
        "prediction", "annotation", "prioritization", "classification",
        "integration", "embedding", "representation", "benchmark",
        "interpretation", "inference", "discovery", "fine-mapping",
        "variant effect", "cell type", "cell state", "gene regulatory network"
    ])

    return has_ml_method and has_genetics_application and has_useful_research_task


# =========================
# Fetch bioRxiv / medRxiv
# =========================

def fetch_biorxiv_like(server: str, days_back: int = 2) -> list[dict]:
    """
    server: "biorxiv" or "medrxiv"
    """
    end = date.today()
    start = end - timedelta(days=days_back)
    interval = f"{start.isoformat()}/{end.isoformat()}"

    papers = []
    cursor = 0

    while cursor < MAX_BIORXIV_RESULTS_PER_SERVER:
        url = f"https://api.biorxiv.org/details/{server}/{interval}/{cursor}/json"

        try:
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error fetching {server}: {e}")
            break

        collection = data.get("collection", [])
        if not collection:
            break

        for item in collection:
            title = normalize_text(item.get("title", ""))
            abstract = normalize_text(item.get("abstract", ""))
            doi = item.get("doi", "")
            date_posted = item.get("date", "")
            authors = normalize_text(item.get("authors", ""))
            category = item.get("category", "")

            if is_relevant(title, abstract):
                papers.append({
                    "source": server,
                    "title": title,
                    "abstract": abstract,
                    "authors": authors,
                    "date": date_posted,
                    "category": category,
                    "url": f"https://doi.org/{doi}" if doi else "",
                    "score": score_paper(title, abstract),
                    "topics": assign_topics(title, abstract)
                })

        cursor += len(collection)

        if len(collection) < 100:
            break

    return papers


# =========================
# Fetch arXiv
# =========================

def fetch_arxiv(days_back: int = 2, max_results: int = 30) -> list[dict]:
    """
    arXiv API does not filter perfectly by submitted date in simple mode,
    so we query relevant categories/terms and then keep recent-ish entries.
    """
    query = (
        'all:"genomics" OR all:"genetics" OR all:"single-cell" OR '
        'all:"methylation" OR all:"variant effect" OR all:"epigenomics" OR '
        'all:"transcriptomics"'
    )

    url = (
        "http://export.arxiv.org/api/query?"
        f"search_query={requests.utils.quote(query)}"
        "&sortBy=submittedDate"
        "&sortOrder=descending"
        f"&max_results={max_results}"
    )

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        print(f"Error fetching arXiv: {e}")
        return []

    cutoff = date.today() - timedelta(days=days_back + 2)
    papers = []

    for entry in feed.entries:
        title = normalize_text(entry.get("title", ""))
        abstract = normalize_text(entry.get("summary", ""))
        authors = ", ".join([a.name for a in entry.get("authors", [])])
        published = entry.get("published", "")[:10]
        link = entry.get("link", "")

        try:
            published_date = date.fromisoformat(published)
        except Exception:
            published_date = date.today()

        if published_date < cutoff:
            continue

        if is_relevant(title, abstract):
            papers.append({
                "source": "arXiv",
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "date": published,
                "category": ", ".join([t.get("term", "") for t in entry.get("tags", [])]),
                "url": link,
                "score": score_paper(title, abstract),
                "topics": assign_topics(title, abstract)
            })

    return papers


# =========================
# Email formatting
# =========================

def short_abstract(text: str, max_chars: int = 700) -> str:
    text = normalize_text(text)
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def build_email_html(papers: list[dict]) -> str:
    today = date.today().isoformat()

    if not papers:
        return f"""
        <html>
        <body>
        <h2>Daily AI + Genomics Paper Digest — {today}</h2>
        <p>No highly relevant new papers found today based on your current filters.</p>
        </body>
        </html>
        """

    # Sort by relevance and keep only top 10
    papers = sorted(papers, key=lambda x: x["score"], reverse=True)
    papers = papers[:MAX_PAPERS_PER_EMAIL]

    html_parts = [
        "<html><body>",
        f"<h2>Daily AI + Genomics Paper Digest — {today}</h2>",
        f"<p>Showing the top <b>{len(papers)}</b> most relevant papers from bioRxiv, medRxiv, and arXiv.</p>",
        "<p><b>Priority topics:</b> single-cell AI, genomic foundation models, methylation/epigenomics, variant effect prediction, and multimodal omics.</p>",
        "<hr>"
    ]

    for i, paper in enumerate(papers, start=1):
        title = html.escape(paper["title"])
        authors = html.escape(paper["authors"])
        summary = html.escape(make_two_sentence_summary(paper["title"], paper["abstract"]))
        source = html.escape(paper["source"])
        category = html.escape(paper.get("category", ""))
        paper_date = html.escape(paper["date"])
        url = paper["url"]
        topics = html.escape(", ".join(paper["topics"]))

        html_parts.append(f"""
        <div style="margin-bottom: 22px; padding-bottom: 16px; border-bottom: 1px solid #ddd;">
            <p><b>{i}. <a href="{url}">{title}</a></b></p>
            <p><b>Source:</b> {source} | <b>Date:</b> {paper_date}</p>
            <p><b>Category:</b> {category}</p>
            <p><b>Authors:</b> {authors}</p>
            <p><b>Matched topics:</b> {topics}</p>
            <p><b>Two-sentence summary:</b> {summary}</p>
        </div>
        """)

    html_parts.append("""
        <p style="font-size: 12px; color: #666;">
        This digest is automatically generated from recent bioRxiv, medRxiv, and arXiv papers using keyword filtering and relevance scoring.
        </p>
        </body></html>
    """)

    return "\n".join(html_parts)


def send_email(subject: str, html_body: str) -> None:
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver = os.getenv("EMAIL_RECEIVER")

    if not sender or not password or not receiver:
        raise ValueError("Missing EMAIL_SENDER, EMAIL_PASSWORD, or EMAIL_RECEIVER in .env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())


# =========================
# Main
# =========================

def main():
    all_papers = []

    all_papers.extend(fetch_biorxiv_like("biorxiv", DAYS_BACK))
    all_papers.extend(fetch_biorxiv_like("medrxiv", DAYS_BACK))
    all_papers.extend(fetch_arxiv(DAYS_BACK, MAX_ARXIV_RESULTS))

    # Deduplicate by title
    seen = set()
    deduped = []
    for paper in all_papers:
        key = paper["title"].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(paper)

    html_body = build_email_html(deduped)
    subject = f"Daily Useful ML Methods for Genetics Research — {date.today().isoformat()}"

    send_email(subject, html_body)
    print(f"Sent digest with {len(deduped)} papers.")


if __name__ == "__main__":
    load_dotenv()
    main()