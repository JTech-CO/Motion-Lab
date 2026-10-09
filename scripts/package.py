"""Package the runtime, rebuild inputs and user documentation without tests."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'Motion-Lab.zip'
FOLDERS = ('dist', 'data', 'motionlab', 'scripts', 'docs/assets', 'skills')
DOCS = ('asset-analysis.md', 'collection.md', 'interfaces.md', 'recipes.md')
EXCLUDED = {'__pycache__', '.cache', '.git', '.vsf', 'node_modules'}

def main():
    files = []
    for directory in FOLDERS:
        for file in (ROOT / directory).rglob('*'):
            if file.is_file() and not EXCLUDED.intersection(file.relative_to(ROOT).parts) and file.suffix not in ('.pyc','.pyo','.log','.mp4','.mov','.webm'):
                files.append(file)
    files.extend(ROOT / 'docs' / file for file in DOCS if (ROOT / 'docs' / file).is_file())
    files.extend(ROOT / file for file in ('README.md','.gitignore','.gitattributes') if (ROOT/file).is_file())
    # The source checkout keeps its regression command; the portable archive
    # does not ship development tests, so its package metadata omits that command.
    package = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))
    package.get('scripts', {}).pop('test', None)
    with zipfile.ZipFile(OUTPUT,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in sorted(files):
            archive.write(file, 'Motion Lab/' + file.relative_to(ROOT).as_posix())
        archive.writestr('Motion Lab/package.json', json.dumps(package, indent=2) + '\n')
    with zipfile.ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        if bad: raise ValueError('Archive validation failed: '+bad)
        print(f'{OUTPUT.name}: {len(archive.namelist())} files, {OUTPUT.stat().st_size:,} bytes; integrity OK')

if __name__=='__main__': main()
