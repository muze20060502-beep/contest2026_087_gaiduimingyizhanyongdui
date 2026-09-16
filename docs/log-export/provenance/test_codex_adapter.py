import sys, json, tempfile, os
from pathlib import Path
BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(BASE/'work/official-collector/skills/contest-log-collector/adapters/codex'))
from recover_rollout import parse_rollout, recover
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    src=root/'test.jsonl'
    rows=[
        {'type':'session_meta','payload':{'id':'test-sid','timestamp':'2026-09-11T01:00:00.000Z','source':'vscode','originator':'codex_work_desktop'}},
        {'type':'response_item','timestamp':'2026-09-11T01:00:01.123Z','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'real prompt'}]}},
        {'type':'response_item','timestamp':'2026-09-11T01:00:02.456Z','payload':{'type':'function_call','name':'read','call_id':'c1','arguments':'{"path":"x"}'}},
        {'type':'response_item','timestamp':'2026-09-11T01:00:03.789Z','payload':{'type':'function_call_output','call_id':'c1','output':'ok'}},
        {'type':'response_item','timestamp':'2026-09-11T01:00:04.111Z','payload':{'type':'message','role':'assistant','channel':'final','content':[{'type':'output_text','text':'real answer'}]}},
        {'type':'response_item','timestamp':'2026-09-11T01:00:04.222Z','payload':{'type':'message','role':'developer','content':[{'type':'input_text','text':'excluded instruction'}]}},
        {'type':'event_msg','payload':{'type':'agent_message','message':'real answer'}},
    ]
    src.write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
    meta,events,data,count=parse_rollout(src)
    assert len(events)==4
    assert events[0]['text']=='real prompt' and events[0]['ts']==rows[1]['timestamp']
    assert events[1]['input']=={'path':'x'}
    assert events[1]['tool_call_id']==events[2]['tool_call_id']=='c1'
    assert 'tokens_in' not in events[3]
    os.environ['TEAM_ID']='contest2026_087_gaiduimingyizhanyongdui'
    os.environ['GITHUB_LOGIN']='muze20060502-beep'
    staging=root/'staging'
    recover([src],staging,confirm=False)
    assert not staging.exists()
    recover([src],staging,confirm=True)
    target=next(staging.rglob('codex__*.jsonl'))
    first=target.read_bytes()
    recover([src],staging,confirm=True)
    assert target.read_bytes()==first
    src.write_text('invalid',encoding='utf-8')
    try: recover([src],staging,confirm=True)
    except ValueError: pass
    else: raise AssertionError('invalid source accepted')
    assert target.read_bytes()==first
print('PASS: native mapping, timestamps, tool pairing, exclusions, preview, idempotence, invalid source protection')
