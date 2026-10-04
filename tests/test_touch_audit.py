"""Synthetic counterexamples to link mention and same-command execution attribution."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'explorer'))
from trace_exec import runs_repo
from trace_shell_audit import shell_evidence, strict_touch, without_payloads
from trace_touch_sensitivity import root_candidate


NAME = 'example-repo'
URL = 'https://github.com/team/example-repo'


def test_unrelated_run_does_not_execute_remote_repo():
    cmd = f'curl {URL}/README.md; python3 other.py'
    assert runs_repo(cmd, NAME)  # confirmed legacy false positive
    assert not shell_evidence(cmd, NAME).run


def test_latest_cd_and_quoted_paths_change_attribution():
    assert runs_repo('cd example-repo; cd /tmp; pytest', NAME)
    assert not shell_evidence('cd example-repo; cd /tmp; pytest', NAME).run
    assert shell_evidence('cd "example-repo" && python3 "verify.py"', NAME).run
    assert not runs_repo('cd "example-repo" && python3 "verify.py"', NAME)


def test_payload_is_not_executed_but_following_command_is():
    cmd = "cat > article.md <<'EOF'\ncd example-repo; pytest\nEOF\ncd /tmp; python3 other.py"
    assert not shell_evidence(cmd, NAME).run
    assert shell_evidence(cmd + '\ncd example-repo; pytest', NAME).run
    assert 'pytest' not in without_payloads(cmd)


def test_dependency_install_and_echo_do_not_run_repo():
    assert not shell_evidence('cd example-repo; python3 -m pip install -r requirements.txt', NAME).run
    assert not shell_evidence("echo 'cd example-repo; python3 check.py'", NAME).run
    assert shell_evidence('python3 ~/example-repo/check.py', NAME).run


def test_retrieval_request_is_not_url_in_text_or_post_data():
    assert strict_touch({'command': f'git clone {URL}.git'}, URL) == 'clone_request'
    assert strict_touch({'command': f'curl -L {URL}'}, URL) == 'retrieval_request'
    assert strict_touch({'text': URL}, URL) is None
    assert strict_touch({'command': f'echo "{URL}"'}, URL) is None
    assert strict_touch({'command': f'curl -d "{URL}" https://api.example.com/post'}, URL) is None


def test_contribution_intent_requires_explicit_repo_context():
    assert shell_evidence('git -C ~/example-repo commit -m fix', NAME).contribution
    assert not shell_evidence(f'echo {URL}; git push', NAME).contribution
    assert shell_evidence('cd example-repo; pytest; git push', NAME).run
    assert shell_evidence('cd example-repo; pytest; git push', NAME).contribution


def test_external_scanner_and_wrapped_repo_script_have_different_provenance():
    assert not shell_evidence('cd example-repo; python3 ~/other-repo/check.py .', NAME).run
    assert shell_evidence('cd example-repo; timeout 5 node check.js', NAME).run
    assert shell_evidence('find . -name "*.md" | xargs python3 example-repo/check.py', NAME).run


def test_build_tool_word_in_comment_is_not_invocation():
    cmd = '# Inspect the file to make sure it is valid\nhead -50 /tmp/example-repo/index.html'
    assert runs_repo(cmd, NAME)
    assert not shell_evidence(cmd, NAME).run


def test_repo_frame_does_not_treat_subpages_or_api_as_repo_roots():
    assert root_candidate(URL)
    assert not root_candidate(URL + '/issues')
    assert not root_candidate(URL + '/blob/main/README.md')
    assert not root_candidate('https://gitlab.com/api/v4/projects')
    assert not root_candidate('https://gitlab.com/ai-village-agents/village')
