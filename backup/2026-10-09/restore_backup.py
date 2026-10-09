from pathlib import Path
import argparse, json, hashlib, shutil

def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): value.update(block)
    return value.hexdigest()

def main():
    parser=argparse.ArgumentParser(description='Verify or restore the public thesis backup without overwriting existing files.')
    parser.add_argument('--output',type=Path,help='New, non-existing directory for restored materials')
    args=parser.parse_args()
    here=Path(__file__).resolve().parent
    repo=here.parents[1]
    manifest=json.loads((here/'manifest.json').read_text(encoding='utf8'))
    if args.output:
        output=args.output.resolve()
        if output.exists(): raise SystemExit('Output directory already exists; choose a new directory.')
    checked={}
    for item in manifest['files']:
        source=(repo/item['stored']).resolve()
        if not source.is_relative_to(repo): raise SystemExit('Unsafe stored path')
        if source not in checked: checked[source]=digest(source)
        if checked[source]!=item['sha256']: raise SystemExit('Checksum mismatch: '+item['stored'])
    if args.output:
        for item in manifest['files']:
            target=(output/item['source']).resolve()
            if not target.is_relative_to(output): raise SystemExit('Unsafe restoration path')
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(repo/item['stored'],target)
            if digest(target)!=item['sha256']: raise SystemExit('Restored checksum mismatch')
    print('Verified',len(manifest['files']),'original file paths from',len(checked),'stored files.')
    if args.output: print('Restored to',output)

if __name__=='__main__': main()
