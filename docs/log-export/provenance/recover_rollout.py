"""Local compatibility patch, not an upstream-approved collector release.

Explicit paths only: no workspace spoofing, no automatic personal-session scan.
Native records stay unchanged. Use official redaction and JSONL/manifest writers.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'shared'))
import snapshot_core as core

GENERATOR_TOOL = 'codex-rollout-local-fix'

def parse_rollout(path):
    data = Path(path).read_bytes()
    records = [json.loads(line) for line in data.decode('utf-8').splitlines() if line.strip()]
    if not records or records[0].get('type') != 'session_meta':
        raise ValueError('Expected native Codex session_meta header')
    meta = records[0]['payload']
    sid = meta['id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+', sid):
        raise ValueError('Unsafe session ID')
    events = []
    model = None
    for source_line, raw in enumerate(records, 1):
        payload = raw.get('payload') or {}
        if raw.get('type') == 'turn_context':
            model = payload.get('model')
        if raw.get('type') != 'response_item':
            continue
        kind = payload.get('type')
        event = None
        if kind == 'message' and payload.get('role') in ('user', 'assistant'):
            if payload.get('channel') in ('analysis', 'summary'):
                continue
            texts = [b['text'] for b in payload.get('content', [])
                     if b.get('type') in ('text', 'input_text', 'output_text') and isinstance(b.get('text'), str)]
            if texts:
                event = {'role': payload['role'], 'text': '\n'.join(texts)}
        elif kind in ('function_call', 'custom_tool_call'):
            args = payload.get('arguments', payload.get('input'))
            if kind == 'function_call' and isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    pass
            event = dict(role='tool', tool_name=payload['name'], tool_call_id=payload['call_id'], input=args, output=None)
        elif kind in ('function_call_output', 'custom_tool_call_output'):
            event = dict(role='tool', tool_name='<result>', tool_call_id=payload['call_id'], input=None, output=payload.get('output'))
        if event is not None:
            event['ts'] = raw['timestamp']
            event['metadata'] = {'source_line':source_line, 'source_type':kind}
            if model and event['role'] == 'assistant':
                event['model'] = model
            events.append(event)
    if not events:
        raise ValueError('No visible Codex events; refusing an empty export')
    return meta, events, data, len(records)

def recover(paths, staging, github_login=None, confirm=False):
    core.load_env_file()
    team = os.environ.get('TEAM_ID', '')
    login = github_login or os.environ.get('GITHUB_LOGIN', '')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]+', team):
        raise ValueError('Set valid TEAM_ID')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', login):
        raise ValueError('Set valid GITHUB_LOGIN')
    # Parse every selected file before writing any file.
    parsed = [(Path(p), *parse_rollout(p)) for p in paths]
    if len({x[1]['id'] for x in parsed}) != len(parsed):
        raise ValueError('Duplicate selected session')
    member = Path(staging) / login
    manifest = core.read_manifest(member, team, login, GENERATOR_TOOL)
    if manifest['team_id'] != team or manifest['github_login'] != login:
        raise ValueError('Existing staging identity mismatch')
    selected = []
    for path, meta, events, data, raw_count in parsed:
        sid = meta['id']
        rel = f'{meta["timestamp"][:10]}/codex__{sid}.jsonl'
        target = member / rel
        old = next((e for e in manifest['sessions'] if e['session_id'] == sid), None)
        digest = hashlib.sha256(data).hexdigest()
        if old or target.exists():
            if old and target.exists() and old.get('source_integrity', {}).get('main_sha256') == digest:
                selected.append({**old, 'github_login':login})
                continue
            raise ValueError('Staging session already exists with different source; use a fresh SESSION_LOG_DIR')
        source = meta.get('source')
        if source not in ('vscode', 'cli'):
            raise ValueError(f'Unknown source {source!r}; cannot truthfully classify collection_mode')
        entry = dict(session_id=sid, tool='codex', started_at=meta['timestamp'], last_event_at=events[-1]['ts'],
            event_count=len(events), raw_event_count=raw_count, file_path=f'logs/{login}/{rel}',
            collection_mode='vscode_extension_partial' if source == 'vscode' else 'cli',
            health='degraded', source_originator=meta.get('originator'), source_kind=source,
            recovery_method='explicit-native-rollout; local compatibility patch; not upstream approved',
            data_completeness_warning='Visible messages and tool calls/results only. Excludes system/developer instructions, private reasoning, media and duplicate runtime bookkeeping. Snapshot through export time. Historical recovery outside automatic workspace gate, explicitly selected by user. Contest acceptance unconfirmed.',
            source_integrity=dict(main_sha256=digest, main_size=len(data), captured_at=core.iso_now()))
        print(f'{sid}: {len(events)} events; source={source}; originator={meta.get("originator")}')
        if confirm:
            member.mkdir(parents=True, exist_ok=True)
            result = core.append_events(target, events, sid, team, login, 'codex', 0, core.load_redact_rules(member))
            assert result['written'] == len(events)
            entry['redacted_count_total'] = result['redacted']
            manifest['sessions'].append(entry)
        selected.append({**entry, 'github_login':login})
    if confirm:
        core.write_manifest(member, manifest, team, login, GENERATOR_TOOL)
    return selected
