# Publicação de versões

Roteiro dos mantenedores para publicar uma versão do Themis LGPD no PyPI e no GitHub Container
Registry (GHCR). Todo o processo roda no GitHub Actions (`.github/workflows/release.yml`), disparado
por uma tag `vX.Y.Z`; nenhum token ou chave é armazenado no repositório.

## Configuração única

Feita uma vez, por quem administra o projeto no PyPI e no GitHub.

**1. Publicador confiável no PyPI.** Em <https://pypi.org/manage/account/publishing/>, adicione um
publicador pendente (o projeto ainda não existe no PyPI) com:

| Campo | Valor |
|---|---|
| PyPI Project Name | `themis-lgpd` |
| Owner | `matheusteixeira-commits` |
| Repository name | `themis-lgpd` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

**2. Ambiente `pypi` no GitHub.** Em *Settings → Environments*, crie o ambiente `pypi`. Recomenda-se
exigir aprovação de um mantenedor (*Required reviewers*) e restringir a implantação às tags `v*`
(*Deployment branches and tags*).

**3. Pacotes do GitHub.** Na primeira publicação, a imagem `ghcr.io/matheusteixeira-commits/themis-lgpd`
é criada como privada. Em *Packages → themis-lgpd → Package settings*, torne-a pública e vincule-a ao
repositório.

## A cada versão

1. Atualize `src/themis_lgpd/_versao.py` (fonte única da versão; o `pyproject.toml` a lê dali) — por
   exemplo, de `1.1.0.dev0` para `1.1.0`.
2. Em `CHANGELOG.md`, troque "Não publicado" por `1.1.0 — AAAA-MM-DD`.
3. Atualize `docs/openapi.json` (`python scripts/gerar_openapi.py`), que registra a versão.
4. Abra um pull request: o workflow de publicação roda como ensaio (pacote, `twine check`, SBOM e
   construção da imagem, sem publicar). Depois de aprovado e integrado, crie a tag:

   ```bash
   git tag -a v1.1.0 -m "Themis LGPD 1.1.0"
   git push origin v1.1.0
   ```

5. O workflow confere que a tag corresponde à versão do pacote e então: constrói a roda e o sdist,
   gera o SBOM CycloneDX, emite os atestados de proveniência, publica no PyPI (após a aprovação no
   ambiente `pypi`), publica a imagem no GHCR, assina-a com cosign e emite o atestado da imagem. O
   workflow do pacote portátil para Windows gera o `.zip` como artefato da mesma tag.
6. Crie a release no GitHub a partir da tag, com o trecho do CHANGELOG, e anexe o SBOM
   (`themis-lgpd.cdx.json`, artefato `dist`) e o pacote portátil para Windows.
7. Volte a versão de desenvolvimento para a próxima (`1.2.0.dev0`).

## Verificação pelos usuários

Os comandos de verificação da assinatura e da proveniência da imagem e dos pacotes estão em
[INSTALACAO.md](INSTALACAO.md#imagem-publicada-e-verificação-de-autenticidade).
