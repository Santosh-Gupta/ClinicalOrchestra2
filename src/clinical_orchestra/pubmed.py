"""PubMed search and abstract retrieval."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import xml.etree.ElementTree as ET

from .ncbi import NcbiClient


@dataclass(frozen=True)
class PubMedArticle:
    pmid: str
    title: str | None
    abstract: str | None
    journal: str | None
    publication_year: str | None
    publication_types: tuple[str, ...]
    doi: str | None
    pmcid: str | None
    url: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["publication_types"] = list(self.publication_types)
        return value


def search_pmids(
    client: NcbiClient,
    query: str,
    *,
    limit: int = 20,
    sort: str = "relevance",
) -> tuple[list[str], int, str | None]:
    """Search PubMed and return PMIDs, total count, and translated query."""

    response = client.get_json(
        "esearch.fcgi",
        {
            "db": "pubmed",
            "retmode": "json",
            "retmax": limit,
            "sort": sort,
            "term": query,
        },
    )
    result = response.get("esearchresult", {})
    pmids = [str(item) for item in result.get("idlist", [])]
    count = int(result.get("count", "0"))
    translation = result.get("querytranslation")
    return pmids, count, translation


def fetch_pubmed_articles(client: NcbiClient, pmids: list[str]) -> list[PubMedArticle]:
    """Fetch PubMed article metadata and abstracts via EFetch XML."""

    if not pmids:
        return []
    xml_text = client.get_text(
        "efetch.fcgi",
        {
            "db": "pubmed",
            "retmode": "xml",
            "id": ",".join(pmids),
        },
    )
    return parse_pubmed_xml(xml_text)


def parse_pubmed_xml(xml_text: str) -> list[PubMedArticle]:
    root = ET.fromstring(xml_text)
    articles: list[PubMedArticle] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = _find_text(article, ".//MedlineCitation/PMID")
        if not pmid:
            continue
        articles.append(
            PubMedArticle(
                pmid=pmid,
                title=_clean(_article_title(article)),
                abstract=_clean(_abstract(article)),
                journal=_clean(_find_text(article, ".//Journal/Title")),
                publication_year=_publication_year(article),
                publication_types=tuple(_publication_types(article)),
                doi=_article_id(article, "doi"),
                pmcid=_normalize_pmcid(_article_id(article, "pmc")),
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            )
        )
    return articles


def pubmed_search(
    client: NcbiClient,
    query: str,
    *,
    limit: int = 20,
    sort: str = "relevance",
) -> dict[str, Any]:
    pmids, count, translation = search_pmids(client, query, limit=limit, sort=sort)
    articles = fetch_pubmed_articles(client, pmids)
    return {
        "query": query,
        "query_translation": translation,
        "count": count,
        "pmids": pmids,
        "articles": [article.to_dict() for article in articles],
    }


def _find_text(element: ET.Element, path: str) -> str | None:
    found = element.find(path)
    if found is None:
        return None
    return "".join(found.itertext())


def _article_title(article: ET.Element) -> str | None:
    title = article.find(".//ArticleTitle")
    if title is None:
        return None
    return "".join(title.itertext())


def _abstract(article: ET.Element) -> str | None:
    parts: list[str] = []
    for abstract_text in article.findall(".//Abstract/AbstractText"):
        label = abstract_text.attrib.get("Label")
        text = _clean("".join(abstract_text.itertext()))
        if not text:
            continue
        if label:
            parts.append(f"{label}: {text}")
        else:
            parts.append(text)
    return "\n".join(parts) if parts else None


def _publication_year(article: ET.Element) -> str | None:
    for path in (
        ".//Article/Journal/JournalIssue/PubDate/Year",
        ".//ArticleDate/Year",
        ".//PubMedPubDate[@PubStatus='pubmed']/Year",
    ):
        year = _find_text(article, path)
        if year:
            return year
    medline_date = _find_text(article, ".//Article/Journal/JournalIssue/PubDate/MedlineDate")
    if medline_date:
        return medline_date[:4]
    return None


def _publication_types(article: ET.Element) -> list[str]:
    values: list[str] = []
    for publication_type in article.findall(".//PublicationTypeList/PublicationType"):
        text = _clean("".join(publication_type.itertext()))
        if text:
            values.append(text)
    return values


def _article_id(article: ET.Element, id_type: str) -> str | None:
    for article_id in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
        if article_id.attrib.get("IdType") == id_type:
            return _clean("".join(article_id.itertext()))
    return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _normalize_pmcid(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    if cleaned.upper().startswith("PMC"):
        return "PMC" + cleaned[3:]
    return f"PMC{cleaned}"
