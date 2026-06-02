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
import xml.etree.ElementTree as ET

# =========================
# User settings
# =========================

DAYS_BACK = 15
MAX_ARXIV_RESULTS = 100
MAX_BIORXIV_RESULTS_PER_SERVER = 100

MAX_PAPERS_PER_EMAIL = 20
SUMMARY_SENTENCES = 2

MIN_QUALITY_SCORE = 10

MAX_PUBMED_RESULTS = 40

TARGET_JOURNALS = [
    "PLOS Computational Biology",
    "Bioinformatics",
    "Genome Biology",
    "Genome Research",
    "Nature Methods",
    "Nature Biotechnology",
    "Nature Genetics",
    "Nucleic Acids Research",
    "Cell Systems",
    "PLOS Genetics",
    "PLOS Biology",
    "Briefings in Bioinformatics",
    "BMC Bioinformatics",
    "GigaScience",
    "Patterns",
    "Nature Communications",
    "Communications Biology",
    "Cell Genomics"
]

PUBMED_TOPIC_TERMS = [
    # AI / ML
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "foundation model",
    "large language model",
    "transformer",
    "self-supervised learning",
    "representation learning",
    "generative model",
    "diffusion model",
    "variational autoencoder",
    "autoencoder",
    "graph neural network",
    "graph transformer",
    "graph representation learning",

    # genetics / genomics
    "genomics",
    "genetics",
    "single-cell",
    "single cell",
    "scRNA-seq",
    "scATAC-seq",
    "methylation",
    "epigenomics",
    "chromatin",
    "variant effect",
    "regulatory variant",
    "GWAS",
    "eQTL",
    "multi-omics",
    "spatial transcriptomics",

    # your added interests
    "Hi-C",
    "single-cell Hi-C",
    "scHi-C",
    "3D genome",
    "3D chromatin",
    "chromatin conformation",
    "chromatin architecture",
    "genome folding",
    "TAD",
    "contact map",
    "gene regulatory network"
]

TOPICS = {
    "Single-cell AI / Foundation Models": [
        "single-cell", "single cell", "scrna", "scRNA", "scatac", "scATAC",
        "cell foundation model", "geneformer", "scgpt", "cellplm",
        "cell type annotation", "perturbation prediction"
    ],

    "scHi-C / 3D Genome / Chromatin Structure": [
        "scHi-C", "single-cell Hi-C", "single cell Hi-C",
        "single-cell chromatin conformation", "chromatin conformation",
        "chromosome conformation", "3D genome", "3D genome organization",
        "3D chromatin", "chromatin structure", "chromatin architecture",
        "higher-order chromatin", "genome folding", "chromosome folding",
        "TAD", "TADs", "topologically associating domain",
        "A/B compartment", "chromatin compartment",
        "contact map", "Hi-C contact map", "contact matrix",
        "loop extrusion", "chromatin loop", "enhancer-promoter contact",
        "genome architecture", "spatial genome organization",
        "Micro-C", "HiChIP", "PLAC-seq"
    ],

    "Genomic Foundation Models / DNA Language Models": [
        "genomic foundation model", "dna language model", "dnabert",
        "nucleotide transformer", "hyenadna", "caduceus", "evo",
        "sequence model", "genome language model"
    ],

    "Variant Effect / Regulatory Genomics": [
        "variant effect", "variant prediction", "regulatory variant",
        "enhancer", "promoter", "transcription factor", "chromatin",
        "gene regulation", "noncoding variant", "splicing"
    ],

    "Epigenomics / Methylation": [
        "methylation", "dna methylation", "epigenomic", "epigenetics",
        "chromatin accessibility", "atac", "bisulfite", "single-cell methylation", "scmethylation",
        "amethyst", "scalemethyl"

    ],

    "Multimodal Omics / Integration": [
        "multi-omics", "multiomics", "multimodal", "data integration",
        "spatial transcriptomics", "proteomics", "transcriptomics",
        "omics foundation model"
    ],

    "Graph ML / VAE / Generative Models": [
        "graph neural network", "graph neural networks", "GNN",
        "graph representation learning", "graph embedding",
        "graph autoencoder", "variational graph autoencoder",
        "VGAE", "graph transformer", "geometric deep learning",
        "network embedding", "gene regulatory network",
        "variational autoencoder", "VAE", "autoencoder",
        "generative model", "diffusion model", "latent representation",
        "latent variable model"
    ],

    "Methods / Benchmarking": [
        "benchmark", "evaluation", "reproducibility", "domain shift",
        "batch effect", "uncertainty", "calibration", "interpretability"
    ],
}

