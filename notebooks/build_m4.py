"""Build a notebook from ordered # %% source cells, without executing or changing DBs."""
import argparse
from pathlib import Path
import re

import nbformat

ROOT = Path(__file__).resolve().parents[1]


def source_cells(path):
    kind, lines = None, []
    cells = []
    for line in path.read_text(encoding='utf-8').splitlines(keepends=True):
        marker = re.fullmatch(r'# %%\s*(\[markdown\])?\s*\n?',line)
        if marker:
            if kind is not None:
                cells.append(make_cell(kind,lines))
            kind, lines = ('markdown' if marker[1] else 'code'), []
        elif kind is not None:
            lines.append(line)
        elif line.strip():
            raise ValueError('Every source must start with a # %% cell marker: '+str(path))
    if kind is not None:
        cells.append(make_cell(kind,lines))
    return cells


def make_cell(kind,lines):
    if kind=='markdown':
        source = ''.join(re.sub(r'^# ?', '',line) for line in lines).strip()
        return nbformat.v4.new_markdown_cell(source)
    return nbformat.v4.new_code_cell(''.join(lines).strip())


def build(output=None):
    sources = [ROOT/'notebooks/m4_cagatay.py']
    egemen = ROOT/'notebooks/m4_egemen.py'
    if egemen.exists():
        sources.append(egemen)
    cells = [cell for path in sources for cell in source_cells(path)]
    cells.extend(source_cells(ROOT/'notebooks/m4_finalize.py'))
    for index,cell in enumerate(cells):
        cell.id = 'm4-cell-'+str(index).zfill(3)
    notebook = nbformat.v4.new_notebook(cells=cells,metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
    nbformat.validate(notebook)
    target = output or ROOT/'notebooks/m4_eda.ipynb'
    target.parent.mkdir(parents=True,exist_ok=True)
    nbformat.write(notebook,target)
    print('Built',target,'from',[p.name for p in sources])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    build(args.output)
