"""PubMed client using NCBI E-utilities API."""

import os
import time
import requests
from typing import List, Dict, Optional
from pathlib import Path
import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent


def get_config() -> dict:
    """Load config from configs/config.yaml."""
    config_path = ROOT / "configs" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def search_pubmed(keywords: str, max_results: int = 5) -> List[str]:
    """
    Search PubMed using NCBI E-utilities esearch.
    
    Args:
        keywords: Search query string
        max_results: Maximum number of PMIDs to return
        
    Returns:
        List of PMIDs (as strings)
    """
    config = get_config()
    email = config.get("ncbi", {}).get("email", "")
    api_key = os.getenv("NCBI_API_KEY") or config.get("ncbi", {}).get("api_key", "")
    rate_limit = config.get("ncbi", {}).get("rate_limit_rps", 3)
    
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    
    params = {
        "db": "pubmed",
        "term": keywords,
        "retmax": min(max_results, 10),  # Cap at 10 per v3.2
        "retmode": "json",
        "email": email,
        "tool": "MCQGenerator"
    }
    
    if api_key:
        params["api_key"] = api_key
    
    # Rate limiting
    time.sleep(1.0 / rate_limit)
    
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        pmids = data.get("esearchresult", {}).get("idlist", [])
        return [str(pmid) for pmid in pmids]
    except Exception as e:
        print(f"[ERROR] PubMed search failed: {e}")
        return []


def fetch_abstracts(pmids: List[str]) -> List[Dict]:
    """
    Fetch abstracts for given PMIDs using NCBI E-utilities efetch.
    
    Args:
        pmids: List of PMIDs (as strings)
        
    Returns:
        List of dicts with keys: pmid, title, abstract, authors, doi
    """
    if not pmids:
        return []
    
    config = get_config()
    email = config.get("ncbi", {}).get("email", "")
    api_key = os.getenv("NCBI_API_KEY") or config.get("ncbi", {}).get("api_key", "")
    rate_limit = config.get("ncbi", {}).get("rate_limit_rps", 3)
    
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
        "email": email,
        "tool": "MCQGenerator"
    }
    
    if api_key:
        params["api_key"] = api_key
    
    # Rate limiting
    time.sleep(1.0 / rate_limit)
    
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse XML using standard library
        import xml.etree.ElementTree as ET
        
        # Remove namespace prefixes for easier parsing
        xml_content = response.content
        # Replace namespace declarations
        xml_content = xml_content.replace(b'xmlns="http://www.ncbi.nlm.nih.gov"', b'')
        xml_content = xml_content.replace(b'xmlns:pubmed="http://www.ncbi.nlm.nih.gov"', b'')
        
        root = ET.fromstring(xml_content)
        
        articles = []
        # Find all PubmedArticle elements (without namespace)
        for article in root.findall('.//PubmedArticle'):
            # Extract PMID
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else None
            
            # Extract title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else ""
            
            # Extract abstract
            abstract_elems = article.findall('.//AbstractText')
            abstract_parts = []
            for elem in abstract_elems:
                text = elem.text if elem.text else ""
                # Handle structured abstracts (Label attribute)
                label = elem.get('Label', '')
                if label:
                    text = f"{label}: {text}"
                abstract_parts.append(text)
            abstract = " ".join(abstract_parts)
            
            # Extract authors
            author_list = article.findall('.//Author')
            authors = []
            for author in author_list[:3]:  # Max 3 for display
                last_name_elem = author.find('LastName')
                first_name_elem = author.find('ForeName')
                if last_name_elem is not None and first_name_elem is not None:
                    last_name = last_name_elem.text or ""
                    first_name = first_name_elem.text or ""
                    if last_name and first_name:
                        authors.append(f"{last_name}, {first_name[0]}.")
            
            author_str = ""
            if len(authors) == 1:
                author_str = authors[0]
            elif len(authors) == 2:
                author_str = f"{authors[0]} and {authors[1]}"
            elif len(authors) > 2:
                author_str = f"{authors[0]} et al."
            
            # Extract DOI
            doi = None
            for aid_elem in article.findall('.//ArticleId'):
                if aid_elem.get('IdType') == 'doi':
                    doi = aid_elem.text
            
            if pmid and abstract:
                articles.append({
                    "pmid": str(pmid),
                    "title": title,
                    "abstract": abstract,
                    "authors": author_str,
                    "doi": doi
                })
        
        
        return articles
    except Exception as e:
        print(f"[ERROR] PubMed fetch failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def search_and_fetch(keywords: str, max_results: int = 5) -> List[Dict]:
    """
    Search PubMed and fetch abstracts in one call.
    
    Args:
        keywords: Search query string
        max_results: Maximum number of results
        
    Returns:
        List of article dicts with pmid, title, abstract, authors, doi
    """
    pmids = search_pubmed(keywords, max_results)
    if not pmids:
        return []
    
    return fetch_abstracts(pmids)

