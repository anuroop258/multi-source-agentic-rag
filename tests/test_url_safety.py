import pytest
from rag_app.web_sources import validate_public_url

def test_accepts_public_ip_https_url_without_dns():
    assert validate_public_url("https://8.8.8.8/dns-query").startswith("https://")

def test_blocks_localhost():
    with pytest.raises(ValueError):
        validate_public_url("http://localhost:8501/")

def test_blocks_non_http_scheme():
    with pytest.raises(ValueError):
        validate_public_url("file:///etc/passwd")
