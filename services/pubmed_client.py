"""
PubMed/NCBI E-utilities client.
Handles esearch and efetch operations for abstracts.
"""

import os
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from utils.rate_limit import RateLimiter
from utils.runtime import get_config


# Base URLs for NCBI E-utilities
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def _get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        rate = get_config("ncbi.rate_limit_rps", 6.0)
        _rate_limiter = RateLimiter(rate=float(rate))
    return _rate_limiter


def esearch(query: str, retmax: int = 100) -> List[str]:
    """
    Search PubMed and return list of PMIDs.
    
    Args:
        query: Search query string
        retmax: Maximum number of results to return
        
    Returns:
        List of PubMed IDs (as strings)
    """
    _get_rate_limiter().wait_if_needed()
    
    # Get credentials from config or environment
    email = get_config("ncbi.email") or os.getenv("NCBI_EMAIL", "")
    api_key = get_config("ncbi.api_key") or os.getenv("NCBI_API_KEY", "")
    
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
        "tool": "demoday",
        "email": email
    }
    
    if api_key:
        params["api_key"] = api_key
    
    try:
        response = requests.get(ESEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Extract PMIDs from response
        pmids = data.get("esearchresult", {}).get("idlist", [])
        return [str(pid) for pid in pmids]
    
    except Exception as e:
        # Handle errors gracefully
        return []


def efetch_abstracts(pmids: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch abstracts for given PubMed IDs.
    
    Args:
        pmids: List of PubMed IDs
        
    Returns:
        List of dictionaries with 'pmid', 'title', 'abstract' keys
    """
    if not pmids:
        return []
    
    _get_rate_limiter().wait_if_needed()
    
    # Get credentials from config or environment
    email = get_config("ncbi.email") or os.getenv("NCBI_EMAIL", "")
    api_key = get_config("ncbi.api_key") or os.getenv("NCBI_API_KEY", "")
    
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
        "tool": "demoday",
        "email": email
    }
    
    if api_key:
        params["api_key"] = api_key
    
    try:
        response = requests.get(EFETCH_URL, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.text)
        
        # Handle namespaces
        ns = {'': 'https://www.ncbi.nlm.nih.gov/soap/eutils/efetch_pubmed'}
        
        results = []
        for article in root.findall('.//PubmedArticle'):
            # Extract PMID
            pmid_elem = article.find('.//PMID')
            pmid = pmid_elem.text if pmid_elem is not None else ""
            
            # Extract title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else ""
            
            # Extract abstract
            abstract_elems = article.findall('.//AbstractText')
            abstract_parts = []
            for elem in abstract_elems:
                if elem.text:
                    abstract_parts.append(elem.text)
            abstract = " ".join(abstract_parts)
            
            if pmid:
                results.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract
                })
        
        return results
    
    except Exception as e:
        # Handle errors gracefully
        return []

