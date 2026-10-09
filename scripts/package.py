"""Package the runtime, rebuild inputs and user documentation without tests."""
import json
import os
from pathlib import Path
import stat
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'Motion-Lab.zip'
FOLDERS = ('dist', 'data', 'motionlab', 'scripts', 'docs/assets', 'skills')
DOCS = ('asset-analysis.md', 'collection.md', 'interfaces.md', 'recipes.md')
EXCLUDED = {'__pycache__', '.cache', '.git', '.vsf', 'node_modules'}
EXCLUDED_SUFFIXES = {'.pyc', '.pyo', '.log', '.mp4', '.mov', '.webm'}


def checked_path(path, root, *, missing=False):
    """Reject linked components before reading; all paths must stay in root."""
    path, root = Path(path).absolute(), Path(root).absolute()
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValueError('Package path escaped the project') from error
    if '..' in relative.parts:
        raise ValueError('Package path escaped the project')
    current = root
    for component in (None, *relative.parts):
        if component is not None:
            current /= component
        try:
            info = current.lstat()
        except FileNotFoundError:
            if missing and current != root:
                return None
            raise
        if (stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise ValueError('Linked path is not allowed in package: ' + repr(current.relative_to(root).as_posix()))
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
    except ValueError as error:
        raise ValueError('Package path escaped the project') from error
    return info


def collect_files(root):
    root = Path(root).absolute()
    checked_path(root, root)
    files = []
    for directory in FOLDERS:
        base = root / directory
        base_info = checked_path(base, root, missing=True)
        if base_info is None:
            continue
        if not stat.S_ISDIR(base_info.st_mode):
            raise ValueError('Package source must be a directory')
        pending = [base]
        while pending:
            current = pending.pop()
            info = checked_path(current, root)
            if stat.S_ISDIR(info.st_mode):
                pending.extend(child for child in current.iterdir() if child.name not in EXCLUDED)
            elif stat.S_ISREG(info.st_mode) and current.suffix not in EXCLUDED_SUFFIXES:
                files.append(current)
            elif not stat.S_ISREG(info.st_mode):
                raise ValueError('Non-regular file is not allowed in package')
    for path in [*(root / 'docs' / name for name in DOCS),
                 *(root / name for name in ('README.md', '.gitignore', '.gitattributes'))]:
        info = checked_path(path, root, missing=True)
        if info is not None:
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Package documentation must be a regular file')
            files.append(path)
    return sorted(set(files))

def main():
    files = collect_files(ROOT)
    # The source checkout keeps its regression command; the portable archive
    # does not ship development tests, so its package metadata omits that command.
    package_path = ROOT / 'package.json'
    if not stat.S_ISREG(checked_path(package_path, ROOT).st_mode):
        raise ValueError('Package metadata must be a regular file')
    package = json.loads(package_path.read_text(encoding='utf-8'))
    package.get('scripts', {}).pop('test', None)
    output_info = checked_path(OUTPUT, ROOT, missing=True)
    if output_info is not None and not stat.S_ISREG(output_info.st_mode):
        raise ValueError('Package output must be a regular file')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=ROOT, prefix='.motionlab-package-', suffix='.zip', delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for file in files:
                if not stat.S_ISREG(checked_path(file, ROOT).st_mode):
                    raise ValueError('Package input must remain a regular file')
                archive.write(file, 'Motion Lab/' + file.relative_to(ROOT).as_posix())
            archive.writestr('Motion Lab/package.json', json.dumps(package, indent=2) + '\n')
        with zipfile.ZipFile(temporary) as archive:
            bad = archive.testzip()
            if bad:
                raise ValueError('Archive validation failed: ' + bad)
            count = len(archive.namelist())
        checked_path(OUTPUT, ROOT, missing=True)
        os.replace(temporary, OUTPUT)
        print(f'{OUTPUT.name}: {count} files, {OUTPUT.stat().st_size:,} bytes; integrity OK')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

if __name__=='__main__': main()
