#!/usr/bin/env python3
"""Merge the PROVA-MG HTML site into one Google-Docs-importable HTML file."""
import re, html, sys
from bs4 import BeautifulSoup, NavigableString, Tag, Comment

ROOT = "/home/user/prova-mg/"

# ---------------------------------------------------------------- LaTeX -> Unicode
GREEK = {
    'alpha':'α','beta':'β','gamma':'γ','delta':'δ','epsilon':'ε','varepsilon':'ε',
    'zeta':'ζ','eta':'η','theta':'θ','vartheta':'ϑ','iota':'ι','kappa':'κ',
    'lambda':'λ','mu':'μ','nu':'ν','xi':'ξ','pi':'π','rho':'ρ','sigma':'σ',
    'tau':'τ','upsilon':'υ','phi':'φ','varphi':'φ','chi':'χ','psi':'ψ','omega':'ω',
    'Gamma':'Γ','Delta':'Δ','Theta':'Θ','Lambda':'Λ','Xi':'Ξ','Pi':'Π','Sigma':'Σ',
    'Upsilon':'Υ','Phi':'Φ','Psi':'Ψ','Omega':'Ω',
}
SYMS = {
    'mid':'|','cdot':'·','times':'×','div':'÷','pm':'±','mp':'∓',
    'leq':'≤','le':'≤','geq':'≥','ge':'≥','neq':'≠','ne':'≠','approx':'≈',
    'equiv':'≡','sim':'∼','propto':'∝','ll':'≪','gg':'≫',
    'sum':'∑','prod':'∏','int':'∫','infty':'∞','partial':'∂','nabla':'∇',
    'in':'∈','notin':'∉','subset':'⊂','subseteq':'⊆','supset':'⊃','cup':'∪','cap':'∩',
    'emptyset':'∅','forall':'∀','exists':'∃','neg':'¬','land':'∧','lor':'∨',
    'rightarrow':'→','to':'→','leftarrow':'←','gets':'←','Rightarrow':'⇒',
    'Leftarrow':'⇐','leftrightarrow':'↔','Leftrightarrow':'⇔','mapsto':'↦',
    'langle':'⟨','rangle':'⟩','ldots':'…','cdots':'⋯','dots':'…','vdots':'⋮',
    'star':'★','ast':'∗','circ':'∘','oplus':'⊕','otimes':'⊗','perp':'⊥',
    'parallel':'∥','sqrt':'√','prime':'′','ell':'ℓ','Re':'ℜ','Im':'ℑ',
    'quad':' ','qquad':'  ',',':' ',';':' ','!':'','>':' ',' ':' ',
    ':':' ','|':'‖','\\':'  ','%':'%',
}
SUP = {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸',
       '9':'⁹','+':'⁺','-':'⁻','n':'ⁿ','i':'ⁱ','T':'ᵀ'}
SUB = {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈',
       '9':'₉','+':'₊','-':'₋','a':'ₐ','e':'ₑ','i':'ᵢ','j':'ⱼ','k':'ₖ','l':'ₗ',
       'm':'ₘ','n':'ₙ','o':'ₒ','p':'ₚ','r':'ᵣ','s':'ₛ','t':'ₜ','u':'ᵤ','v':'ᵥ','x':'ₓ'}
ACCENT = {'hat':'̂','bar':'̄','tilde':'̃','vec':'⃗','dot':'̇'}

# macros whose single {...} argument is kept verbatim
UNWRAP = {'mathrm','mathbf','mathcal','mathbb','text','textrm','textbf','texttt',
          'textit','operatorname','mathit','boldsymbol','boxed','mathsf','mathtt',
          'mbox','textsf','textsc','emph'}
# function-like operators rendered as words
OPS = {'log','exp','ln','max','min','argmax','argmin','sup','inf','lim','det',
       'dim','sin','cos','tan','tr','deg','gcd','Pr','softmax','sigmoid','diag'}
# purely typographic macros with no textual content
DROPPED = {'left','right','displaystyle','limits','nolimits','big','Big','bigg',
           'Bigg','bigl','bigr','Bigl','Bigr','biggl','biggr','Biggl','Biggr',
           'nonumber','notag','vphantom','phantom','hfill','strut'}


