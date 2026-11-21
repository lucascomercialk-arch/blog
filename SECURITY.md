# Segurança e Endurecimento da Publicação

Este documento descreve os controles de segurança do repositório público do blog (`lucascomercialk-arch/blog`), os resultados da auditoria realizada na issue #4, os limites do escopo avaliado e os procedimentos de resposta caso uma credencial venha a ser exposta.

## 1. Escopo, premissas e limitações

- **Repositório público:** Todo arquivo commitado ou artefato publicado no GitHub Pages é público. **Qualquer segredo commitado deve ser tratado como comprometido imediatamente**, mesmo após remoção em um commit posterior, pois permanece acessível no histórico Git, caches e eventuais forks.
- **Limites da revisão:** Esta análise cobre apenas o código do gerador estático (`build.py`, `rich_text.py`), os arquivos estáticos (`assets/`), o manifesto (`content/posts.json`), os workflows (`.github/workflows/pages.yml`), a suíte de testes (`tests/test_security.py`) e o artefato gerado em `dist/`.
- **Atlas Hub e sistemas externos:** Uma revisão deste repositório **não audita nem certifica** o Atlas Hub, suas contas, infraestrutura, permissões internas, tokens armazenados fora deste repositório ou integrações externas. Não há neste repositório API, fluxo de autenticação ou credenciais do Atlas Hub.

## 2. Resultado da auditoria de segredos e artefatos

Durante a auditoria da árvore de trabalho atual, de todo o histórico Git disponível (12 commits entre `main` e as branches `quill/template-*`), dos metadados das imagens `.webp` e do artefato `dist/`:

- Nenhum token, chave de API, senha, chave privada, URL interna/local ou dado de `cover_source` foi encontrado nos arquivos rastreados, nos diffs de commit ou nos arquivos gerados em `dist/`.
- As imagens `.webp` em `assets/` contêm apenas o chunk de imagem `VP8 `, sem chunks de metadados EXIF ou XMP.
- O arquivo `build.py` rejeita explicitamente entradas com o campo privado `cover_source` caso apareça em `content/posts.json`.
- **Observação sobre logs remotos:** O histórico de logs de execuções anteriores do GitHub Actions não foi baixado nesta sessão por ausência de sessão autenticada do `gh` CLI no ambiente local; recomenda-se manter revisão periódica na aba *Actions* do repositório caso novos workflows ou secrets sejam adicionados.

## 3. Onde podem existir segredos e procedimento de revogação/rotação

Embora este repositório não armazene credenciais, o fluxo de publicação entre ferramentas externas (como Atlas Hub / Quill) e o GitHub pode utilizar segredos fora do código-fonte:

- **GitHub (Tokens / Apps / Actions):** Personal Access Tokens (PATs), tokens de instalação de GitHub App usados para abrir PRs ou publicar posts em `content/posts.json`, ou secrets/variáveis configurados em *Settings → Secrets and variables → Actions* e no ambiente `github-pages`.
- **Serviços externos (Atlas Hub / Quill / provedores de mídia):** Credenciais mantidas na infraestrutura externa responsável por gerar ou aprovar conteúdo antes do commit neste repositório.

### Procedimento de resposta a incidentes (sem expor valores)

Se houver suspeita ou confirmação de exposição de uma credencial em commits, PRs, issues ou logs:

1. **Não reproduzir o valor:** Nunca colar o segredo em issues, comentários, mensagens de commit, testes ou logs. Registrar apenas o tipo da credencial, onde apareceu e a data da mitigação.
2. **Revogar e rotacionar imediatamente:** Invalidar o token/chave no emissor (GitHub, Atlas Hub ou provedor correspondente) e gerar uma nova credencial com o menor escopo necessário.
3. **Revisar auditoria e logs:** Verificar registros de acesso, commits recentes, PRs e execuções de workflow para confirmar se houve uso indevido no intervalo de exposição.
4. **Limpar o histórico, se necessário:** Remover o dado do repositório e reescrever o histórico se aplicável, mantendo a premissa de que o valor antigo continua comprometido após revogação.

## 4. Endurecimento do GitHub Actions e configurações recomendadas

### Controles aplicados no código

- **Pin por SHA completo:** Todas as actions em `.github/workflows/pages.yml` (`actions/checkout`, `actions/setup-python`, `actions/configure-pages`, `actions/upload-pages-artifact` e `actions/deploy-pages`) estão fixadas por hash SHA de 40 caracteres com comentário indicando a versão correspondente.
- **Atualizações controladas:** O arquivo `.github/dependabot.yml` configura verificações semanais para `github-actions`, permitindo revisar atualizações mantendo o pin por SHA.
- **Menor privilégio:** O workflow declara apenas `contents: read`, `pages: write` e `id-token: write`, desativa a persistência de credenciais no checkout (`persist-credentials: false`), não injeta secrets externos no build e executa os testes automatizados antes de gerar `dist/`.

### Configurações recomendadas na interface do GitHub

Na consulta ao repositório, a branch `main` constava sem proteção ativa (`protected: false`). Recomenda-se habilitar diretamente nas configurações do repositório no GitHub:

1. **Proteção da branch `main` (Branch protection / Ruleset):**
   - Exigir pull request antes do merge ou restringir pushes diretos conforme o fluxo editorial.
   - Exigir aprovação da verificação de CI/testes antes do deploy.
   - Bloquear *force push* e exclusão da branch `main`.
   - Exigir revisão explícita (por exemplo, via `CODEOWNERS` ou ruleset) para alterações em `.github/workflows/*` e scripts do gerador.
2. **Restrições do ambiente `github-pages`:**
   - Em *Settings → Environments → github-pages*, restringir *Deployment branches and tags* para permitir deploy apenas a partir da branch `main`.

## 5. Controles do site estático e limitações do GitHub Pages

O gerador (`build.py` e `rich_text.py`) aplica validação estrita e escaping de HTML/atributos em todo conteúdo editorial e metadados, restringe links do formato *rich text* a `http`, `https` e `mailto` (sem credenciais embutidas, caracteres de controle ou espaços nas extremidades) com `rel="noopener noreferrer"`, impede travessia de caminho fora de `dist/` e bloqueia links simbólicos na saída e em `assets/`.

Todas as páginas HTML geradas incluem:

- `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self'; base-uri 'self'; form-action 'none'">`
- `<meta name="referrer" content="strict-origin-when-cross-origin">`
- `rel="noopener noreferrer"` no link externo do rodapé.

### Limitações de cabeçalhos HTTP no GitHub Pages

O GitHub Pages não permite configurar cabeçalhos HTTP arbitrários por repositório. Por isso, tags `<meta>` atuam apenas como camada adicional de defesa em profundidade e **não substituem cabeçalhos HTTP completos**:

- Diretivas como `frame-ancestors` (proteção contra clickjacking) e mecanismos de relatório (`report-to`) são ignorados em `<meta http-equiv="Content-Security-Policy">` e dependem de cabeçalho HTTP real.
- Cabeçalhos como `X-Content-Type-Options: nosniff`, `Strict-Transport-Security` e `Permissions-Policy` dependem da plataforma de hospedagem ou de um proxy/CDN intermediário caso seja necessário controle total dos cabeçalhos de resposta.

## 6. Verificação local

Para executar a suíte de testes de segurança e gerar o site estático localmente:

```bash
python -m unittest discover -s tests -v
python build.py
```

O artefato público final é gerado em `dist/` (ignorado pelo Git) e deve conter apenas páginas HTML, `publications.json`, `.nojekyll` e os arquivos estáticos de `assets/`.
