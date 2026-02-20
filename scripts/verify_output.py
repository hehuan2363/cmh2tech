import csv, glob, os

files = sorted(glob.glob('/home/hehua/RepoClaudeCode/CMH2Tech/docs/coldemails/Leads/*-with-icebreakers.csv'))
for f in files:
    with open(f, 'r', encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    total = len(rows)
    ok = sum(1 for r in rows if r.get('icebreaker', '').strip() and r['icebreaker'] != 'SKIP')
    skip = sum(1 for r in rows if r.get('icebreaker') == 'SKIP')
    empty = total - ok - skip
    print(os.path.basename(f))
    print(f'  Total: {total} | Icebreakers: {ok} | Skipped: {skip} | Empty: {empty}')
    samples = [r for r in rows if r.get('icebreaker', '').strip() and r['icebreaker'] != 'SKIP'][:3]
    for s in samples:
        print(f'  > {s["icebreaker"]}')
    print()
