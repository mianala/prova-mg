#!/usr/bin/env python3
"""dist/prova-mg-google-doc.html -> blocks.json for the docx builder."""
import json, re, sys
from bs4 import BeautifulSoup, NavigableString, Tag

SRC = sys.argv[1]
DEST = sys.argv[2]

soup = BeautifulSoup(open(SRC, encoding='utf-8').read(), 'lxml')


def runs_of(node, bold=False, italic=False, mono=False, link=None):
    """Flatten inline content into styled runs."""
    out = []
    for child in node.children:
        if isinstance(child, NavigableString):
            if type(child) is not NavigableString:
                continue
            t = str(child)
            if t:
                out.append({'text': t, 'bold': bold, 'italic': italic,
                            'mono': mono, 'link': link})
        elif isinstance(child, Tag):
            if child.name == 'br':
                out.append({'text': '\n', 'bold': bold, 'italic': italic,
                            'mono': mono, 'link': link})
                continue
            b = bold or child.name in ('b', 'strong')
            i = italic or child.name in ('i', 'em')
            m = mono or child.name == 'code' or \
                'Courier' in (child.get('style') or '')
            l = link
            if child.name == 'a' and child.get('href'):
                l = child['href']
            out.append({'text': '', 'sup': child.name == 'sup'}) if False else None
            out.extend(runs_of(child, b, i, m, l))
    return [r for r in out if r['text']]


def merge(runs):
    """Coalesce adjacent runs sharing formatting."""
    merged = []
    for r in runs:
        if merged:
            p = merged[-1]
            if (p['bold'], p['italic'], p['mono'], p['link']) == \
               (r['bold'], r['italic'], r['mono'], r['link']):
                p['text'] += r['text']
                continue
        merged.append(dict(r))
    for r in merged:
        r['text'] = re.sub(r'[ \t]+', ' ', r['text'])
    while merged and not merged[0]['text'].strip():
        merged.pop(0)
    while merged and not merged[-1]['text'].strip():
        merged.pop()
    if merged:
        merged[0]['text'] = merged[0]['text'].lstrip(' ')
        merged[-1]['text'] = merged[-1]['text'].rstrip(' ')
    return merged


def classify(p):
    """Map the generated inline styles back to a semantic paragraph kind."""
    s = p.get('style') or ''
    if 'text-align:center' in s and 'Courier' in s:
        return 'formula'
    if 'Courier' in s and 'margin:0' in s:
        return 'listing'
    if 'letter-spacing' in s:
        return 'label'
    if 'font-style:italic' in s:
        return 'standfirst'
    if 'font-weight:bold' in s:
        return 'subtitle'
    if 'margin-left' in s:
        return 'bullet'
    return 'body'


blocks = []


def walk(node, indent=0):
    for el in node.children:
        if not isinstance(el, Tag):
            continue
        n = el.name
        if n in ('h1', 'h2', 'h3', 'h4', 'h5'):
            blocks.append({'type': n, 'text': el.get_text(' ', strip=True)})
        elif n == 'p':
            kind = classify(el)
            r = merge(runs_of(el))
            if not r:
                if kind == 'listing':
                    blocks.append({'type': 'p', 'kind': 'listing',
                                   'runs': [], 'indent': indent})
                continue
            blocks.append({'type': 'p', 'kind': kind, 'runs': r,
                           'indent': indent})
        elif n in ('ul', 'ol'):
            for k, li in enumerate(el.find_all('li', recursive=False), 1):
                nested = [c for c in li.find_all(['ul', 'ol'], recursive=False)]
                for x in nested:
                    x.extract()
                r = merge(runs_of(li))
                if r:
                    blocks.append({'type': 'li', 'runs': r, 'indent': indent,
                                   'ordered': n == 'ol'})
                for x in nested:
                    walk_list(x, indent + 1)
        elif n == 'table':
            rows = []
            for tr in el.find_all('tr'):
                cells = []
                for td in tr.find_all(['td', 'th']):
                    cells.append({'runs': merge(runs_of(td)),
                                  'header': td.name == 'th'})
                if cells:
                    rows.append(cells)
            if rows:
                blocks.append({'type': 'table', 'rows': rows, 'indent': indent})
        elif n == 'blockquote':
            walk(el, indent + 1)
        elif n == 'hr':
            blocks.append({'type': 'hr'})
        else:
            walk(el, indent)


def walk_list(el, indent):
    for li in el.find_all('li', recursive=False):
        r = merge(runs_of(li))
        if r:
            blocks.append({'type': 'li', 'runs': r, 'indent': indent,
                           'ordered': el.name == 'ol'})


walk(soup.body)
json.dump(blocks, open(DEST, 'w', encoding='utf-8'), ensure_ascii=False)
kinds = {}
for b in blocks:
    k = b['type'] + (':' + b.get('kind', '') if b['type'] == 'p' else '')
    kinds[k] = kinds.get(k, 0) + 1
print('blocks:', len(blocks))
for k, v in sorted(kinds.items()):
    print(f'  {v:5}  {k}')
