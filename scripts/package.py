"""Create a portable archive without host identity, credentials or local reports."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'Motion-Lab.zip'
FOLDERS = ('dist', 'data', 'motionlab', 'scripts', 'docs', 'skills', 'tests')
EXCLUDED = {'__pycache__', '.cache', '.git', '.vsf', 'node_modules'}

def main():
    files = []
    for directory in FOLDERS:
        for file in (ROOT / directory).rglob('*'):
            if file.is_file() and not EXCLUDED.intersection(file.relative_to(ROOT).parts) and file.suffix not in ('.pyc','.pyo','.log','.mp4','.mov','.webm'):
                files.append(file)
    files.extend(ROOT / file for file in ('README.md','package.json','.gitignore') if (ROOT/file).is_file())
    with zipfile.ZipFile(OUTPUT,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for file in sorted(files):
            archive.write(file, 'Motion Lab/' + file.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(OUTPUT) as archive:
        bad = archive.testzip()
        if bad: raise ValueError('Archive validation failed: '+bad)
        print(f'{OUTPUT.name}: {len(archive.namelist())} files, {OUTPUT.stat().st_size:,} bytes; integrity OK')

if __name__=='__main__': main()
