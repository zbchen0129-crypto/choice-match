"""Bounded, read-only review of Git-visible project files; never opens .env."""
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    proc=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z','.'],
                        cwd=ROOT,capture_output=True,check=True,timeout=10)
    if len(proc.stdout)>1000000:raise ValueError('File list budget exceeded')
    names=sorted(set(n.decode() for n in proc.stdout.split(b'\0') if n))
    if len(names)>400:raise ValueError('File count budget exceeded')
    issues=[];local_paths=[];total=0
    for name in names:
        p=ROOT/name
        if not p.resolve().is_relative_to(ROOT):raise ValueError('Path outside project')
        if p.name.startswith('.env') and p.name!='.env.example' or 'data/private' in name or '.venv/' in name:
            issues.append({'file':name,'issue':'private path visible to Git'});continue
        size=p.stat().st_size;total+=size
        if size>3*1024**2 or total>20*1024**2:raise ValueError('File byte budget exceeded')
        if p.suffix.lower() in {'.png','.jpg','.jpeg'}:continue
        text=p.read_text()
        if re.search(r'(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}|postgres(?:ql)?://[^\s:@]+:[^\s@{}]+@',text):
            issues.append({'file':name,'issue':'credential-like token; content withheld'})
        if '/Users/' in text:local_paths.append(name)
    ignored={path:subprocess.run(['git','check-ignore','-q',path],cwd=ROOT).returncode==0
             for path in ['.env','.venv/test','data/private/test','.DS_Store']}
    result={'scope':'Git-visible project files only; heuristic scan, not a guarantee of no secrets',
            'file_count':len(names),'total_bytes':total,'private_paths_ignored':ignored,
            'findings':issues,'files_with_local_path_metadata':local_paths}
    print(json.dumps(result,indent=2))
    return bool(issues) or not all(ignored.values())

if __name__=='__main__':raise SystemExit(main())
