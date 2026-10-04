"""Conservative shell-intent sensitivity, not a shell interpreter or provenance check.

Tracks explicit working directories within a turn, separates simple commands,
retains quoted path arguments, and removes heredoc payloads. Unsupported shell
constructs are not resolved. Missing cross-turn cwd/aliases are coverage limits.
"""
from dataclasses import dataclass
from pathlib import PurePosixPath
import re
import shlex


DELIMITERS = {';', '&&', '||', '|', '&', '(', ')', '{', '}'}
HD = re.compile(r"<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z_0-9]*)\2")


def without_payloads(command):
    lines = (command or '').splitlines(keepends=True)
    result = []
    pending = []
    for line in lines:
        if pending:
            delimiter, tabs = pending[0]
            if (line.lstrip('\t') if tabs else line).strip('\r\n') == delimiter:
                pending.pop(0)
            continue
        pending.extend((m.group(3), bool(m.group(1))) for m in HD.finditer(line))
        result.append(HD.sub(' ', line))
    return ''.join(result)


def segments(command):
    # Newlines are shell separators, including inside an ordinary multiline quote.
    # shlex preserves that quote; inject separators only outside quotes.
    body = without_payloads(command)
    lexer = shlex.shlex(body, posix=True, punctuation_chars=';&|(){}\n')
    lexer.whitespace = ' \t\r'
    lexer.whitespace_split = True
    lexer.commenters = '#'
    parts, current = [], []
    try:
        for token in lexer:
            if token in DELIMITERS or token.strip('\n') == '':
                if current:
                    parts.append(current)
                current = []
            else:
                current.append(token)
    except ValueError:
        return []
    if current:
        parts.append(current)
    return parts


def local_repo(path, name):
    return '://' not in path and name.lower() in PurePosixPath(path.lower()).parts


@dataclass(frozen=True)
class ShellEvidence:
    run: bool = False
    contribution: bool = False


def shell_evidence(command, name):
    cwd = False
    run = contribution = False
    for words in segments(command):
        while words and (re.match(r'^\w+=', words[0]) or words[0] == 'env'):
            words = words[1:]
        if words and words[0] in {'timeout','xargs'}:
            wrapper, words = words[0], words[1:]
            while words and words[0].startswith('-'):
                option, words = words[0], words[1:]
                if option in {'-s','--signal','-k','--kill-after','-n','-P','-I','-d'}:
                    words = words[1:]
            if wrapper == 'timeout':
                words = words[1:]  # duration precedes the wrapped command
        if not words:
            continue
        tool = PurePosixPath(words[0]).name.lower()
        args = words[1:]
        if tool == 'cd':
            cwd = bool(args and local_repo(args[-1], name))
            continue
        if tool in {'pushd', 'popd'}:
            cwd = bool(args and local_repo(args[0], name))
            continue
        if tool in {'bash', 'sh'} and '-c' in args:
            at = args.index('-c')
            if at + 1 < len(args):
                inner = shell_evidence(('cd ' + shlex.quote(name) + '; ' if cwd else '') + args[at + 1], name)
                run |= inner.run
                contribution |= inner.contribution
            continue
        direct_path = False
        git_cwd = cwd
        if tool == 'git' and '-C' in args:
            at = args.index('-C')
            git_cwd = at + 1 < len(args) and local_repo(args[at + 1], name)
            args = args[at + 2:]
        if tool == 'git' and git_cwd and args and args[0] in {'commit', 'push'}:
            contribution = True  # intent only; completion is not observed
        file_run = False
        script = None
        if re.fullmatch(r'python\d*(?:\.\d+)?', tool):
            if '-c' not in args and args:
                if '-m' in args:
                    at = args.index('-m')
                    module = args[at + 1] if at + 1 < len(args) else ''
                    file_run = bool(module and module not in {'pip', 'piptools', 'http.server', 'json.tool', 'venv'})
                else:
                    script = next((x for x in args if x.endswith('.py') and not x.startswith('-')),None)
                    file_run = script is not None
        elif tool in {'node', 'nodejs'}:
            file_run = not any(x in args for x in ['-e','--check','-c']) and any(x.endswith(('.js', '.cjs', '.mjs')) for x in args)
            script = next((x for x in args if x.endswith(('.js','.cjs','.mjs'))),None)
        elif tool in {'bash', 'sh'}:
            file_run = any(x.endswith('.sh') for x in args)
            script = next((x for x in args if x.endswith('.sh')),None)
        elif tool in {'pytest', 'make'}:
            file_run = True
            direct_path = any(local_repo(x,name) and not x.endswith(('.ini','.toml','.cfg')) for x in args)
        elif tool in {'npm', 'pnpm', 'yarn', 'cargo', 'go'}:
            file_run = bool(args and args[0] in {'run', 'test', 'build', 'check'})
        elif tool == 'npx':
            file_run = bool(args and args[0] in {'pytest', 'jest', 'vitest', 'playwright', 'tsc', 'vite', 'tsx'})
        # A URL argument and a cd that has been superseded cannot establish local execution.
        external_script = bool(script and (script.startswith(('/', '~', '../'))) and not local_repo(script,name))
        if script:
            direct_path = local_repo(script,name)
        if file_run and not external_script and (cwd or direct_path):
            run = True
    return ShellEvidence(run, contribution)


def strict_touch(action, url):
    """Explicit retrieval/clone request, excluding typed text and API/post payloads.

    Returned category describes request syntax; it does not establish successful
    page delivery, a clone, or reading. Browser URL navigation must be explicit.
    """
    if isinstance(action, str):
        import json
        action = json.loads(action)
    kind = action.get('action') or action.get('type')
    target = action.get('url')
    if target and target.rstrip('/') == url.rstrip('/') and kind in {'navigate', 'open_url', 'browse'}:
        return 'navigation_request'
    for words in segments(action.get('command', '')):
        if not words:
            continue
        tool = PurePosixPath(words[0]).name
        args = words[1:]
        matching = [x for x in args if x.rstrip('/').removesuffix('.git') == url.rstrip('/')]
        if tool == 'git' and 'clone' in args and matching:
            return 'clone_request'
        if tool in {'curl', 'wget'} and matching:
            if any(x in args for x in ['-d', '--data', '--data-raw', '--data-binary', '--json', '-F', '--form']):
                continue
            if '-X' in args and args[args.index('-X') + 1:args.index('-X') + 2] != ['GET']:
                continue
            return 'retrieval_request'
    return None
