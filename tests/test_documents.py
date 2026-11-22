from rag_app.documents import _split_text

def test_split_text_nonempty_and_reasonably_sized():
    chunks = _split_text(("This is a paragraph. " * 250), chunk_size=500, overlap=50)
    assert chunks
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 600 for chunk in chunks)
