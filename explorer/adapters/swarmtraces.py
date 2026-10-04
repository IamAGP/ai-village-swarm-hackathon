"""Preserve redacted recovered texts; null-time records never become strict dated events."""
import gzip
import hashlib
import json

from .common import Adapter, CVE_RE, run, timestamp, urls_in_text


class SwarmTracesAdapter(Adapter):
    dataset = 'swarmtraces'
    fields = {'id', 'cite', 'kind', 'parent_id', 'time_utc', 'tags', 'text'}
    notes = [
        'No actor field; embedded names/agent_id literals are not authenticated authors.',
        'parent_id is a recovery relationship, not an exposure or communication edge.',
        'said means preserved textual evidence, not an observed agent utterance.',
        'Payload or response text does not establish execution, access or success.',
        'Exact hashes describe released redacted text; redaction and templates can cause recurrence.',
        'Undated observations use t=null in a separate file; strict events require ISO8601Z.',
        'URLs are extracted offline from full text before clipping; no payload is executed or fetched.',
    ]

    def rows(self, path):
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as source:
            for line in source:
                if line.strip():
                    yield json.loads(line)

    def adapt(self, row):
        if not self.fields <= row.keys() or row['kind'] not in ('payload', 'recovered_text', 'response'):
            raise ValueError('Unexpected SwarmTraces schema or record kind')
        text = row['text']
        if not isinstance(text, str):
            raise ValueError('SwarmTraces text must be a string')
        t = timestamp(row['time_utc'])
        tokens = ['redacted-sha256:' + hashlib.sha256(text.encode()).hexdigest()]
        tokens += ['cve:' + value.upper() for value in sorted(set(CVE_RE.findall(text)))]
        return self.observation(row['id'], text, t, 'recovered_' + row['kind'], 'said',
                                urls_in_text(text), tokens, source_kind=row['kind'],
                                time_quality='missing' if t is None else 'source_timestamp_precision_unspecified',
                                parent_id=row['parent_id'], citation=row['cite'], tags=row['tags'],
                                artifact_basis='released_redacted_text')


if __name__ == '__main__':
    run(SwarmTracesAdapter())