GENERAL_INCLUDE_TERMS = [
    "machine learning", "deep learning", "artificial intelligence", "foundation model",
    "large language model", "transformer", "self-supervised", "representation learning",
    "generative model", "diffusion", "graph neural network", "neural network",
    "genomics", "genetics", "single-cell", "epigenomics", "methylation",
    "transcriptomics", "multi-omics", "variant",

    # New scHi-C / 3D genome terms
    "scHi-C", "single-cell Hi-C", "single cell Hi-C",
    "Hi-C", "Micro-C", "HiChIP", "PLAC-seq",
    "3D genome", "3D chromatin", "chromatin conformation",
    "chromosome conformation", "chromatin architecture",
    "genome folding", "chromosome folding",
    "TAD", "topologically associating domain",
    "A/B compartment", "contact map", "contact matrix",
    "chromatin loop", "enhancer-promoter contact",

    # New VAE / graph ML terms
    "variational autoencoder", "VAE", "autoencoder",
    "graph neural network", "graph neural networks", "GNN",
    "graph representation learning", "graph embedding",
    "graph autoencoder", "variational graph autoencoder",
    "VGAE", "graph transformer", "geometric deep learning",
    "network embedding", "latent variable model",
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

    high_value_terms = [
        "foundation model", "single-cell", "single cell", "genomic",
        "methylation", "variant effect", "multi-omics", "transformer",
        "self-supervised", "benchmark", "perturbation",

        # New interests
        "schi-c", "single-cell hi-c", "single cell hi-c",
        "hi-c", "micro-c", "3d genome", "3d chromatin",
        "chromatin conformation", "chromatin architecture",
        "genome folding", "tad", "contact map", "contact matrix",
        "variational autoencoder", "vae", "graph neural network",
        "gnn", "graph transformer", "graph autoencoder",
        "variational graph autoencoder"
    ]

    for term in high_value_terms:
        if term in combined:
            score += 3

    for term in GENERAL_INCLUDE_TERMS:
        if term.lower() in combined:
            score += 1

    return score


def quality_score_paper(title: str, abstract: str, source: str = "", category: str = "", journal: str = "") -> int:
    """
    Estimate whether a paper is likely useful/high quality for genetics/genomics ML.
    This is not perfect, but much better than keyword filtering alone.
    """
    combined = f"{title} {abstract} {source} {category} {journal}".lower()
    score = 0

    # Strong positive signals: likely useful methods
    strong_method_terms = [
        "we introduce", "we present", "we propose", "we develop",
        "benchmark", "systematic evaluation", "state-of-the-art",
        "open-source", "software", "tool", "pipeline", "framework",
        "large-scale", "multi-cohort", "cross-validation",
        "external validation", "independent validation",
        "reproducible", "github", "code available"
    ]

    for term in strong_method_terms:
        if term in combined:
            score += 3

    # Strong biology/genomics relevance
    strong_genomics_terms = [
        "variant effect prediction", "regulatory variant",
        "single-cell foundation model", "cell foundation model",
        "single-cell", "single cell", "multi-omics", "multiomics",
        "dna methylation", "methylation", "epigenomics",
        "chromatin accessibility", "regulatory genomics",
        "gene regulatory network", "gwas", "fine-mapping",
        "eqtl", "perturbation prediction", "crispr screen"
    ]

    for term in strong_genomics_terms:
        if term in combined:
            score += 3

    # ML method strength
    ml_terms = [
        "foundation model", "transformer", "self-supervised",
        "contrastive learning", "representation learning",
        "graph neural network", "gnn", "diffusion model",
        "generative model", "deep learning", "machine learning",
        "causal inference", "bayesian", "uncertainty",
        "interpretability"
    ]

    for term in ml_terms:
        if term in combined:
            score += 2

    # Better if it sounds like a real applied method paper
    useful_task_terms = [
        "prediction", "classification", "annotation", "integration",
        "prioritization", "imputation", "denoising", "inference",
        "discovery", "embedding", "representation", "generalization"
    ]

    for term in useful_task_terms:
        if term in combined:
            score += 1

    # Negative signals: often lower priority for your digest
    low_priority_terms = [
        "protocol", "perspective", "commentary", "editorial",
        "letter to the editor", "case report",
        "questionnaire", "survey study", "cross-sectional study",
        "clinical trial protocol"
    ]

    for term in low_priority_terms:
        if term in combined:
            score -= 5

    # Too vague: says AI but not much genomics method content
    vague_ai_terms = [
        "chatgpt", "large language models in healthcare",
        "artificial intelligence in medicine",
        "review of artificial intelligence"
    ]

    for term in vague_ai_terms:
        if term in combined:
            score -= 3

    return score

def is_relevant(title: str, abstract: str) -> bool:
    combined = f"{title} {abstract}".lower()

    if contains_any(combined, GENERAL_EXCLUDE_TERMS):
        return False

    has_ai = contains_any(combined, [
        "machine learning", "deep learning", "artificial intelligence",
        "foundation model", "transformer", "neural network",
        "self-supervised", "representation learning", "generative model",
        "large language model", "diffusion", "graph neural network",
        "variational autoencoder", "vae", "autoencoder",
        "graph neural networks", "gnn", "graph representation learning",
        "graph embedding", "graph autoencoder",
        "variational graph autoencoder", "vgae", "graph transformer",
        "geometric deep learning", "latent variable model"
    ])

    has_genomics = contains_any(combined, [
        "genomics", "genetics", "genome", "dna", "rna", "single-cell",
        "single cell", "methylation", "epigenomic", "chromatin",
        "variant", "gene expression", "transcriptomics", "multi-omics",
        "spatial transcriptomics","hi-c", "schic", "scHi-C", "single-cell hi-c",
        "single cell hi-c", "micro-c", "hichip", "plac-seq",
        "chromatin conformation", "chromosome conformation",
        "3d genome", "3d chromatin", "chromatin architecture",
        "genome folding", "chromosome folding", "tad",
        "topologically associating domain", "a/b compartment",
        "contact map", "contact matrix", "chromatin loop",
        "enhancer-promoter contact"
    ])

    return has_ai and has_genomics


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
                    "doi": doi,
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
    'all:"transcriptomics" OR all:"Hi-C" OR all:"single-cell Hi-C" OR '
    'all:"3D genome" OR all:"chromatin conformation" OR '
    'all:"chromatin architecture" OR all:"contact map" OR '
    'all:"graph neural network" OR all:"variational autoencoder" OR '
    'all:"VAE" OR all:"graph transformer"'
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

def fetch_pubmed_journal_articles(days_back: int = 7, max_results: int = 40) -> list[dict]:
    """
    Fetch recent journal-published papers from PubMed using:
    target journals + topic terms + publication date window.

    This catches papers from journals such as PLOS Computational Biology,
    Bioinformatics, Genome Biology, Nature Methods, etc.
    """
    end = date.today()
    start = end - timedelta(days=days_back)

    journal_query = " OR ".join([f'"{journal}"[Journal]' for journal in TARGET_JOURNALS])
    topic_query = " OR ".join([f'"{term}"[Title/Abstract]' for term in PUBMED_TOPIC_TERMS])

    query = (
        f"({journal_query}) AND "
        f"({topic_query}) AND "
        f'("{start.isoformat()}"[Date - Publication] : "{end.isoformat()}"[Date - Publication])'
    )

    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": max_results,
        "sort": "pub date"
    }

    try:
        search_resp = requests.get(search_url, params=search_params, timeout=20)
        search_resp.raise_for_status()
        pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"Error searching PubMed: {e}")
        return []

    if not pmids:
        return []

    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml"
    }

    try:
        fetch_resp = requests.get(fetch_url, params=fetch_params, timeout=30)
        fetch_resp.raise_for_status()
        root = ET.fromstring(fetch_resp.text)
    except Exception as e:
        print(f"Error fetching PubMed records: {e}")
        return []

    papers = []

    for article in root.findall(".//PubmedArticle"):
        medline = article.find(".//MedlineCitation")
        article_info = article.find(".//Article")

        if article_info is None:
            continue

        title = normalize_text("".join(article_info.findtext("ArticleTitle", default="")))

        abstract_parts = []
        for abstract_text in article_info.findall(".//AbstractText"):
            label = abstract_text.attrib.get("Label")
            text = "".join(abstract_text.itertext())
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)

        abstract = normalize_text(" ".join(abstract_parts))

        journal = article_info.findtext(".//Journal/Title", default="")
        journal = normalize_text(journal)

        pub_date_node = article_info.find(".//JournalIssue/PubDate")
        pub_year = pub_date_node.findtext("Year", default="") if pub_date_node is not None else ""
        pub_month = pub_date_node.findtext("Month", default="") if pub_date_node is not None else ""
        pub_day = pub_date_node.findtext("Day", default="") if pub_date_node is not None else ""
        pub_date = " ".join([x for x in [pub_year, pub_month, pub_day] if x])

        authors_list = []
        for author in article_info.findall(".//Author"):
            last = author.findtext("LastName", default="")
            initials = author.findtext("Initials", default="")
            if last:
                authors_list.append(f"{last} {initials}".strip())

        authors = ", ".join(authors_list[:12])
        if len(authors_list) > 12:
            authors += ", et al."

        pmid = medline.findtext("PMID", default="") if medline is not None else ""

        doi = ""
        for article_id in article.findall(".//ArticleId"):
            if article_id.attrib.get("IdType") == "doi":
                doi = article_id.text or ""
                break

        if doi:
            url = f"https://doi.org/{doi}"
        elif pmid:
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        else:
            url = ""

        if not title:
            continue

        if is_relevant(title, abstract):
            paper = {
                "source": "PubMed",
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "date": pub_date,
                "category": journal,
                "url": url,
                "score": score_paper(title, abstract),
                "topics": assign_topics(title, abstract),
                "journal": journal,
                "pmid": pmid,
                "doi": doi
            }

            papers.append(paper)

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
    papers = sorted(
        papers,
        key=lambda x: (x.get("quality_score", 0), x.get("score", 0)),
        reverse=True)
    papers = papers[:MAX_PAPERS_PER_EMAIL]

    html_parts = [
        "<html><body>",
        f"<h2>Daily AI + Genomics Paper Digest — {today}</h2>",
        f"<p>Showing the top <b>{len(papers)}</b> most relevant papers from bioRxiv, medRxiv, arXiv, and PubMed journal searches.</p>",
        "<p><b>Priority topics:</b> single-cell AI, scHi-C/3D genome structure, genomic foundation models, methylation/epigenomics, variant effect prediction, multimodal omics, VAE, and graph neural networks.</p>",
        "<hr>"
    ]

    for i, paper in enumerate(papers, start=1):
        title = html.escape(paper["title"])
        authors = html.escape(paper["authors"])
        summary = html.escape(make_two_sentence_summary(paper["title"], paper["abstract"]))
        source = html.escape(paper["source"])
        category = html.escape(paper.get("category", ""))
        journal = html.escape(paper.get("journal", ""))
        paper_date = html.escape(paper["date"])
        url = paper["url"]
        topics = html.escape(", ".join(paper["topics"]))
        quality_score = paper.get("quality_score", 0)

        html_parts.append(f"""
        <div style="margin-bottom: 22px; padding-bottom: 16px; border-bottom: 1px solid #ddd;">
            <p><b>{i}. <a href="{url}">{title}</a></b></p>
            <p><b>Source:</b> {source} | <b>Journal/Category:</b> {journal or category} | <b>Date:</b> {paper_date}</p>
            <p><b>Category:</b> {category}</p>
            <p><b>Authors:</b> {authors}</p>
            <p><b>Matched topics:</b> {topics}</p>
            <p><b>Quality score:</b> {quality_score}</p>
            <p><b>Two-sentence summary:</b> {summary}</p>
        </div>
        """)

    html_parts.append("""
        <p style="font-size: 12px; color: #666;">
        This digest is automatically generated from recent bioRxiv, medRxiv, arXiv, and PubMed journal searches using keyword filtering and relevance scoring.
        </p>
        </body></html>
    """)

    return "\n".join(html_parts)


