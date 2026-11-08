"""Fail the Pages build if private research pages or source evidence is present."""
import json,re,sys
from pathlib import Path


def verify(site):
    site=Path(site)
    forbidden=['drs','ska','bmg','bms','glossary','format-audit-status','bridges-terrain',
               'plugin/material_advanced_reference','plugin/material_handler_inventory','plugin/artist_class_audit']
    for path in forbidden:
        if (site/path).exists():raise SystemExit('Private research in public build: '+path)
    search=json.loads((site/'search/search_index.json').read_text(encoding='utf8'))
    for entry in search['docs']:
        location=entry['location'].split('#')[0]
        if location and not location.startswith('plugin/'):
            raise SystemExit('Unexpected public search entry: '+location)
        if re.search(r'0x[0-9a-fA-F]{8}|sha256=|\.asm\b',entry['text']):
            raise SystemExit('Developer evidence in public search: '+location)
    print('PUBLIC_GUIDES_ONLY_BUILD_AND_SEARCH_OK')

if __name__=='__main__':verify(sys.argv[1] if len(sys.argv)>1 else Path(__file__).parent/'site')
