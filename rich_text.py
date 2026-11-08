"""Portable, allowlisted editorial document format; no user HTML is executed."""
from html import escape
import json
from urllib.parse import urlsplit

INLINE = {'text', 'hardBreak'}
BLOCK = {'paragraph', 'heading', 'bulletList', 'orderedList', 'blockquote', 'horizontalRule', 'codeBlock'}
MARKS = {'bold': 'strong', 'italic': 'em', 'underline': 'u', 'strike': 's', 'code': 'code'}


def validate_document(doc):
    if len(json.dumps(doc, ensure_ascii=False)) > 240000:
        raise ValueError('Documento muito grande.')
    count = 0
    def visit(node, allowed, depth=0):
        nonlocal count
        count += 1
        if depth > 16 or count > 12000 or not isinstance(node, dict):
            raise ValueError('Estrutura do texto inválida.')
        kind = node.get('type')
        if not isinstance(kind, str) or kind not in allowed or set(node) - {'type', 'content', 'text', 'marks', 'attrs'}:
            raise ValueError('Formatação não suportada.')
        attrs = node.get('attrs') or {}
        if not isinstance(attrs, dict):
            raise ValueError('Atributos inválidos.')
        accepted = {'heading': {'level'}, 'orderedList': {'start', 'type'}, 'codeBlock': {'language'}}.get(kind, set())
        if set(attrs) - accepted:
            raise ValueError('Atributo de formatação não suportado.')
        if kind == 'heading' and attrs.get('level') not in (2, 3):
            raise ValueError('Use subtítulos H2 ou H3.')
        if kind == 'orderedList' and (type(attrs.get('start', 1)) is not int or not 1 <= attrs.get('start', 1) <= 10000):
            raise ValueError('Numeração inválida.')
        if kind in {'text', 'hardBreak'}:
            if (kind == 'text' and not isinstance(node.get('text'), str)) or 'content' in node or (kind == 'hardBreak' and 'text' in node):
                raise ValueError('Texto inválido.')
            marks = node.get('marks', [])
            if not isinstance(marks, list) or len(marks) > 6:
                raise ValueError('Marcas inválidas.')
            for mark in marks:
                if not isinstance(mark, dict) or set(mark) - {'type', 'attrs'}:
                    raise ValueError('Marca inválida.')
                if not isinstance(mark.get('type'), str):
                    raise ValueError('Marca inválida.')
                if mark.get('type') == 'link':
                    a = mark.get('attrs') or {}
                    if not isinstance(a, dict) or set(a) - {'href', 'target', 'rel', 'class', 'title'}:
                        raise ValueError('Link inválido.')
                    href = a.get('href', '')
                    if not isinstance(href, str) or len(href) > 2000 or any(ord(c) < 32 for c in href):
                        raise ValueError('Link inválido.')
                    u = urlsplit(href)
                    if u.scheme not in ('https', 'http', 'mailto') or (u.scheme != 'mailto' and (not u.hostname or u.username or u.password)):
                        raise ValueError('Use links http, https ou mailto.')
                elif mark.get('type') not in MARKS or mark.get('attrs'):
                    raise ValueError('Marca não suportada.')
        elif 'text' in node or node.get('marks'):
            raise ValueError('Estrutura de texto inválida.')
        children = node.get('content', [])
        if not isinstance(children, list):
            raise ValueError('Conteúdo inválido.')
        child_allowed = INLINE if kind in {'paragraph', 'heading'} else {'text'} if kind == 'codeBlock' else {'listItem'} if kind in {'bulletList', 'orderedList'} else BLOCK if kind in {'doc', 'blockquote', 'listItem'} else set()
        for child in children:
            visit(child, child_allowed, depth + 1)
    visit(doc, {'doc'})
    if len(plain_text(doc)) > 40000:
        raise ValueError('Texto deve ter até 40000 caracteres.')
    return doc


def plain_text(node):
    kind = node['type']
    if kind == 'text':
        return node['text']
    if kind == 'hardBreak':
        return '\n'
    separator = '' if kind in {'paragraph', 'heading', 'codeBlock'} else '\n\n'
    return separator.join(plain_text(n) for n in node.get('content', []))


def from_plain(text):
    return {'type': 'doc', 'content': [{'type': 'paragraph', 'content': sum(([{'type': 'hardBreak'}] + ([{'type': 'text', 'text': line}] if line else []) for line in block.split('\n')), [])[1:]} for block in text.split('\n\n')]}


def render_document(doc):
    validate_document(doc)
    def render(node):
        kind = node['type']
        if kind == 'text':
            html = escape(node['text'])
            for mark in node.get('marks', []):
                if mark['type'] == 'link':
                    html = '<a href="'+escape(mark['attrs']['href'], quote=True)+'" rel="noopener noreferrer">'+html+'</a>'
                else:
                    tag = MARKS[mark['type']]
                    html = f'<{tag}>{html}</{tag}>'
            return html
        if kind == 'hardBreak':
            return '<br>'
        if kind == 'horizontalRule':
            return '<hr>'
        inner = ''.join(render(n) for n in node.get('content', []))
        if kind == 'doc':
            return inner
        if kind == 'codeBlock':
            return '<pre><code>'+inner+'</code></pre>'
        tag = {'paragraph': 'p', 'heading': 'h'+str(node.get('attrs', {}).get('level', 2)), 'bulletList': 'ul', 'orderedList': 'ol', 'listItem': 'li', 'blockquote': 'blockquote'}[kind]
        attr = ' start="'+str(node.get('attrs', {}).get('start', 1))+'"' if kind == 'orderedList' else ''
        return f'<{tag}{attr}>{inner}</{tag}>'
    return render(doc)
