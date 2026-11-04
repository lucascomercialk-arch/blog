# Blog de Lucas Kammer

Site estático preparado para GitHub Pages, sem dependências Python adicionais.

```bash
python3 build.py
```

O resultado fica em `dist/`. Links relativos funcionam em um domínio próprio ou no caminho de um repositório do GitHub Pages. Em Settings → Pages, selecionar GitHub Actions como origem. O workflow `Publicar blog` compila e publica após um push em `main`.

O Quill altera somente `content/posts.json`, após autorização explícita para uma versão. O manifesto inicial está vazio: nenhum texto de exemplo é publicado como artigo do autor. Parágrafos e quebras de linha são preservados; HTML é exibido como texto, nunca executado. Markdown avançado ainda não é interpretado.

A paisagem foi gerada para reproduzir a direção visual aprovada. Nesta primeira entrega ela também é a única capa disponível; geração de capas por API será uma integração separada. O painel mostra a mesma imagem antes da aprovação.

Este repositório público deve conter somente o site e artigos aprovados. Não copiar o projeto Atlas, rascunhos privados, dados SQLite, credenciais ou workflows n8n para cá.
