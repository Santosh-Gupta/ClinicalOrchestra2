"""PMC search, full-text fetch, and JATS XML parsing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import xml.etree.ElementTree as ET

from .ncbi import NcbiClient


@dataclass(frozen=True)
class PmcSection:
    title: str | None
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PmcArticle:
    pmcid: str
    title: str | None
    abstract: str | None
    journal: str | None
    publication_year: str | None
    doi: str | None
    pmid: str | None
    license_type: str | None
    url: str
    sections: tuple[PmcSection, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["sections"] = [section.to_dict() for section in self.sections]
        return value


def search_pmcids(
    client: NcbiClient,
    query: str,
    *,
    limit: int = 20,
    sort: str = "relevance",
) -> tuple[list[str], int, str | None]:
    """Search PMC and return PMCIDs, total count, and translated query."""

    response = client.get_json(
        "esearch.fcgi",
        {
            "db": "pmc",
            "retmode": "json",
            "retmax": limit,
            "sort": sort,
            "term": query,
        },
    )
    result = response.get("esearchresult", {})
    pmcids = [normalize_pmcid(str(item)) for item in result.get("idlist", [])]
    count = int(result.get("count", "0"))
    translation = result.get("querytranslation")
    return pmcids, count, translation


def fetch_pmc_articles(client: NcbiClient, pmcids: list[str]) -> list[PmcArticle]:
    """Fetch PMC full-text article XML via EFetch."""

    if not pmcids:
        return []
    xml_text = client.get_text(
        "efetch.fcgi",
        {
            "db": "pmc",
            "retmode": "xml",
            "id": ",".join(_eutils_pmc_id(pmcid) for pmcid in pmcids),
        },
    )
    return parse_pmc_xml(xml_text)


def pmc_search(
    client: NcbiClient,
    query: str,
    *,
    limit: int = 20,
    sort: str = "relevance",
) -> dict[str, Any]:
    pmcids, count, translation = search_pmcids(client, query, limit=limit, sort=sort)
    articles = fetch_pmc_articles(client, pmcids)
    return {
        "query": query,
        "query_translation": translation,
        "count": count,
        "pmcids": pmcids,
        "articles": [article.to_dict() for article in articles],
    }


def parse_pmc_xml(xml_text: str) -> list[PmcArticle]:
    root = ET.fromstring(xml_text)
    articles: list[PmcArticle] = []
    for article in _article_elements(root):
        pmcid = _normalize_optional_pmcid(
            _first_nonempty(
                _article_id(article, "pmc"),
                _article_id(article, "pmcid"),
                _article_id(article, "pmcaid"),
            )
        )
        if not pmcid:
            continue
        articles.append(
            PmcArticle(
                pmcid=pmcid,
                title=_clean(_article_title(article)),
                abstract=_clean(_abstract(article)),
                journal=_clean(_find_text(article, "./front/journal-meta/journal-title-group/journal-title")),
                publication_year=_publication_year(article),
                doi=_clean(_article_id(article, "doi")),
                pmid=_clean(_article_id(article, "pmid")),
                license_type=_license_type(article),
                url=f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/",
                sections=tuple(_sections(article)),
            )
        )
    return articles


def normalize_pmcid(value: str) -> str:
    cleaned = _clean(value)
    if not cleaned:
        raise ValueError("PMCID must be non-empty")
    if cleaned.upper().startswith("PMC"):
        return "PMC" + cleaned[3:]
    return f"PMC{cleaned}"


def _eutils_pmc_id(value: str) -> str:
    pmcid = normalize_pmcid(value)
    return pmcid[3:]


def _normalize_optional_pmcid(value: str | None) -> str | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    return normalize_pmcid(cleaned)


def _article_elements(root: ET.Element) -> list[ET.Element]:
    if _strip_namespace(root.tag) == "article":
        return [root]
    return [element for element in root.iter() if _strip_namespace(element.tag) == "article"]


def _find_text(element: ET.Element, path: str) -> str | None:
    found = element.find(path)
    if found is None:
        found = _find_by_local_path(element, path)
    if found is None:
        return None
    return "".join(found.itertext())


def _find_by_local_path(element: ET.Element, path: str) -> ET.Element | None:
    parts = [part for part in path.strip("./").split("/") if part]
    current = element
    for part in parts:
        match = None
        for child in list(current):
            if _strip_namespace(child.tag) == part:
                match = child
                break
        if match is None:
            return None
        current = match
    return current


def _article_id(article: ET.Element, id_type: str) -> str | None:
    for article_id in article.iter():
        if _strip_namespace(article_id.tag) == "article-id" and article_id.attrib.get("pub-id-type") == id_type:
            return "".join(article_id.itertext())
    return None


def _article_title(article: ET.Element) -> str | None:
    return _find_text(article, "./front/article-meta/title-group/article-title")


def _abstract(article: ET.Element) -> str | None:
    abstract = _find_by_local_path(article, "./front/article-meta/abstract")
    if abstract is None:
        return None
    return _section_text_without_title(abstract)


def _publication_year(article: ET.Element) -> str | None:
    for pub_date in article.iter():
        if _strip_namespace(pub_date.tag) != "pub-date":
            continue
        for child in list(pub_date):
            if _strip_namespace(child.tag) == "year":
                year = _clean("".join(child.itertext()))
                if year:
                    return year
    return None


def _license_type(article: ET.Element) -> str | None:
    for license_element in article.iter():
        if _strip_namespace(license_element.tag) != "license":
            continue
        for key in ("license-type", "{http://www.w3.org/1999/xlink}href", "href"):
            value = license_element.attrib.get(key)
            if value:
                return _clean(value)
    return None


def _sections(article: ET.Element) -> list[PmcSection]:
    body = _find_by_local_path(article, "./body")
    if body is None:
        return []
    sections: list[PmcSection] = []
    for section in _direct_children_by_local_name(body, "sec"):
        title = _clean(_direct_child_text(section, "title"))
        text = _clean(_section_text_without_title(section))
        if text:
            sections.append(PmcSection(title=title, text=text))
    if not sections:
        text = _clean(_section_text_without_title(body))
        if text:
            sections.append(PmcSection(title=None, text=text))
    return sections


def _section_text_without_title(element: ET.Element) -> str:
    parts: list[str] = []
    for child in list(element):
        if _strip_namespace(child.tag) == "title":
            continue
        text = _clean("".join(child.itertext()))
        if text:
            parts.append(text)
    if not parts:
        text = _clean("".join(element.itertext()))
        return text or ""
    return "\n".join(parts)


def _direct_child_text(element: ET.Element, local_name: str) -> str | None:
    for child in list(element):
        if _strip_namespace(child.tag) == local_name:
            return "".join(child.itertext())
    return None


def _direct_children_by_local_name(element: ET.Element, local_name: str) -> list[ET.Element]:
    return [child for child in list(element) if _strip_namespace(child.tag) == local_name]


def _strip_namespace(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _first_nonempty(*values: str | None) -> str | None:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            return cleaned
    return None
