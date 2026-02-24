"""External API clients for paper discovery and ingestion."""

import httpx
from typing import List, Optional
from app.papers.schemas import PaperMetadata
import xml.etree.ElementTree as ET
import re

USER_AGENT = "ResearchHubAI/1.0 (mailto:research@example.com)"
TIMEOUT = 30.0


async def search_openalex(query: str, limit: int = 10) -> List[PaperMetadata]:
    """Search OpenAlex for papers."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        params = {
            "search": query,
            "per_page": limit,
            "select": "id,title,authorships,doi,publication_year,primary_location,abstract_inverted_index",
        }
        resp = await client.get(
            "https://api.openalex.org/works",
            params=params,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json()

        papers = []
        for work in data.get("results", []):
            # Reconstruct abstract from inverted index
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

            authors = [
                a.get("author", {}).get("display_name", "")
                for a in work.get("authorships", [])
            ]

            doi = work.get("doi", "")
            if doi and doi.startswith("https://doi.org/"):
                doi = doi.replace("https://doi.org/", "")

            venue = None
            primary_loc = work.get("primary_location", {})
            if primary_loc and primary_loc.get("source"):
                venue = primary_loc["source"].get("display_name")

            pdf_url = None
            if primary_loc and primary_loc.get("pdf_url"):
                pdf_url = primary_loc["pdf_url"]

            papers.append(PaperMetadata(
                title=work.get("title", "Untitled"),
                authors=authors,
                doi=doi or None,
                year=work.get("publication_year"),
                venue=venue,
                abstract=abstract,
                pdf_url=pdf_url,
                source="openalex",
            ))
        return papers


async def search_crossref(query: str, limit: int = 10) -> List[PaperMetadata]:
    """Search Crossref for papers."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        params = {"query": query, "rows": limit}
        resp = await client.get(
            "https://api.crossref.org/works",
            params=params,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json()

        papers = []
        for item in data.get("message", {}).get("items", []):
            title_list = item.get("title", [])
            title = title_list[0] if title_list else "Untitled"

            authors = []
            for a in item.get("author", []):
                name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                if name:
                    authors.append(name)

            year = None
            date_parts = item.get("published-print", {}).get("date-parts", [[]])
            if date_parts and date_parts[0]:
                year = date_parts[0][0]

            venue_list = item.get("container-title", [])
            venue = venue_list[0] if venue_list else None

            abstract = item.get("abstract", "")
            if abstract:
                abstract = re.sub(r"<[^>]+>", "", abstract).strip()

            papers.append(PaperMetadata(
                title=title,
                authors=authors,
                doi=item.get("DOI"),
                year=year,
                venue=venue,
                abstract=abstract or None,
                source="crossref",
            ))
        return papers


async def search_arxiv(query: str, limit: int = 10) -> List[PaperMetadata]:
    """Search arXiv for papers."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
        }
        resp = await client.get(
            "http://export.arxiv.org/api/query",
            params=params,
            headers={"User-Agent": USER_AGENT},
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            title_text = title.text.strip().replace("\n", " ") if title is not None else "Untitled"

            summary = entry.find("atom:summary", ns)
            abstract = summary.text.strip() if summary is not None else None

            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None:
                    authors.append(name.text)

            published = entry.find("atom:published", ns)
            year = None
            if published is not None:
                year = int(published.text[:4])

            # Get PDF link
            pdf_url = None
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href")

            # Extract arXiv ID as pseudo-DOI
            id_elem = entry.find("atom:id", ns)
            arxiv_id = None
            if id_elem is not None:
                arxiv_id = id_elem.text.split("/abs/")[-1]

            papers.append(PaperMetadata(
                title=title_text,
                authors=authors,
                doi=f"arxiv:{arxiv_id}" if arxiv_id else None,
                year=year,
                venue="arXiv",
                abstract=abstract,
                pdf_url=pdf_url,
                source="arxiv",
            ))
        return papers


async def search_pubmed(query: str, limit: int = 10) -> List[PaperMetadata]:
    """Search PubMed for papers."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Step 1: Search for IDs
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmax": limit,
            "retmode": "json",
        }
        search_resp = await client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            params=search_params,
            headers={"User-Agent": USER_AGENT},
        )
        search_resp.raise_for_status()
        id_list = search_resp.json().get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return []

        # Step 2: Fetch details
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
        }
        fetch_resp = await client.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params=fetch_params,
            headers={"User-Agent": USER_AGENT},
        )
        fetch_resp.raise_for_status()

        root = ET.fromstring(fetch_resp.text)
        papers = []

        for article in root.findall(".//PubmedArticle"):
            medline = article.find(".//MedlineCitation")
            art = medline.find(".//Article") if medline else None
            if art is None:
                continue

            title_el = art.find("ArticleTitle")
            title = title_el.text if title_el is not None else "Untitled"

            abstract_el = art.find(".//AbstractText")
            abstract = abstract_el.text if abstract_el is not None else None

            authors = []
            for author in art.findall(".//Author"):
                last = author.find("LastName")
                first = author.find("ForeName")
                if last is not None:
                    name = last.text
                    if first is not None:
                        name = f"{first.text} {name}"
                    authors.append(name)

            year = None
            pub_date = art.find(".//PubDate/Year")
            if pub_date is not None:
                year = int(pub_date.text)

            journal = art.find(".//Journal/Title")
            venue = journal.text if journal is not None else None

            doi = None
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text

            papers.append(PaperMetadata(
                title=title,
                authors=authors,
                doi=doi,
                year=year,
                venue=venue,
                abstract=abstract,
                source="pubmed",
            ))
        return papers


async def fetch_unpaywall_pdf(doi: str) -> Optional[str]:
    """Get OA PDF URL from Unpaywall if available."""
    if not doi:
        return None
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            resp = await client.get(
                f"https://api.unpaywall.org/v2/{doi}",
                params={"email": "research@researchhub.ai"},
                headers={"User-Agent": USER_AGENT},
            )
            if resp.status_code == 200:
                data = resp.json()
                best_oa = data.get("best_oa_location")
                if best_oa:
                    return best_oa.get("url_for_pdf")
        except Exception:
            pass
    return None


def _reconstruct_abstract(inverted_index: Optional[dict]) -> Optional[str]:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return None
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(word for _, word in word_positions)
