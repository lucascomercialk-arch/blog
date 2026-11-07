"""Build a portable static blog from approved posts; no runtime or third-party dependencies."""
from datetime import datetime
import hashlib
from html import escape
import json
import os
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parent


def page(title, body, prefix='', description='Tecnologia, inteligência artificial e o que aprendo pelo caminho.'):
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{escape(description,quote=True)}"><title>{escape(title)} · Lucas Kammer</title><link rel="icon" href="{prefix}assets/favicon.svg"><link rel="stylesheet" href="{prefix}assets/style.css"><script src="{prefix}assets/site.js" defer></script></head><body><a class="skip" href="#conteudo">Ir para o conteúdo</a><header class="header"><a class="wordmark" href="{prefix}index.html">lucas kammer <span>✦</span></a><nav aria-label="Principal"><a href="{prefix}index.html#textos">Textos</a><a href="{prefix}projetos.html">Projetos</a><a href="{prefix}sobre.html">Sobre</a><a class="search-link" href="{prefix}index.html#busca" aria-label="Buscar textos">⌕</a></nav></header><main id="conteudo">{body}</main><footer><span>Um espaço pessoal para ideias que merecem sair da cabeça.</span><a href="https://github.com/lucascomercialk-arch" target="_blank" rel="noreferrer">GitHub ↗</a></footer></body></html>'''


def paragraphs(text):
    # Plain editorial text: HTML and scripts are always escaped.
    return '\n'.join('<p>'+escape(part).replace('\n','<br>')+'</p>' for part in re.split(r'\n\s*\n',text) if part.strip())


def validate_project(project):
    if (not isinstance(project, dict) or set(project) != {'id','name','description'}
            or not isinstance(project['id'], str) or not re.fullmatch(r'[a-f0-9]{12}', project['id'])
            or not isinstance(project['name'], str) or not 2 <= len(project['name'].strip()) <= 100
            or not isinstance(project['description'], str) or len(project['description']) > 500):
        raise ValueError('Projeto inválido.')


def project_tag(content, prefix='', navigation=True):
    project = content.get('project')
    if not project:
        return ''
    validate_project(project)
    label = 'Projeto · '+escape(project['name'])
    if not navigation:
        return '<span class="project-tag">'+label+'</span>'
    return f'<a class="project-tag" href="{prefix}projetos/{project["id"]}.html">{label} ↗</a>'