def _brace(s, i):
    """Return (content, index_after) for a {...} group starting at s[i]=='{'."""
    depth, j = 0, i
    while j < len(s):
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def latex_to_text(s, depth=0):
    """Best-effort LaTeX -> readable Unicode. Unknown constructs keep their source."""
    if depth > 12:
        return s
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == '\\':
            m = re.match(r'\\([A-Za-z]+)', s[i:])
            if m:
                name = m.group(1)
                j = i + m.end()
                if j < len(s) and s[j] == '*':      # e.g. \operatorname*
                    j += 1
                if name in ('begin', 'end'):        # environments: drop wrapper
                    if j < len(s) and s[j] == '{':
                        _, j = _brace(s, j)
                    i = j
                    continue
                if name in DROPPED:
                    i = j
                    continue
                if name == 'underbrace':
                    inner = ''
                    if j < len(s) and s[j] == '{':
                        inner, j = _brace(s, j)
                    label = ''
                    if j < len(s) and s[j] == '_':
                        j += 1
                        if j < len(s) and s[j] == '{':
                            label, j = _brace(s, j)
                        else:
                            label, j = s[j:j + 1], j + 1
                    txt = latex_to_text(inner, depth + 1)
                    if label:
                        txt += ' [' + latex_to_text(label, depth + 1) + ']'
                    out.append(txt)
                    i = j
                    continue
                if name in OPS:
                    out.append(name + ' ')
                    i = j
                    continue
                if name in UNWRAP:
                    if j < len(s) and s[j] == '{':
                        inner, j = _brace(s, j)
                        out.append(latex_to_text(inner, depth + 1))
                    i = j
                    continue
                if name in ('frac', 'tfrac', 'dfrac'):
                    a = b = ''
                    if j < len(s) and s[j] == '{':
                        a, j = _brace(s, j)
                    if j < len(s) and s[j] == '{':
                        b, j = _brace(s, j)
                    a, b = latex_to_text(a, depth + 1), latex_to_text(b, depth + 1)
                    wrap = lambda x: x if re.fullmatch(r'[\w.·]+', x) else '(' + x + ')'
                    out.append(wrap(a) + '/' + wrap(b))
                    i = j
                    continue
                if name in ACCENT:
                    if j < len(s) and s[j] == '{':
                        inner, j = _brace(s, j)
                    else:
                        inner, j = s[j:j + 1], j + 1
                    inner = latex_to_text(inner, depth + 1)
                    out.append(inner + ACCENT[name] if len(inner) == 1 else inner)
                    i = j
                    continue
                if name in ('left', 'right', 'displaystyle', 'limits', 'nolimits'):
                    i = j
                    continue
                if name in GREEK:
                    out.append(GREEK[name]); i = j; continue
                if name in SYMS:
                    out.append(SYMS[name]); i = j; continue
                out.append('\\' + name)
                i = j
                continue
            # escaped punctuation / spacing macro
            nxt = s[i + 1:i + 2]
            if nxt in SYMS:
                out.append(SYMS[nxt]); i += 2; continue
            if nxt in '{}%$&#_':
                out.append(nxt); i += 2; continue
            out.append(c); i += 1; continue
        if c in '_^':
            table = SUB if c == '_' else SUP
            j = i + 1
            if j < len(s) and s[j] == '{':
                inner, j = _brace(s, j)
            elif j < len(s) and s[j] == '\\':
                mm = re.match(r'\\[A-Za-z]+', s[j:])
                if mm:
                    inner, j = mm.group(0), j + mm.end()
                else:
                    inner, j = s[j:j + 2], j + 2
            else:
                inner, j = s[j:j + 1], j + 1
            conv = latex_to_text(inner, depth + 1)
            if conv and all(ch in table for ch in conv):
                out.append(''.join(table[ch] for ch in conv))
            else:
                out.append(c + ('(' + conv + ')' if len(conv) > 1 else conv))
            i = j
            continue
        if c in '{}':
            i += 1
            continue
        if c == '&':        # alignment marker inside aligned environments
            out.append(' ')
            i += 1
            continue
        out.append(c)
        i += 1
    return re.sub(r'  +', ' ', ''.join(out))


