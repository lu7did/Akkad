#!/usr/bin/env python3
"""Descarga el archivo model.keras de un repositorio HuggingFace."""
import argparse
from pathlib import Path
import shutil
VERSION="0.6.184"
def main():
    p=argparse.ArgumentParser(description="Descargar modelo Keras desde HuggingFace")
    p.add_argument('--name',required=True,help='ViT-Small, ViT-Medium o repositorio owner/name')
    p.add_argument('--out',help='Archivo .keras de destino (default: {name}.keras)')
    p.add_argument('--verbose',action='store_true')
    a=p.parse_args(); name=a.name.strip()
    aliases={'vit-small':'mateuszgrzyb/searchless-chess-vit-small','vit-medium':'mateuszgrzyb/searchless-chess-vit-medium'}
    repo=aliases.get(name.lower(),name if '/' in name else 'mateuszgrzyb/'+name)
    target=Path(a.out or (name.replace('/','_')+'.keras')).expanduser().resolve()
    if target.suffix.lower()!='.keras':p.error('--out requiere extensión .keras')
    print(f'📦 keras-getModel v{VERSION} | modelo={repo} | salida={target}')
    from huggingface_hub import hf_hub_download
    source=Path(hf_hub_download(repo_id=repo,filename='model.keras'))
    target.parent.mkdir(parents=True,exist_ok=True)
    if source.resolve()!=target:shutil.copyfile(source,target)
    print(f'✅ Descargado: {target} ({target.stat().st_size:,} bytes)')
    if a.verbose:print(f'🔍 Origen de caché: {source}')
if __name__=='__main__':main()