def send_email(subject: str, html_body: str) -> None:
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    receiver_raw = os.getenv("EMAIL_RECEIVER")

    if not sender or not password or not receiver_raw:
        raise ValueError("Missing EMAIL_SENDER, EMAIL_PASSWORD, or EMAIL_RECEIVER in .env")

    # Allow multiple receivers separated by commas
    receivers = [email.strip() for email in receiver_raw.split(",") if email.strip()]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(receivers)

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, receivers, msg.as_string())


# =========================
# Main
# =========================

def main():
    all_papers = []

    all_papers.extend(fetch_biorxiv_like("biorxiv", DAYS_BACK))
    all_papers.extend(fetch_biorxiv_like("medrxiv", DAYS_BACK))
    all_papers.extend(fetch_arxiv(DAYS_BACK, MAX_ARXIV_RESULTS))
    all_papers.extend(fetch_pubmed_journal_articles(days_back=7, max_results=MAX_PUBMED_RESULTS))

    # Deduplicate by title and add quality score
    seen = set()
    deduped = []

    for paper in all_papers:
        doi = paper.get("doi", "").lower().strip()
        title_key = paper.get("title", "").lower().strip()

        if doi:
            key = f"doi:{doi}"
        else:
            key = f"title:{title_key}"

        if key in seen:
            continue

        seen.add(key)

        paper["quality_score"] = quality_score_paper(
            title=paper.get("title", ""),
            abstract=paper.get("abstract", ""),
            source=paper.get("source", ""),
            category=paper.get("category", ""),
            journal=paper.get("journal", "")
        )

        # Keep only papers above quality threshold
        if paper["quality_score"] >= MIN_QUALITY_SCORE:
            deduped.append(paper)

    html_body = build_email_html(deduped)
    subject = f"Daily AI + Genomics Papers — {date.today().isoformat()}"

    send_email(subject, html_body)
    print(
        f"Found {len(all_papers)} initially relevant papers. "
        f"Kept {len(deduped)} after quality filtering. "
        f"Sent top {min(len(deduped), MAX_PAPERS_PER_EMAIL)} papers."
    )


if __name__ == "__main__":
    load_dotenv()
    main()