MATH_RE = re.compile(r'\$\$(.+?)\$\$|\\\[(.+?)\\\]|\\\((.+?)\\\)|\$(.+?)\$', re.S)


def convert_math_in_text(text):
    def rep(m):
        body = next(g for g in m.groups() if g is not None)
        return latex_to_text(body.strip())
    return MATH_RE.sub(rep, text)


def convert_math_in_tree(node):
    for t in list(node.find_all(string=True)):
        if t.parent.name in ('script', 'style'):
            continue
        new = convert_math_in_text(str(t))
        if new != str(t):
            t.replace_with(NavigableString(new))


# ---------------------------------------------------------------- styling helpers
S_LABEL = ("font-family:'Courier New',monospace;font-size:9pt;letter-spacing:1px;"
           "color:#8a7a5c;margin-bottom:2pt;")
S_STAND = "font-style:italic;color:#444444;"
S_MONO = "font-family:'Courier New',monospace;font-size:10pt;"
S_FORMULA = ("font-family:'Courier New',monospace;font-size:10.5pt;color:#1a1a1a;"
             "text-align:center;")
S_TAG = "font-family:'Courier New',monospace;font-size:9pt;color:#8a6d2f;"


def new_tag(soup, name, style=None, **attrs):
    t = soup.new_tag(name, **attrs)
    if style:
        t['style'] = style
    return t


def para(soup, style=None):
    return new_tag(soup, 'p', style)


def text_of(node):
    return re.sub(r'\s+', ' ', node.get_text(' ', strip=True)).strip()


def has_class(tag, name):
    return isinstance(tag, Tag) and name in (tag.get('class') or [])


# ---------------------------------------------------------------- block builders
def build_boxed(soup, node, label_classes=('lbl', 'tag')):
    """Callout-ish div -> indented blockquote with a bold leading label."""
    bq = soup.new_tag('blockquote')
    bq['style'] = "margin:6pt 0 6pt 18pt;border-left:2px solid #d8cdb4;padding-left:10pt;"
    lbl = None
    for cls in label_classes:
        el = node.find(class_=cls)
        if el is not None:
            lbl = text_of(el)
            el.decompose()
            break
    # Blocks (tables, lists, nested headings) cannot live inside a <p>; when the
    # box holds any, emit the label on its own line and recurse into the content.
    if node.find(['table', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'p']):
        if lbl:
            p = para(soup)
            b = soup.new_tag('b')
            b['style'] = S_TAG
            b.string = lbl.upper()
            p.append(b)
            bq.append(p)
        emit_children(node, soup, bq)
        return bq

    p = para(soup)
    if lbl:
        b = soup.new_tag('b')
        b['style'] = S_TAG
        b.string = lbl.upper() + ' — '
        p.append(b)
    move_inline(node, p, soup)
    bq.append(p)
    return bq


def build_pre(soup, node):
    """Whitespace-significant listing -> monospace paragraphs with nbsp indents."""
    wrap = soup.new_tag('blockquote')
    wrap['style'] = "margin:6pt 0 6pt 18pt;"
    lbl_el = node.find(class_='lbl')
    label = None
    if lbl_el is not None:
        label = text_of(lbl_el)
        lbl_el.decompose()
    if label:
        p = para(soup)
        b = soup.new_tag('b')
        b['style'] = S_TAG
        b.string = label
        p.append(b)
        wrap.append(p)
    raw = node.get_text('\n')
    raw = convert_math_in_text(raw)
    lines = [ln.rstrip() for ln in raw.split('\n')]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if lines:
        common = min((len(ln) - len(ln.lstrip()) for ln in lines if ln.strip()),
                     default=0)
    for ln in lines:
        p = para(soup, S_MONO + "margin:0;")
        body = ln[common:] if ln.strip() else ''
        indent = len(body) - len(body.lstrip())
        p.append(NavigableString(' ' * indent + body.strip()))
        if not body.strip():
            p.append(NavigableString(' '))
        wrap.append(p)
    return wrap


