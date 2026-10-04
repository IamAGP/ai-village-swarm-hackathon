"""Adapt the union catalog once; report IDs and source categories are not agent IDs."""
import csv
import io
import zipfile

from .common import Adapter, run, timestamp


class TransluceAdapter(Adapter):
    dataset = 'transluce'
    fields = {'report_id', 'report_url', 'report_date_utc', 'timestamp_precision',
              'disposition', 'confidence', 'broad_class', 'why_included', 'caveat'}
    notes = [
        'all-reports.csv is the deduplicated union; component CSVs must not be concatenated again.',
        'No actor field, submitted payloads, target URL inventory or response bodies are supplied.',
        'did is a recorded URLQuery scan observation, not confirmed agent execution or successful access.',
        'Report timestamps have second precision; their offset from the underlying agent act is unknown.',
        'Report URL is an evidence reference, not a shared target or an observed agent exposure.',
        'Confidence labels concern agent-like activity, not calibrated probabilities or verified identities.',
        'Source/method/confidence categories are metadata, never actor IDs or shared-artifact tokens.',
        'All dispositions retained; included/background/review_required remain in the quality sidecar.',
    ]

    def rows(self, path):
        if path.suffix == '.zip':
            with zipfile.ZipFile(path) as archive:
                names = [n for n in archive.namelist() if n.endswith('/all-reports.csv') or n == 'all-reports.csv']
                if len(names) != 1:
                    raise ValueError('ZIP must contain exactly one all-reports.csv')
                with archive.open(names[0]) as source:
                    yield from csv.DictReader(io.TextIOWrapper(source, encoding='utf-8-sig'))
        else:
            with path.open(encoding='utf-8-sig', newline='') as source:
                yield from csv.DictReader(source)

    def adapt(self, row):
        if not self.fields <= row.keys():
            raise ValueError('Unexpected Transluce catalog schema')
        t = timestamp(row['report_date_utc'])
        if row['timestamp_precision'] == 'second':
            quality = 'scan_timestamp_second_precision_agent_act_offset_unknown'
        else:
            quality = 'scan_timestamp_' + row['timestamp_precision'] + '_agent_act_offset_unknown'
        text = row['why_included'] + '\n' + row['caveat']
        return self.observation(row['report_id'], text, t, 'urlquery_scan_metadata', 'did',
                                [row['report_url']], [], source_kind='scan_catalog', time_quality=quality,
                                disposition=row['disposition'], confidence=row['confidence'],
                                broad_class=row['broad_class'], artifact_basis='report_reference_only')


if __name__ == '__main__':
    run(TransluceAdapter())
