"""Build a portable static blog from approved posts; no runtime or third-party dependencies."""
from datetime import datetime
import hashlib
from html import escape
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent


def page(title, body, prefix='', description='Tecnologia, inteligência artificial e o que aprendo pelo caminho.'):
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{escape(description,quote=True)}"><title>{escape(title)} · Lucas Kammer</title><link rel="icon" href="{prefix}assets/favicon.svg"><link rel="stylesheet" href="{prefix}assets/style.css"><script src="{prefix}assets/site.js" defer></script></head><body><a class="skip" href="#conteudo">Ir para o conteúdo</a><header class="header"><a class="wordmark" href="{prefix}index.html">lucas kammer <span>✦</span></a><nav aria-label="Principal"><a href="{prefix}index.html#textos">Textos</a><a href="{prefix}index.html?categoria=Projetos#textos">Projetos</a><a href="{prefix}sobre.html">Sobre</a><a class="search-link" href="{prefix}index.html#busca" aria-label="Buscar textos">⌕</a></nav></header><main id="conteudo">{body}</main><footer><span>Um espaço pessoal para ideias que merecem sair da cabeça.</span><a href="https://github.com/lucascomercialk-arch" target="_blank" rel="noreferrer">GitHub ↗</a></footer></body></html>'''


def paragraphs(text):
    # Plain editorial text: HTML and scripts are always escaped.
    return '\n'.join('<p>'+escape(part).replace('\n','<br>')+'</p>' for part in re.split(r'\n\s*\n',text) if part.strip())


def build(root=ROOT):
    manifest=json.loads((root/'content/posts.json').read_text())
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('posts'),list):
        raise ValueError('Manifesto de artigos inválido.')
    posts=manifest['posts']; ids=set()
    cover_sha=hashlib.sha256((root/'assets/paisagem.webp').read_bytes()).hexdigest()
    for post in posts:
        if not re.fullmatch(r'[a-f0-9]{12}',post.get('id','')) or post['id'] in ids:
            raise ValueError('Identificador inválido ou repetido.')
        ids.add(post['id'])
        if post.get('category') not in ('Inteligência artificial','Tecnologia','Projetos','Reflexões') or post.get('cover')!='paisagem':
            raise ValueError('Categoria ou capa inválida.')
        if not isinstance(post.get('body'),str) or not 10<=len(post['body'])<=40000 or not 3<=len(post.get('title',''))<=160:
            raise ValueError('Texto inválido.')
        datetime.fromisoformat(post['published_at'])
        if post.get('cover_sha256') != cover_sha:
            raise ValueError('A capa mudou depois da aprovação.')
        approved={k:post[k] for k in ('title','body','category','cover','cover_sha256')}
        if hashlib.sha256(json.dumps(approved,ensure_ascii=False,sort_keys=True).encode()).hexdigest()!=post.get('digest'):
            raise ValueError('Conteúdo difere da versão aprovada.')
    output=root/'dist'
    if output.is_symlink():raise ValueError('Saída não pode ser link.')
    if output.exists():shutil.rmtree(output)
    (output/'textos').mkdir(parents=True)
    shutil.copytree(root/'assets',output/'assets')
    cards=[]
    for post in sorted(posts,key=lambda p:p['published_at'],reverse=True):
        minutes=max(1,(len(post['body'].split())+199)//200)
        stamp=datetime.fromisoformat(post['published_at']).strftime('%d/%m/%Y')
        href='textos/'+post['id']+'.html'
        searchable=escape(post['title']+' '+post['body']+' '+post['category'],quote=True)
        cards.append(f'''<article class="post-card" data-category="{escape(post['category'],quote=True)}" data-search="{searchable}"><a href="{href}" class="post-link"><img src="assets/paisagem.webp" alt="" loading="lazy" width="900" height="480"><span class="eyebrow">{escape(post['category'])}</span><h3>{escape(post['title'])}</h3><p>{minutes} min de leitura</p></a></article>''')
        article=f'''<article class="article"><a class="back" href="../index.html#textos">← Todos os textos</a><header><span class="eyebrow">{escape(post['category'])}</span><h1>{escape(post['title'])}</h1><p class="byline">Lucas Kammer · {stamp} · {minutes} min de leitura</p></header><img class="article-cover" src="../assets/paisagem.webp" alt="Paisagem de montanhas e um jardim ao entardecer"><div class="prose">{paragraphs(post['body'])}</div><div class="article-end">Obrigado pela leitura.<br><a href="../index.html#textos">Explorar outros textos ↗</a></div></article>'''
        (output/href).write_text(page(post['title'],article,'../',post['body'][:150]))
    empty='<div class="empty"><span>✦</span><h3>As primeiras ideias estão tomando forma.</h3><p>Os textos aparecerão aqui conforme forem publicados.</p></div>'
    body='''<section class="hero" aria-label="Apresentação"><div class="hero-copy"><span class="eyebrow">IDEIAS EM CONSTRUÇÃO</span><h1>Pensar. Criar.<br>Compartilhar.</h1><p>Tecnologia, inteligência artificial e o que aprendo pelo caminho.</p><a class="pill" href="#textos">Explorar os textos <span>↗</span></a></div><span class="signature">Por Lucas Kammer</span></section><section id="textos" class="posts"><div class="section-heading"><h2>Últimas ideias</h2><div class="filters" aria-label="Filtrar textos">'''
    for name in ('Todos','Inteligência artificial','Tecnologia','Projetos','Reflexões'):
        body+=f'<button data-filter="{escape(name,quote=True)}" aria-pressed="{str(name=="Todos").lower()}">{escape(name)}</button>'
    body+='</div></div><label class="search" id="busca"><span>Buscar nos textos</span><input type="search" placeholder="Um assunto, uma ideia…" aria-label="Buscar nos textos"></label><div class="post-grid">'+(''.join(cards) if cards else empty)+'</div><p id="no-results" hidden>Nenhum texto encontrado. Experimente outro assunto.</p></section>'
    (output/'index.html').write_text(page('Ideias em construção',body))
    about='''<section class="about"><span class="eyebrow">SOBRE ESTE ESPAÇO</span><h1>Ideias que merecem<br>sair da cabeça.</h1><div class="prose"><p>Sou Lucas Kammer, estudante de Engenharia de Software. Este blog é um espaço para compartilhar ideias, experiências e o que vou aprendendo pelo caminho.</p><p>Inteligência artificial, tecnologia e projetos despertam minha curiosidade. Mas também quero deixar espaço para perguntas e reflexões que surgem fora da tela.</p><p>A proposta é simples: escrever com a minha voz e abrir espaço para uma boa conversa.</p></div><a class="pill dark" href="index.html#textos">Explorar os textos ↗</a></section>'''
    (output/'sobre.html').write_text(page('Sobre',about))
    (output/'404.html').write_text(page('Página não encontrada','<section class="about"><h1>Esse caminho ainda não existe.</h1><p>Volte à página inicial para encontrar os textos.</p></section>'))
    (output/'.nojekyll').touch()
    return output


if __name__=='__main__':print('Blog estático gerado em '+str(build()))