def style_table(soup, tbl):
    tbl['style'] = "border-collapse:collapse;width:100%;"
    tbl['border'] = '1'
    tbl['cellpadding'] = '5'
    for th in tbl.find_all('th'):
        th['style'] = ("border:1px solid #b9ae97;background-color:#f2ede2;"
                       "text-align:left;vertical-align:top;font-weight:bold;")
    for td in tbl.find_all('td'):
        td['style'] = "border:1px solid #b9ae97;vertical-align:top;"
    return tbl


# ---------------------------------------------------------------- page transform
DROP_SELECTORS = ['script', 'style', 'link', 'meta', 'noscript', 'button']
DROP_CLASSES = ['nav-back', 'pager', 'print-btn', 'controls', 'progress-shell',
                'progress-row', 'chapter-grid', 'foot', 'next']


def transform_page(path, heading, out_soup, out_root, drop_toc=True):
    src = open(ROOT + path, encoding='utf-8').read()
    soup = BeautifulSoup(src, 'lxml')

    for sel in DROP_SELECTORS:
        for t in soup.find_all(sel):
            t.decompose()
    for cls in DROP_CLASSES:
        for t in soup.find_all(class_=cls):
            t.decompose()
    if drop_toc:
        for t in soup.find_all('nav', class_='toc'):
            t.decompose()
    for t in soup.find_all('img'):
        t.decompose()

    wrap = soup.find('div', class_='wrap') or soup.body or soup
    convert_math_in_tree(wrap)

    # --- section heading (H1) ---
    h1 = wrap.find('h1')
    title_text = text_of(h1) if h1 else heading
    hd = new_tag(out_soup, 'h1')
    hd.string = heading or title_text
    out_root.append(hd)

    masthead = wrap.find('header', class_='masthead')
    if masthead:
        kicker = masthead.find(class_='kicker')
        if kicker:
            p = para(out_soup, S_LABEL)
            p.string = text_of(kicker)
            out_root.append(p)
        if h1 and heading and text_of(h1).lower() != heading.lower():
            p = para(out_soup, "font-weight:bold;font-size:13pt;")
            p.string = text_of(h1)
            out_root.append(p)
        stand = masthead.find(class_='standfirst')
        if stand:
            p = para(out_soup, S_STAND)
            p.string = text_of(stand)
            out_root.append(p)
        mg = masthead.find(class_='meta-grid')
        if mg:
            for row in mg.find_all('div', recursive=False):
                p = para(out_soup)
                p.append(NavigableString(text_of(row)))
                out_root.append(p)
        masthead.decompose()

    emit_children(wrap, out_soup, out_root)


def emit_children(container, out_soup, out_root):
    for node in list(container.children):
        emit_node(node, out_soup, out_root)


