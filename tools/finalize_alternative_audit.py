"""Record successful browser checks after a separate source/visual review."""

import argparse
import hashlib
import json
from pathlib import Path


def finalize(alternative):
    plan=Path(f'plans/architect-alt-{alternative}-v2.json')
    browser=json.loads(Path(f'pdf_renders/alt{alternative}-v2/browser-checks.json').read_text())
    assert browser['planSha256']==hashlib.sha256(plan.read_bytes()).hexdigest(), 'Browser check is stale'
    assert not browser['errors']
    assert len(browser['checks'])==4
    assert all(not c['blocked'] and c['colors']>20 for c in browser['checks'])
    audit_path=Path(f'docs/alt{alternative}-v2-layer-audit.json')
    audit=json.loads(audit_path.read_text(encoding='utf-8'))
    assert audit['validation']['generatorChecksPassed']
    assert audit['roof'].get('ridgeX') is not None
    audit['validation'].update(publicationReady=True,pending=[],planSha256=browser['planSha256'],
        sourceOverlayReviewed=True,browser=browser,
        scope='Visualization checked against source geometry. Inferred openings and source discrepancies remain documented in the source recipe; not a construction certification.')
    audit_path.write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-and-visual-reviewed',action='store_true',required=True)
    parser.add_argument('alternatives',nargs='+',type=int,choices=[3,5])
    args=parser.parse_args()
    for alt in args.alternatives:
        finalize(alt)