def post_card(post, prefix=''):
    minutes = max(1, (len(post['body'].split())+199)//200)
    href = prefix+'textos/'+post['id']+'.html'
    project = post.get('project', {})
    searchable = escape(post['title']+' '+post['body']+' '+post['category']+' '+project.get('name',''), quote=True)
    return (f'<article class="post-card" data-category="{escape(post["category"],quote=True)}" data-search="{searchable}">'
            f'<a href="{href}" class="post-link"><img src="{prefix+cover_path(post)}" alt="" loading="lazy" width="900" height="480">'
            f'<span class="eyebrow">{escape(post["category"])}</span><h3>{escape(post["title"])}</h3>'
            f'<p>{minutes} min de leitura</p></a>{project_tag(post,prefix)}</article>')


def article_body(content, cover_src, stamp, navigation=True):
    minutes = max(1, (len(content['body'].split())+199)//200)
    back = '<a class="back" href="../index.html#textos">← Todos os textos</a>' if navigation else ''
    end = '<div class="article-end">Obrigado pela leitura.<br><a href="../index.html#textos">Explorar outros textos ↗</a></div>' if navigation else ''
    credit = '<figcaption>'+escape(content.get('cover_credit', ''))+'</figcaption>' if content.get('cover_credit') else ''
    alt = content.get('cover_alt', 'Paisagem de montanhas e um jardim ao entardecer')
    return (f'<article class="article">{back}<header><span class="eyebrow">{escape(content["category"])}</span>'
            f'<h1>{escape(content["title"])}</h1>{project_tag(content,"../",navigation)}<p class="byline">Lucas Kammer · {escape(stamp)} · {minutes} min de leitura</p></header>'
            f'<img class="article-cover" src="{escape(cover_src, quote=True)}" alt="{escape(alt, quote=True)}">{credit}'
            f'<div class="prose">{paragraphs(content["body"])}</div>{end}</article>')


def cover_path(post):
    cover = post['cover']
    if cover == 'paisagem':
        return 'assets/paisagem.webp'
    if not re.fullmatch(r'[a-f0-9]{64}', cover):
        raise ValueError('Capa inválida.')
    return 'assets/covers/'+cover+'.webp'


def build(root=ROOT):
    manifest=json.loads((root/'content/posts.json').read_text())
    if manifest.get('schema_version') != 1 or not isinstance(manifest.get('posts'),list):
        raise ValueError('Manifesto de artigos inválido.')
    posts=manifest['posts']; ids=set(); projects={}
    cover_sha=hashlib.sha256((root/'assets/paisagem.webp').read_bytes()).hexdigest()
    for post in posts:
        if not re.fullmatch(r'[a-f0-9]{12}',post.get('id','')) or post['id'] in ids:
            raise ValueError('Identificador inválido ou repetido.')
        ids.add(post['id'])
        if post.get('category') not in ('Inteligência artificial','Tecnologia','Projetos','Reflexões') or not re.fullmatch(r'(paisagem|[a-f0-9]{64})', post.get('cover','')):
            raise ValueError('Categoria ou capa inválida.')
        if not isinstance(post.get('body'),str) or not 10<=len(post['body'])<=40000 or not 3<=len(post.get('title',''))<=160:
            raise ValueError('Texto inválido.')
        datetime.fromisoformat(post['published_at'])
        expected_cover = cover_sha if post['cover']=='paisagem' else hashlib.sha256((root/cover_path(post)).read_bytes()).hexdigest()
        if post.get('cover_sha256') != expected_cover or (post['cover']!='paisagem' and post['cover']!=expected_cover):
            raise ValueError('A capa mudou depois da aprovação.')
        if 'cover_source' in post:
            raise ValueError('Origem privada não pode ser exportada.')
        approved={k:post[k] for k in ('title','body','category','cover','cover_sha256')}
        for key in ('cover_alt','cover_credit'):
            if key in post:
                if not isinstance(post[key],str) or len(post[key])>(300 if key=='cover_alt' else 200):
                    raise ValueError('Metadados de capa inválidos.')
                approved[key]=post[key]
        if 'project' in post:
            project=post['project']
            validate_project(project)
            if project['id'] in projects and projects[project['id']] != project:
                raise ValueError('Dados divergentes para o mesmo projeto.')
            projects[project['id']]=project
            approved['project']=project
        if 'approval_digest' in post and (not re.fullmatch(r'[a-f0-9]{64}',post['approval_digest']) or not post.get('cover_alt','').strip()):
            raise ValueError('Aprovação ou descrição de capa inválida.')
        if hashlib.sha256(json.dumps(approved,ensure_ascii=False,sort_keys=True).encode()).hexdigest()!=post.get('digest'):
            raise ValueError('Conteúdo difere da versão aprovada.')
    output=root/'dist'
    if output.is_symlink():raise ValueError('Saída não pode ser link.')
    if output.exists():shutil.rmtree(output)
    (output/'textos').mkdir(parents=True)
    (output/'projetos').mkdir()
    shutil.copytree(root/'assets',output/'assets')
    cards=[]
    for post in sorted(posts,key=lambda p:p['published_at'],reverse=True):
        stamp=datetime.fromisoformat(post['published_at']).strftime('%d/%m/%Y')
        href='textos/'+post['id']+'.html'
        cards.append(post_card(post))
        article=article_body(post, '../'+cover_path(post), stamp)
        (output/href).write_text(page(post['title'],article,'../',post['body'][:150]))
    empty='<div class="empty"><span>✦</span><h3>As primeiras ideias estão tomando forma.</h3><p>Os textos aparecerão aqui conforme forem publicados.</p></div>'
    body='''<section class="hero" aria-label="Apresentação"><div class="hero-copy"><span class="eyebrow">IDEIAS EM CONSTRUÇÃO</span><h1>Pensar. Criar.<br>Compartilhar.</h1><p>Tecnologia, inteligência artificial e o que aprendo pelo caminho.</p><a class="pill" href="#textos">Explorar os textos <span>↗</span></a></div><span class="signature">Por Lucas Kammer</span></section><section id="textos" class="posts"><div class="section-heading"><h2>Últimas ideias</h2><div class="filters" aria-label="Filtrar textos">'''
    for name in ('Todos','Inteligência artificial','Tecnologia','Projetos','Reflexões'):
        body+=f'<button data-filter="{escape(name,quote=True)}" aria-pressed="{str(name=="Todos").lower()}">{escape(name)}</button>'
    body+='</div></div><label class="search" id="busca"><span>Buscar nos textos</span><input type="search" placeholder="Um assunto, uma ideia…" aria-label="Buscar nos textos"></label><div class="post-grid">'+(''.join(cards) if cards else empty)+'</div><p id="no-results" hidden>Nenhum texto encontrado. Experimente outro assunto.</p></section>'
    (output/'index.html').write_text(page('Ideias em construção',body))
    about='''<section class="about"><span class="eyebrow">SOBRE ESTE ESPAÇO</span><h1>Ideias que merecem<br>sair da cabeça.</h1><div class="prose"><p>Sou Lucas Kammer, estudante de Engenharia de Software. Este blog é um espaço para compartilhar ideias, experiências e o que vou aprendendo pelo caminho.</p><p>Inteligência artificial, tecnologia e projetos despertam minha curiosidade. Mas também quero deixar espaço para perguntas e reflexões que surgem fora da tela.</p><p>A proposta é simples: escrever com a minha voz e abrir espaço para uma boa conversa.</p></div><a class="pill dark" href="index.html#textos">Explorar os textos ↗</a></section>'''
    (output/'sobre.html').write_text(page('Sobre',about))
    project_cards=[]
    for project in sorted(projects.values(), key=lambda p:p['name'].casefold()):
        members=sorted((p for p in posts if p.get('project',{}).get('id')==project['id']),
                       key=lambda p:(datetime.fromisoformat(p['published_at']).timestamp(),p['id']))
        title=escape(project['name']); description=escape(project['description'])
        count=f"{len(members)} texto"+('s' if len(members)!=1 else '')
        project_cards.append(f'<a class="project-folder" href="projetos/{project["id"]}.html"><span class="eyebrow">PROJETO</span><h2>{title}</h2><p>{description}</p><span>{count} · Explorar ↗</span></a>')
        detail=(f'<section class="posts project-detail"><a class="back" href="../projetos.html">← Todos os projetos</a>'
                f'<header class="project-heading"><span class="eyebrow">PROJETO</span><h1>{title}</h1><p>{description}</p>'
                f'<small>{count} · Do primeiro relato ao mais recente</small></header><div class="post-grid">'
                +''.join(post_card(p,'../') for p in members)+'</div></section>')
        (output/'projetos'/f'{project["id"]}.html').write_text(page(project['name'],detail,'../',project['description'] or project['name']))
    project_intro='<section class="posts"><header class="project-heading"><span class="eyebrow">PERCURSOS EM CONSTRUÇÃO</span><h1>Projetos</h1><p>Experiências contadas em capítulos. Os mesmos textos do blog, reunidos pelo que têm em comum.</p></header>'
    project_empty='<div class="empty"><h3>Os próximos projetos começam aqui.</h3><p>As coleções aparecerão com o primeiro texto publicado.</p><a href="index.html#textos">Enquanto isso, explore os textos ↗</a></div>'
    (output/'projetos.html').write_text(page('Projetos',project_intro+('<div class="project-grid">'+''.join(project_cards)+'</div>' if project_cards else project_empty)+'</section>'))
    (output/'404.html').write_text(page('Página não encontrada','<section class="about"><h1>Esse caminho ainda não existe.</h1><p>Volte à página inicial para encontrar os textos.</p></section>'))
    (output/'publications.json').write_text(json.dumps({'schema_version':1, 'commit':os.environ.get('GITHUB_SHA',''), 'posts':[{'id':p['id'],'version':p['version'],'approval_digest':p.get('approval_digest',p['digest'])} for p in posts]}))
    (output/'.nojekyll').touch()
    return output


if __name__=='__main__':print('Blog estático gerado em '+str(build()))