def emit_node(node, out_soup, out_root):
    if isinstance(node, NavigableString):
        if type(node) is not NavigableString:      # Comment, Doctype, CData...
            return
        s = str(node).strip()
        if s:
            p = para(out_soup)
            p.string = s
            out_root.append(p)
        return
    if not isinstance(node, Tag):
        return

    name = node.name
    cls = node.get('class') or []

    if name in ('script', 'style', 'link', 'meta', 'header', 'button'):
        return

    # containers we descend into
    if name in ('div', 'section', 'article', 'main', 'nav') and not (
            set(cls) & {'formula', 'callout', 'example', 'worked', 'plain-eng',
                        'gate', 'warn', 'legend', 'build-bar', 'tree', 'task',
                        'row', 'meta-grid', 'phase', 'sig-block', 'cover-model',
                        'jury', 'sig-box', 'phase-head', 'big', 'med', 'stars',
                        'part-label', 'kicker', 'title-line', 'ident', 'bar',
                        'component', 'cnum', 'ctitle', 'pid', 'small'}):
        emit_children(node, out_soup, out_root)
        return

    if 'part-label' in cls or 'kicker' in cls:
        p = para(out_soup, S_LABEL)
        p.string = text_of(node).upper()
        out_root.append(p)
        return

    if 'formula' in cls:
        p = para(out_soup, S_FORMULA)
        p.string = text_of(node)
        out_root.append(p)
        return

    if 'example' in cls or 'tree' in cls and node.find('ul') is None:
        out_root.append(build_pre(out_soup, node))
        return

    if 'tree' in cls:
        for ul in node.find_all('ul', recursive=False):
            out_root.append(clean_list(ul, out_soup))
        return

    if set(cls) & {'callout', 'worked', 'plain-eng', 'gate', 'warn', 'build-bar',
                   'legend', 'phase-head', 'component'}:
        out_root.append(build_boxed(out_soup, node))
        return

    if 'task' in cls:
        p = para(out_soup, "margin-left:18pt;")
        code = node.find(class_='tcode')
        title = node.find(class_='ttitle')
        deliver = node.find(class_='deliver')
        bits = []
        if code:
            b = out_soup.new_tag('b'); b['style'] = S_TAG; b.string = text_of(code)
            p.append(b); p.append(NavigableString('  '))
        if title:
            p.append(NavigableString(text_of(title)))
        if deliver:
            i = out_soup.new_tag('i'); i.string = '  — ' + text_of(deliver)
            p.append(i)
        if not (code or title or deliver):
            p.append(NavigableString(text_of(node)))
        out_root.append(p)
        return

    if 'row' in cls or 'meta-grid' in cls:
        lbl = node.find(class_='lbl')
        val = node.find(class_='val')
        if lbl is not None:
            p = para(out_soup)
            b = out_soup.new_tag('b'); b.string = text_of(lbl) + ': '
            p.append(b)
            p.append(NavigableString(text_of(val) if val else ''))
            out_root.append(p)
        else:
            for sub in node.find_all('div', recursive=False):
                p = para(out_soup)
                p.append(NavigableString(text_of(sub)))
                out_root.append(p)
        return

    if set(cls) & {'phase', 'sig-block', 'cover-model', 'jury', 'sig-box',
                   'ident', 'title-line', 'small', 'big', 'med', 'stars', 'bar',
                   'cnum', 'ctitle', 'pid'}:
        txt = text_of(node)
        if node.find(['p', 'ul', 'ol', 'table', 'h3', 'div']):
            emit_children(node, out_soup, out_root)
        elif txt:
            p = para(out_soup)
            p.string = txt
            out_root.append(p)
        return

    if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
        level = {'h1': 'h2', 'h2': 'h2', 'h3': 'h3', 'h4': 'h4',
                 'h5': 'h5', 'h6': 'h6'}[name]
        h = new_tag(out_soup, level)
        h.string = text_of(node)
        out_root.append(h)
        return

    if name == 'p':
        style = None
        if set(cls) & {'standfirst', 'lead', 'csum', 'sum', 'phase-note'}:
            style = S_STAND
        p = para(out_soup, style)
        move_inline(node, p, out_soup)
        if text_of(p):
            out_root.append(p)
        return

    if name in ('ul', 'ol'):
        if any(is_rich_li(li) for li in node.find_all('li', recursive=False)):
            emit_rich_list(node, out_soup, out_root)
        else:
            out_root.append(clean_list(node, out_soup))
        return

    if name == 'table':
        node.attrs = {}
        out_root.append(style_table(out_soup, node))
        return

    if name == 'blockquote':
        bq = out_soup.new_tag('blockquote')
        bq['style'] = "margin:6pt 0 6pt 18pt;"
        emit_children(node, out_soup, bq)
        out_root.append(bq)
        return

    if name == 'hr':
        out_root.append(out_soup.new_tag('hr'))
        return

    if name in ('pre', 'code') and name == 'pre':
        out_root.append(build_pre(out_soup, node))
        return

    if name in ('span', 'a', 'em', 'strong', 'b', 'i', 'code', 'small'):
        txt = text_of(node)
        if txt:
            p = para(out_soup)
            move_inline_single(node, p, out_soup)
            out_root.append(p)
        return

    # fallback: descend
    emit_children(node, out_soup, out_root)


INLINE_KEEP = {'a', 'em', 'i', 'strong', 'b', 'sup', 'sub', 'code', 'br', 'u'}


def move_inline_single(node, target, out_soup):
    tmp = out_soup.new_tag('span')
    tmp.append(node)
    move_inline(tmp, target, out_soup)


