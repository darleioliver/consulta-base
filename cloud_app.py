"""Inicializa a base empacotada antes de executar o aplicativo original."""
import gzip
import hashlib
import os
from pathlib import Path
import runpy
import shutil
import tempfile

import streamlit as st

ROOT = Path(__file__).resolve().parent
EXPECTED_SHA256 = '9e7a2d1353036f8ca1b135a121b9383d4275191d74bbf856fbe7732266e9860f'


@st.cache_resource(show_spinner=False)
def prepare_database():
    destination = ROOT / 'base_contagens.sqlite'
    if destination.exists():
        return
    parts = sorted(ROOT.glob('base.sqlite.gz.part*'))
    if not parts:
        raise RuntimeError('Os arquivos da base não foram encontrados.')
    digest = hashlib.sha256()
    temporary_path = None
    try:
        with tempfile.TemporaryFile() as compressed:
            for part in parts:
                with part.open('rb') as source:
                    shutil.copyfileobj(source, compressed, 1024 * 1024)
            compressed.seek(0)
            with tempfile.NamedTemporaryFile(dir=ROOT, suffix='.tmp', delete=False) as output:
                temporary_path = Path(output.name)
                with gzip.GzipFile(fileobj=compressed, mode='rb') as source:
                    while block := source.read(1024 * 1024):
                        digest.update(block)
                        output.write(block)
        if digest.hexdigest() != EXPECTED_SHA256:
            raise RuntimeError('A verificação de integridade da base falhou.')
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


prepare_database()
runpy.run_path(str(ROOT / 'sistema_filtros_uf_multi_faixas.py'), run_name='__main__')
