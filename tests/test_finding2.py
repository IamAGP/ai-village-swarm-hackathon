"""Synthetic checks for separating actual tool output from agent narration."""
import importlib.util
import json
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('finding2', Path(__file__).parents[1] / 'explorer/finding2.py')
finding2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finding2)


def test_tap_summaries_preserve_failure_and_non_tap_uncertainty():
    output = json.dumps('Running 3 test files...\n# tests 8\n# pass 7\n# fail 1\n# tests 2\n# pass 2\n# fail 0\n')
    result = finding2.output_summary(output)
    assert result['test_files'] == 3
    assert result['tap'] == {'tests': [8, 2], 'pass': [7, 2], 'fail': [1, 0]}
    assert not result['runner_all_passed']


def test_narrated_results_do_not_count_as_tap():
    result = finding2.output_summary(json.dumps('I claim # tests 8 and # fail 0.'))
    assert result['tap']['tests'] == []
    assert result['test_files'] is None


def test_json_null_and_unexpected_output_shape():
    assert finding2.json_text(None) == finding2.json_text('null') == ''
    with pytest.raises(ValueError):
        finding2.json_text('{"narration": "passed"}')


def test_bounded_accusation_query():
    c = finding2.duckdb.connect()
    c.execute('CREATE TABLE agents(id VARCHAR, name VARCHAR)')
    c.execute("INSERT INTO agents VALUES ('a','peer')")
    c.execute('CREATE TABLE chat_messages(id VARCHAR, created_at INTEGER, agent_speaker_id VARCHAR, content VARCHAR)')
    c.executemany('INSERT INTO chat_messages VALUES (?, ?, ?, ?)', [
        ('before', 0, 'a', 'GPT-5.1 false'), ('start', 1, 'a', 'GPT-5.1 FALSE'),
        ('other', 2, 'a', 'someone fabricated'), ('neutral', 2, 'a', 'GPT-5.1 tested'),
        ('end', 3, 'a', 'GPT-5.1 deceptive')])
    assert [r[0] for r in c.execute(finding2.ACCUSATIONS_SQL, [1, 3]).fetchall()] == ['start']
