"""Publish only explicitly listed artist guides. Research stays out of every output."""
from pathlib import Path, PurePosixPath
from mkdocs.exceptions import PluginError

def _pages(nav):
    for item in nav:
        if isinstance(item,str):yield item
        elif isinstance(item,dict):
            for value in item.values():
                if isinstance(value,str):yield value
                elif isinstance(value,list):yield from _pages(value)

def on_files(files,config):
    allowed=set(_pages(config['nav']))
    for path in allowed:
        if path!='index.md' and (not path.startswith('plugin/') or path in {
            'plugin/material_advanced_reference.md','plugin/material_handler_inventory.md',
            'plugin/artist_class_audit.md'}):
            raise PluginError('Public documentation may only list artist guides: '+path)
    for file in list(files):
        # Keep theme assets supplied by MkDocs/Material, not private docs.
        if file.src_dir and Path(file.src_dir).resolve()!=Path(config['docs_dir']).resolve():continue
        path=file.src_uri
        asset=path.startswith('assets/images/') and PurePosixPath(path).suffix.lower() in {'.png','.jpg','.jpeg','.webp','.svg','.ico'}
        if path not in allowed and not asset:files.remove(file)
    return files
