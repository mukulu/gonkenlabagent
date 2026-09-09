"""Safe Markdown/text ingestion, reproducible BM25, calibrated support, atomic index.

Only explicit maintenance builds write the index. Runtime rejects stale/corrupt
indexes rather than silently changing the accepted corpus or support threshold.
"""
import hashlib
import json
import math
import os
import re
import stat
import tempfile
from collections import Counter
from pathlib import Path

MAX_FILES = 256
MAX_FILE_BYTES = 256 * 1024
MAX_CORPUS_BYTES = 8 * 1024 * 1024
MAX_INDEX_BYTES = 32 * 1024 * 1024
CHUNK_WORDS = 160
OVERLAP_WORDS = 24
STOPWORDS = frozenset('a an and are as at be by can do does for from how i in is it of on or the to what when where which who why with'.split())
SETTINGS = {'schema': 1, 'chunk_words': CHUNK_WORDS, 'overlap_words': OVERLAP_WORDS,
            'tokenizer': 'unicode-casefold-v1', 'bm25_k1': 1.5, 'bm25_b': .75}


class IndexError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def tokens(text):
    return [t for t in re.findall(r'\w+', text.casefold()) if t not in STOPWORDS]


def sources(root):
    root = Path(root).absolute()
    if root.resolve() != root or not root.is_dir():
        raise IndexError('CORPUS_ROOT_UNSAFE_OR_MISSING')
    records = []
    total = 0
    def visit(fd, prefix='', depth=0):
        nonlocal total
        if depth > 12:
            raise IndexError('CORPUS_DEPTH_LIMIT')
        for name in sorted(os.listdir(fd)):
            if not name or any(ord(c) < 32 for c in name) or any(c in name for c in '\\#@'):
                raise IndexError('CORPUS_UNSAFE_NAME')
            metadata = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode):
                raise IndexError('CORPUS_SYMLINK')
            relative = prefix + name
            if stat.S_ISDIR(metadata.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try: visit(child, relative + '/', depth + 1)
                finally: os.close(child)
            elif Path(name).suffix.lower() in {'.md', '.txt'}:
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_FILE_BYTES:
                    raise IndexError('CORPUS_FILE_LIMIT_OR_TYPE')
                handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    if not stat.S_ISREG(os.fstat(handle).st_mode):
                        raise IndexError('CORPUS_FILE_TYPE_CHANGED')
                    with os.fdopen(handle, 'rb', closefd=False) as stream:
                        raw = stream.read(MAX_FILE_BYTES + 1)
                finally: os.close(handle)
                total += len(raw)
                if len(raw) > MAX_FILE_BYTES or total > MAX_CORPUS_BYTES or len(records) >= MAX_FILES:
                    raise IndexError('CORPUS_SIZE_LIMIT')
                try: content = raw.decode('utf-8')
                except UnicodeDecodeError as exc: raise IndexError('CORPUS_NOT_UTF8') from exc
                records.append({'path': relative, 'sha256': hashlib.sha256(raw).hexdigest(), 'text': content})
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: visit(fd)
    finally: os.close(fd)
    return records


def chunks(records):
    result = []
    for source in records:
        heading = 'document'
        number = 0
        # Paragraph boundaries are preserved; long paragraphs split with overlap.
        for paragraph in re.split(r'\n\s*\n', source['text']):
            lines = paragraph.strip().splitlines()
            if not lines: continue
            if lines[0].startswith('#'):
                heading = re.sub(r'[^a-z0-9]+', '-', lines[0].lstrip('# ').casefold()).strip('-')[:64] or 'section'
            words = paragraph.split()
            for start in range(0, len(words), CHUNK_WORDS - OVERLAP_WORDS):
                excerpt = ' '.join(words[start:start + CHUNK_WORDS])
                if not excerpt: continue
                number += 1
                sha = hashlib.sha256(excerpt.encode()).hexdigest()
                source_id = f"{source['path']}#{heading}:{number}@{sha[:16]}"
                result.append({'id': source_id, 'path': source['path'], 'text': excerpt})
                if start + CHUNK_WORDS >= len(words): break
    return result


def ranked(index, query, top_k=3):
    if not isinstance(query, str) or not query.strip() or len(query) > 4096 or not 1 <= top_k <= 10:
        raise IndexError('INVALID_RETRIEVAL_REQUEST')
    terms = set(tokens(query))
    docs = index['chunks']
    all_terms = [Counter(tokens(d['text'])) for d in docs]
    lengths = [sum(t.values()) for t in all_terms]
    average = sum(lengths) / len(lengths) if lengths else 1
    df = {t: sum(t in counter for counter in all_terms) for t in terms}
    scored = []
    for doc, freq, length in zip(docs, all_terms, lengths):
        score = 0.0
        for term in sorted(terms):
            count = freq[term]
            if count:
                idf = math.log(1 + (len(docs) - df[term] + .5) / (df[term] + .5))
                score += idf * count * 2.5 / (count + 1.5 * (.25 + .75 * length / (average or 1)))
        if score > 0:
            scored.append({**doc, 'score': round(score, 10)})
    return sorted(scored, key=lambda d: (-d['score'], d['id']))[:top_k]


def calibrate(index, cases):
    if not isinstance(cases, list) or not cases or len(cases) > 1000:
        raise IndexError('CALIBRATION_CASES_REQUIRED')
    paths={source['path'] for source in index['sources']}
    seen=set()
    for case in cases:
        if not isinstance(case,dict) or not {'query','expected_paths'} <= set(case):
            raise IndexError('CALIBRATION_CASE_INVALID')
        if not isinstance(case['query'],str) or not case['query'].strip() or len(case['query'])>4096:
            raise IndexError('CALIBRATION_QUERY_INVALID')
        expected=case['expected_paths']
        if not isinstance(expected,list) or any(type(path) is not str or path not in paths for path in expected):
            raise IndexError('CALIBRATION_SOURCE_INVALID')
        if case['query'] in seen:
            raise IndexError('CALIBRATION_DUPLICATE_QUERY')
        seen.add(case['query'])
    if not any(c['expected_paths'] for c in cases) or not any(not c['expected_paths'] for c in cases):
        raise IndexError('CALIBRATION_REQUIRES_ANSWERABLE_AND_UNANSWERABLE')
    scores = []
    for case in cases:
        hits = ranked(index, case['query'])
        positive = bool(case['expected_paths'])
        hit = any(h['path'] in case['expected_paths'] for h in hits)
        scores.append((hits[0]['score'] if hits else 0, positive, hit))
    candidates = sorted({1e-8} | {s + 1e-8 for s, _, _ in scores} | {s for s, _, _ in scores if s > 0})
    def accuracy(threshold):
        known = [s >= threshold and hit for s, pos, hit in scores if pos]
        unknown = [s < threshold for s, pos, hit in scores if not pos]
        return (sum(known)/len(known) + sum(unknown)/len(unknown))/2
    threshold = max(candidates, key=lambda t: (accuracy(t), t))
    return {'threshold': threshold, 'cases_sha256': digest(cases), 'case_count': len(cases),
            'method': 'balanced-calibration-accuracy-v1', 'balanced_accuracy': accuracy(threshold)}


def build(root, calibration_cases):
    records = sources(root)
    index = {'schema': 1, 'settings': SETTINGS,
             'sources': [{'path': r['path'], 'sha256': r['sha256']} for r in records],
             'chunks': chunks(records)}
    if not index['chunks']:
        raise IndexError('CORPUS_EMPTY')
    index['calibration'] = calibrate(index, calibration_cases)
    index['checksum'] = digest(index)
    return index


def save(index, output):
    output = Path(output).absolute()
    if output.is_symlink() or output.parent.resolve() != output.parent:
        raise IndexError('INDEX_PATH_UNSAFE')
    payload = canonical(index) + b'\n'
    if len(payload) > MAX_INDEX_BYTES:
        raise IndexError('INDEX_SIZE_LIMIT')
    fd, temporary = tempfile.mkstemp(prefix='.index-', dir=output.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, output)
        fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load(path, root):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > MAX_INDEX_BYTES:
        raise IndexError('INDEX_PATH_OR_SIZE_INVALID')
    try:
        value = json.loads(path.read_bytes())
        if not isinstance(value, dict): raise IndexError('INDEX_CORRUPT')
        checksum = value.pop('checksum')
        if digest(value) != checksum or value['schema'] != 1 or value['settings'] != SETTINGS:
            raise IndexError('INDEX_CORRUPT_OR_UNSUPPORTED')
        value['checksum'] = checksum
        records = sources(root)
        if value['sources'] != [{'path': r['path'], 'sha256': r['sha256']} for r in records] or value['chunks'] != chunks(records):
            raise IndexError('INDEX_STALE_OR_CORRUPT_REBUILD_REQUIRED')
        threshold = value['calibration']['threshold']
        if type(threshold) not in (float, int) or not math.isfinite(threshold) or threshold <= 0:
            raise IndexError('INDEX_THRESHOLD_INVALID')
        return value
    except (KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise IndexError('INDEX_CORRUPT') from exc


def retrieve(index, query, top_k=3):
    hits = ranked(index, query, top_k)
    threshold = index['calibration']['threshold']
    return [h for h in hits if h['score'] >= threshold]
