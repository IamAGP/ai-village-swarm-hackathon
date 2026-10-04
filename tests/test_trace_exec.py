import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'explorer'))
from trace_exec import REPO, runs_repo  # noqa: E402

N = 'graffiti-verification'


def test_runs_inside_repo_count():
    assert runs_repo('cd graffiti-verification && python3 verify/verify_conj66.py', N)
    assert runs_repo('python3 ~/graffiti-verification/verify/x.py', N)
    assert runs_repo('cd ~/work/graffiti-verification; pytest -q', N)


def test_parsing_api_replies_and_quotes_are_not_runs():
    # the false positive found on the first pass: API JSON piped into python -c
    assert not runs_repo("glab api projects/a%2Fgraffiti-verification 2>/dev/null | python3 -c 'import json'", N)
    assert not runs_repo("curl -s https://gitlab.com/a/graffiti-verification | python3 -c 'x'", N)
    assert not runs_repo("cat > post.md <<'EOF'\ncd graffiti-verification && python3 v.py\nEOF\n", N)
    assert not runs_repo("echo 'cd graffiti-verification && python3 v.py'", N)
    assert not runs_repo('git clone https://gitlab.com/x/graffiti-verification && ls', N)


def test_repo_url_parsing():
    assert REPO.match('https://gitlab.com/ai-village-agents/village/graffiti-verification').group(2) == N
    assert REPO.match('https://github.com/ai-village-agents/rpg-game.git').group(2) == 'rpg-game'
    assert REPO.match('https://github.com/ai-village-agents') is None
