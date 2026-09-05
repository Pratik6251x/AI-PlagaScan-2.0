"""AI plagiarism detection engine.
Combines:
  - spaCy for tokenisation / sentence segmentation / lemmatisation
  - NLTK stopwords + tokenisation
  - TF-IDF vectorisation (scikit-learn)
  - Cosine similarity
  - A lightweight "sentence transformer" built from TF-IDF embeddings
    (no external model download required) used for semantic similarity
  - A heuristic AI-vs-human probability estimator

The engine compares an uploaded document against every other document
already stored in the system and returns matched paragraphs, similarity
percentages, AI/human probabilities and a confidence score.
"""
import re
from typing import List, Dict, Tuple
import numpy as np

# Lazy-loaded NLP resources (loaded once on first use)
_NLP = None
_STOPWORDS = None

def _ensure_nlp():
    global _NLP, _STOPWORDS
    if _NLP is not None:
        return
    try:
        import spacy
        try:
            _NLP = spacy.load("en_core_web_sm", disable=["ner", "parser"])
            if "sentencizer" not in _NLP.pipe_names:
                _NLP.add_pipe("sentencizer")
        except Exception:
            _NLP = spacy.blank("en")
            _NLP.add_pipe("sentencizer")
    except Exception:
        _NLP = None
    try:
        import nltk
        from nltk.corpus import stopwords
        try:
            _STOPWORDS = set(stopwords.words("english"))
        except Exception:
            nltk.download("stopwords", quiet=True)
            _STOPWORDS = set(stopwords.words("english"))
    except Exception:
        _STOPWORDS = set()

# Text preprocessing
def preprocess(text: str) -> str:
    """Lowercase, strip excess whitespace, normalise punctuation."""
    text = (text or "").lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9\s.,;:'\"-]", " ", text)
    return text.strip()

def split_sentences(text: str) -> List[str]:
    """Sentence segmentation using spaCy if available, else regex."""
    _ensure_nlp()
    text = (text or "").strip()
    if not text:
        return []
    if _NLP is not None:
        doc = _NLP(text)
        return [s.text.strip() for s in doc.sents if s.text.strip()]
    # Regex fallback
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]

def split_paragraphs(text: str) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paras:
        paras = [text]
    return paras

# TF-IDF + cosine similarity
def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if _STOPWORDS:
        tokens = [t for t in tokens if t not in _STOPWORDS and len(t) > 2]
    return tokens

def _build_tfidf_matrix(texts: List[str]) -> Tuple[np.ndarray, List[str]]:
    """Build a TF-IDF matrix manually (no sklearn dependency needed)."""
    # Vocabulary
    vocab = {}
    tokenized = []
    for t in texts:
        toks = _tokenize(t)
        tokenized.append(toks)
        for tok in toks:
            if tok not in vocab:
                vocab[tok] = len(vocab)
    n_docs = len(texts)
    n_vocab = len(vocab)
    if n_vocab == 0:
        return np.zeros((n_docs, 1)), []
    # Term frequency
    tf = np.zeros((n_docs, n_vocab))
    for i, toks in enumerate(tokenized):
        for tok in toks:
            tf[i, vocab[tok]] += 1
        if len(toks) > 0:
            tf[i] /= len(toks)
    # Document frequency
    df = np.count_nonzero(tf > 0, axis=0)
    idf = np.log((1 + n_docs) / (1 + df)) + 1
    tfidf = tf * idf
    # L2 normalise rows
    norms = np.linalg.norm(tfidf, axis=1, keepdims=True)
    norms[norms == 0] = 1
    tfidf = tfidf / norms
    return tfidf, list(vocab.keys())

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