def move_inline(src, target, out_soup):
    """Copy inline content, preserving links/emphasis, flattening spans/divs."""
    for child in list(src.children):
        if isinstance(child, NavigableString):
            target.append(NavigableString(str(child)))
        elif isinstance(child, Tag):
            if child.name == 'br':
                target.append(out_soup.new_tag('br'))
            elif child.name == 'a' and child.get('href'):
                a = out_soup.new_tag('a', href=child['href'])
                a.string = text_of(child) or child['href']
                target.append(a)
            elif child.name in INLINE_KEEP:
                t = out_soup.new_tag('code' if child.name == 'code' else child.name)
                if child.name == 'code':
                    t['style'] = S_MONO
                move_inline(child, t, out_soup)
                target.append(t)
            else:
                move_inline(child, target, out_soup)


LI_BLOCKS = ('table', 'div', 'p', 'pre', 'blockquote')


def is_rich_li(li):
    """A list item carrying block content (formula, legend table, callout)."""
    return any(isinstance(c, Tag) and c.name in LI_BLOCKS for c in li.children)


def emit_rich_list(node, out_soup, out_root):
    """Lists whose items hold formulas/tables can't stay real lists in a Doc.
    Render each item as a bulleted paragraph with its blocks indented beneath."""
    ordered = node.name == 'ol'
    for n, li in enumerate(node.find_all('li', recursive=False), 1):
        blocks = [c for c in li.children
                  if isinstance(c, Tag) and c.name in LI_BLOCKS]
        lead = para(out_soup, "margin-left:18pt;")
        lead.append(NavigableString(f'{n}. ' if ordered else '• '))
        tmp = out_soup.new_tag('span')
        for c in list(li.children):
            if isinstance(c, Tag) and c in blocks:
                continue
            tmp.append(c.extract())
        move_inline(tmp, lead, out_soup)
        if text_of(lead):
            out_root.append(lead)
        if blocks:
            holder = out_soup.new_tag('blockquote')
            holder['style'] = "margin:4pt 0 8pt 30pt;"
            for b in blocks:
                emit_node(b, out_soup, holder)
            out_root.append(holder)


def clean_list(node, out_soup):
    lst = out_soup.new_tag(node.name)
    for li in node.find_all('li', recursive=False):
        new_li = out_soup.new_tag('li')
        nested = []
        for sub in li.find_all(['ul', 'ol'], recursive=False):
            nested.append(sub.extract())
        move_inline(li, new_li, out_soup)
        for n in nested:
            new_li.append(clean_list(n, out_soup))
        lst.append(new_li)
    return lst


# ---------------------------------------------------------------- document plan
PARTS = [
    ('FRONT MATTER', [
        ('front-matter/teny-fisaorana.html', 'Teny Fisaorana'),
        ('front-matter/remerciements.html', 'Remerciements'),
        ('front-matter/abbreviations.html', 'List of Abbreviations and Notations'),
        ('front-matter/figures-tables.html', 'List of Figures and Tables'),
    ]),
    ('BODY', [
        ('chapters/00-introduction-generale.html',
         'General Introduction and Position of the Problem'),
        ('chapters/01-sota-foundations.html',
         'Chapter I — Foundations of Speech Recognition'),
        ('chapters/02-sota-asr.html',
         'Chapter II — Low-Resource and Multilingual ASR'),
        ('chapters/03-methodology.html',
         'Chapter III — The PROVA-MG Methodology'),
        ('chapters/04-results-discussion.html',
         'Chapter IV — Validation, Expected Results and Discussion'),
    ]),
    ('BACK MATTER', [
        ('back-matter/conclusion-generale.html', 'General Conclusion'),
        ('back-matter/resume.html', 'Résumé / Abstract'),
        ('back-matter/annexes.html', 'Annexes'),
        ('back-matter/references.html', 'Bibliographic References'),
        ('back-matter/fiche.html', 'Thesis Record Sheet (Fiche)'),
    ]),
    ('APPENDIX — WORKING MATERIAL', [
        ('understanding.html',
         'Appendix A — Plain-Algebra Primer to the PROVA-MG Formulas'),
        ('short/fr/new-methodology.html',
         'Appendix B — Nouvelle méthodologie (résumé en français)'),
        ('guidelines/avancement.html',
         'Appendix C — Progress Tracker and Task Checklist'),
        ('guidelines/guide-redaction.html',
         'Appendix D — Thesis Writing Guide (EDTM3D, Université de Toamasina)'),
    ]),
]