def _sentence_transformer_embedding(text: str, vocab_index: Dict[str, int], idf_vec: np.ndarray) -> np.ndarray:
    """Lightweight sentence embedding: IDF-weighted average of one-hot token vectors."""
    toks = _tokenize(text)
    if not toks:
        return np.zeros(len(vocab_index))
    vec = np.zeros(len(vocab_index))
    for tok in toks:
        idx = vocab_index.get(tok)
        if idx is not None:
            vec[idx] += idf_vec[idx]
    vec /= len(toks)
    n = np.linalg.norm(vec)
    if n > 0:
        vec /= n
    return vec

# AI / human probability heuristic
def ai_probability_estimate(text: str) -> Tuple[float, float, float]:
    """Enhanced AI-generated vs human-written probability detection.
    
    Uses multiple sophisticated heuristics:
    - Sentence length variance and uniformity
    - Punctuation diversity
    - Contraction usage (AI avoids contractions)
    - Transition word density (AI overuses them)
    - Word diversity (AI uses fewer unique words)
    - Passive voice ratio (AI uses more passive)
    - Clichéd phrase detection
    - Filler phrase patterns
    
    Returns (ai_probability, human_probability, confidence).
    """
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return 50.0, 50.0, 30.0

    # Feature 1: Sentence length uniformity
    lengths = [len(s.split()) for s in sentences]
    mean_len = np.mean(lengths)
    std_len = np.std(lengths)
    cv = std_len / mean_len if mean_len > 0 else 0
    uniformity_score = max(0, (0.45 - cv) / 0.45)  # Higher = more uniform = more AI-like

    # Feature 2: Punctuation diversity
    punct_chars = set(re.findall(r"[.,;:!?\'\"-]", text))
    punct_diversity = min(1.0, len(punct_chars) / 8.0)
    punct_score = max(0, (1.0 - punct_diversity))  # Lower diversity = more AI-like

    # Feature 3: Sentence length extremes (humans vary more)
    extreme_ratio = sum(1 for l in lengths if l < 6 or l > 35) / len(lengths)
    extreme_score = max(0, (0.2 - extreme_ratio) / 0.2)  # Lower extremes = more AI-like

    # Feature 4: Contraction usage (AI avoids contractions: can't, won't, etc.)
    contractions = re.findall(r"\b(?:don't|can't|won't|isn't|aren't|wasn't|weren't|hasn't|haven't|hadn't|doesn't|didn't|shouldn't|wouldn't|couldn't|mightn't|mustn't|shan't|oughtn't|let's|that's|what's|who's|i'm|you're|he's|she's|it's|we're|they're|i've|you've|we've|they've|i'd|you'd|he'd|she'd|we'd|they'd|i'll|you'll|he'll|she'll|it'll|we'll|they'll)\b", text.lower(), re.IGNORECASE)
    contraction_ratio = len(contractions) / len(text.split()) if text.split() else 0
    contraction_score = max(0, (0.1 - contraction_ratio) / 0.1)  # Fewer contractions = more AI

    # Feature 5: Transition word density (AI overuses: furthermore, moreover, etc.)
    transition_words = re.findall(r"\b(furthermore|moreover|however|therefore|thus|hence|additionally|meanwhile|nevertheless|meanwhile|consequently|subsequently|accordingly|indeed|rather|specifically|particularly|similarly|likewise|alternatively|unfortunately|fortunately|surprisingly|obviously|clearly|certainly|undoubtedly|arguably|notably|interestingly|frankly|honestly)\b", text.lower(), re.IGNORECASE)
    transition_ratio = len(transition_words) / len(sentences) if sentences else 0
    transition_score = min(1.0, max(0, (transition_ratio - 0.1) / 0.5))  # More transitions = more AI

    # Feature 6: Word diversity (type-token ratio)
    words = re.findall(r"\b[a-z]+\b", text.lower())
    unique_words = len(set(words))
    total_words = len(words)
    if total_words > 0:
        word_diversity = unique_words / total_words
        diversity_score = max(0, (0.55 - word_diversity) / 0.55)  # Lower diversity = more AI
    else:
        diversity_score = 0

    # Feature 7: Passive voice detection (is/was + past participle)
    passive_patterns = re.findall(r"\b(?:is|was|are|were|be|being|been)\s+(?:[a-z]+ed|[a-z]+en)\b", text.lower(), re.IGNORECASE)
    passive_ratio = len(passive_patterns) / len(sentences) if sentences else 0
    passive_score = min(1.0, max(0, (passive_ratio - 0.1) / 0.3))  # More passive = more AI

    # Feature 8: Clichéd and filler phrases (AI loves these)
    cliche_phrases = [
        "it is important to note", "it is worth noting", "in conclusion",
        "to summarize", "in summary", "as mentioned", "as stated", "the fact that",
        "due to the fact that", "in order to", "in light of", "at the end of the day",
        "needless to say", "it goes without saying", "there is no doubt", 
        "without a doubt", "in the final analysis", "in the long run"
    ]
    cliche_count = sum(text.lower().count(p) for p in cliche_phrases)
    cliche_score = min(1.0, max(0, cliche_count / max(1, len(sentences) / 5)))  # More clichés = more AI

    # Feature 9: Perfect paragraph structure (all start similarly)
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    if len(paragraphs) >= 3:
        para_starts = [p.split()[0] if p.split() else "" for p in paragraphs]
        unique_starts = len(set(para_starts))
        structure_score = max(0, (1.0 - unique_starts / len(paragraphs)))  # Low variety = more AI
    else:
        structure_score = 0

    # Combine all features with weights
    ai_score = (
        uniformity_score * 0.15 +
        punct_score * 0.10 +
        extreme_score * 0.12 +
        contraction_score * 0.18 +  # High weight - strong AI indicator
        transition_score * 0.14 +
        diversity_score * 0.16 +
        passive_score * 0.10 +
        cliche_score * 0.12 +
        structure_score * 0.08
    )
    
    ai_score = max(0.0, min(1.0, ai_score))
    ai_prob = round(ai_score * 100, 2)
    human_prob = round(100 - ai_prob, 2)
    
    # Confidence based on number of sentences and feature consistency
    confidence = round(
        50 + min(40, len(sentences) * 1.5) + 
        min(10, abs(cv - 0.35) * 20),
        2
    )
    confidence = min(98.0, max(40.0, confidence))
    
    return ai_prob, human_prob, confidence