def build():
    out = BeautifulSoup(
        '<html><head><meta charset="utf-8"><title>PROVA-MG</title></head>'
        '<body></body></html>', 'lxml')
    body = out.body

    # ---- title page from index.html ----
    idx = BeautifulSoup(open(ROOT + 'index.html', encoding='utf-8').read(), 'lxml')
    mast = idx.find('header', class_='masthead')
    t = new_tag(out, 'h1')
    t.string = ('PROVA-MG: A Probabilistic Routing Framework for '
                'Low-Resource Malagasy Speech Recognition')
    body.append(t)
    if mast:
        k = mast.find(class_='kicker')
        if k:
            p = para(out, S_LABEL); p.string = text_of(k).upper(); body.append(p)
        st = mast.find(class_='standfirst')
        if st:
            p = para(out, S_STAND); p.string = text_of(st); body.append(p)
        mg = mast.find(class_='meta-grid')
        if mg:
            tbl = out.new_tag('table')
            tb = out.new_tag('tbody'); tbl.append(tb)
            for row in mg.find_all('div', recursive=False):
                span = row.find('span')
                key = row.get_text(' ', strip=True)
                val = text_of(span) if span else ''
                if span:
                    key = key.replace(val, '').strip().rstrip(':')
                tr = out.new_tag('tr')
                th = out.new_tag('th'); th.string = key
                td = out.new_tag('td'); td.string = val
                tr.append(th); tr.append(td); tb.append(tr)
            body.append(style_table(out, tbl))

    # ---- abstract from index.html ----
    for sec in idx.find_all('section'):
        lbl = sec.find(class_='part-label')
        if lbl and 'abstract' in text_of(lbl).lower():
            convert_math_in_tree(sec)
            h = new_tag(out, 'h1'); h.string = 'Abstract'; body.append(h)
            for p in sec.find_all('p'):
                style = S_STAND if 'lead' in (p.get('class') or []) else None
                np = para(out, style)
                move_inline(p, np, out)
                body.append(np)
            break

    # ---- contents at a glance (from index TOC summaries) ----
    h = new_tag(out, 'h1'); h.string = 'Contents at a Glance'; body.append(h)
    for nav in idx.find_all('nav', class_='toc'):
        h2 = new_tag(out, 'h2')
        h2.string = text_of(nav.find('h2')) if nav.find('h2') else 'Contents'
        body.append(h2)
        ol = out.new_tag('ul')
        for li in nav.find_all('li'):
            a = li.find('a')
            summ = li.find(class_='sum')
            new_li = out.new_tag('li')
            b = out.new_tag('b'); b.string = text_of(a) if a else text_of(li)
            new_li.append(b)
            if summ:
                new_li.append(NavigableString(' — ' + text_of(summ)))
            ol.append(new_li)
        body.append(ol)

    # ---- all parts ----
    for part_title, files in PARTS:
        body.append(out.new_tag('hr'))
        ph = new_tag(out, 'h1')
        ph.string = part_title
        body.append(ph)
        for path, heading in files:
            transform_page(path, heading, out, body)

    # U+2011 (non-breaking hyphen) is a web-typography artifact: it defeats
    # search and spellcheck in Docs, so fold it back to a plain hyphen.
    for t in list(out.find_all(string=True)):
        if '‑' in t:
            t.replace_with(NavigableString(str(t).replace('‑', '-')))

    # tidy: stop empty cells collapsing, drop stray empty paragraphs
    for cell in out.find_all(['td', 'th']):
        if not cell.get_text(strip=True):
            cell.string = ' '
    for p in out.find_all('p'):
        if not p.get_text(strip=True) and not p.get('style'):
            p.decompose()

    return out


if __name__ == '__main__':
    doc = build()
    dest = sys.argv[1] if len(sys.argv) > 1 else '/tmp/prova-mg.html'
    open(dest, 'w', encoding='utf-8').write(str(doc))
    print('wrote', dest, len(str(doc)), 'bytes')