# Similarity category
def category_for(percent: float) -> str:
    percent = float(percent)
    if percent <= 10:
        return "Very Low"
    if percent <= 30:
        return "Low"
    if percent <= 50:
        return "Medium"
    if percent <= 75:
        return "High"
    return "Very High"

# Main analysis
def analyse(target_text: str, corpus: List[Dict]) -> Dict:
    """Analyse target_text against a corpus of stored documents.

    Each corpus item is a dict with keys: id, title, original_name, extracted_text.
    Returns the full analysis result dict.
    """
    target_text = (target_text or "").strip()
    if not target_text:
        return _empty_result()

    # Build corpus texts (target + all sources)
    corpus_texts = [item.get("extracted_text") or "" for item in corpus]
    all_texts = [target_text] + corpus_texts
    tfidf_matrix, vocab = _build_tfidf_matrix(all_texts)
    vocab_index = {w: i for i, w in enumerate(vocab)}
    # idf vector approximated from column sparsity
    n_docs = tfidf_matrix.shape[0]
    df = np.count_nonzero(tfidf_matrix > 0, axis=0)
    idf_vec = np.log((1 + n_docs) / (1 + df)) + 1

    target_vec = tfidf_matrix[0]
    target_emb = _sentence_transformer_embedding(target_text, vocab_index, idf_vec)

    # Paragraph-level matching
    target_paras = split_paragraphs(target_text)
    matched_sources = []
    overall_scores = []

    for idx, item in enumerate(corpus):
        source_text = (item.get("extracted_text") or "").strip()
        if not source_text:
            continue
        source_vec = tfidf_matrix[idx + 1]
        doc_sim = cosine_sim(target_vec, source_vec)
        overall_scores.append(doc_sim)

        # Paragraph-level comparison
        source_paras = split_paragraphs(source_text)
        para_pairs = []
        for tp in target_paras:
            tp_emb = _sentence_transformer_embedding(tp, vocab_index, idf_vec)
            best_sim = 0.0
            best_sp = ""
            for sp in source_paras:
                sp_emb = _sentence_transformer_embedding(sp, vocab_index, idf_vec)
                sim = cosine_sim(tp_emb, sp_emb)
                if sim > best_sim:
                    best_sim = sim
                    best_sp = sp
            if best_sim >= 0.25:
                para_pairs.append({
                    "matched_text": tp,
                    "source_text": best_sp,
                    "similarity_percent": round(best_sim * 100, 2),
                    "citation_suggestion": _citation(item, best_sp),
                })

        if para_pairs:
            avg_para = np.mean([p["similarity_percent"] for p in para_pairs])
            doc_match_percent = round(max(doc_sim * 100, avg_para), 2)
            if doc_match_percent >= 5:
                matched_sources.append({
                    "source_document_id": item.get("id"),
                    "source_title": item.get("title") or item.get("original_name"),
                    "source_reference": _source_reference(item),
                    "similarity_percent": doc_match_percent,
                    "matched_paragraphs": para_pairs,
                })

    # Overall similarity = max single-doc match (most plagiarised source)
    if matched_sources:
        similarity_percent = round(max(m["similarity_percent"] for m in matched_sources), 2)
    elif overall_scores:
        similarity_percent = round(max(overall_scores) * 100, 2)
    else:
        similarity_percent = 0.0
    original_percent = round(max(0.0, 100 - similarity_percent), 2)
    ai_prob, human_prob, confidence = ai_probability_estimate(target_text)

    # Matched paragraphs (for highlighting) - flatten top matches
    matched_paragraphs = []
    for m in matched_sources:
        for p in m["matched_paragraphs"][:5]:
            matched_paragraphs.append({
                "matched_text": p["matched_text"],
                "source_text": p["source_text"],
                "similarity_percent": p["similarity_percent"],
                "source_reference": m["source_reference"],
            })

    summary = _build_summary(similarity_percent, original_percent, ai_prob,
                             human_prob, confidence, len(matched_sources))

    return {
        "similarity_percent": similarity_percent,
        "original_percent": original_percent,
        "ai_probability": ai_prob,
        "human_probability": human_prob,
        "confidence_score": confidence,
        "category": category_for(similarity_percent),
        "matched_sources": matched_sources,
        "matched_paragraphs": matched_paragraphs,
        "summary": summary,
    }
def _citation(item: Dict, text: str) -> str:
    title = item.get("title") or item.get("original_name") or "Unknown source"
    # Take first 6 words of matched text as a quote
    words = text.split()
    short = words[:6]
    quote = " ".join(short) + ("..." if len(words) > 6 else "")
    return f'"{quote}" - {title}'

def _source_reference(item: Dict) -> str:
    title = item.get("title") or item.get("original_name") or "Document"
    return f"Internal repository: {title}"

def _build_summary(sim, orig, ai, human, conf, n_sources):
    cat = category_for(sim)
    return (
        f"This document shows a {cat.lower()} similarity of {sim}% "
        f"({orig}% original) against {n_sources} source(s) in the repository. "
        f"AI-generated probability is estimated at {ai}% "
        f"(human-written {human}%) with a confidence score of {conf}%. "
        f"Results are probabilistic analysis, not absolute proof of plagiarism or authorship."
    )

def _empty_result() -> Dict:
    return {
        "similarity_percent": 0.0,
        "original_percent": 100.0,
        "ai_probability": 0.0,
        "human_probability": 0.0,
        "confidence_score": 0.0,
        "category": "Very Low",
        "matched_sources": [],
        "matched_paragraphs": [],
        "summary": "No text could be extracted from this document.",
    }