"""Interface web do Themis LGPD (Streamlit).

O fluxo de texto tem três etapas — analisar, revisar e gerar — e a revisão humana acontece antes da
exportação: cada achado pode ser desmarcado e trechos adicionais podem ser tarjados. No fluxo de
arquivo, o resultado é gerado de imediato e pode ser refeito após a revisão.

Garantias de privacidade da interface:

* o conteúdo existe apenas na memória da sessão e é descartado ao final dela; nada é gravado em
  disco nem registrado em log;
* todo texto vindo de documentos é exibido com HTML escapado (ver :mod:`themis_lgpd.ui.realce`);
* mensagens de erro nunca exibem detalhes da exceção, que poderiam conter trechos do documento;
* no modo de demonstração, o relatório interno com valores originais não é oferecido.

A interface deve ser iniciada por ``themis interface``, que aplica as opções seguras do Streamlit
(ver :data:`themis_lgpd.cli.STREAMLIT_SEGURO`).
"""

from __future__ import annotations

import hashlib
import time

import streamlit as st

from themis_lgpd import __version__, relatorio
from themis_lgpd.config import carregar
from themis_lgpd.formatos import ArquivoInvalido, FalhaOCR, VazamentoDetectado, anonimizar_arquivo
from themis_lgpd.motor import Anonimizador
from themis_lgpd.operadores import MODOS
from themis_lgpd.perfis import PERFIS
from themis_lgpd.ui.realce import realcar_original, realcar_saida

CFG = carregar()

#: Análises permitidas por sessão a cada hora. Na demonstração pública, o proxy reverso também limita
#: as requisições por endereço IP.
LIMITE_SESSAO = 40 if CFG.demo else 10_000

st.set_page_config(page_title="Themis LGPD", page_icon="⚖️", layout="wide", menu_items={})

st.markdown(
    "<style>header [data-testid='stToolbar']{display:none} .block-container{padding-top:1.6rem}</style>",
    unsafe_allow_html=True,  # CSS fixo, sem nenhum conteúdo do usuário
)


def _cota() -> bool:
    """Registra uma análise e informa se a sessão ainda está dentro do limite horário."""
    agora = time.time()
    historico = [t for t in st.session_state.get("_usos", []) if agora - t < 3600]
    if len(historico) >= LIMITE_SESSAO:
        st.error("Limite de uso desta sessão atingido. Tente novamente mais tarde.")
        return False
    st.session_state["_usos"] = historico + [agora]
    return True


def _linhas(texto: str) -> list[str]:
    """Itens não vazios de uma lista digitada um por linha (no máximo 200)."""
    return [t.strip() for t in (texto or "").splitlines() if t.strip()][:200]


# ------------------------------------------------------------------ barra lateral
with st.sidebar:
    st.markdown(f"### Themis LGPD\n<small>v{__version__} · código aberto (MIT)</small>", unsafe_allow_html=True)
    perfil = st.selectbox("Perfil", list(PERFIS), format_func=lambda p: PERFIS[p].titulo,
                          help="Define o que é tarjado e o que vira alerta para revisão.")
    st.caption(PERFIS[perfil].descricao)
    # Na demonstração pública, o modo HMAC usaria uma chave do servidor compartilhada entre usuários.
    modos = [m for m in MODOS if not (CFG.demo and m == "hmac")]
    modo = st.selectbox("Como substituir", modos, help="\n\n".join(f"**{k}**: {v}" for k, v in MODOS.items()))
    preservar = st.checkbox("Manter nomes de agentes públicos em exercício da função",
                            help="Ex.: 'Secretária de Estado de Saúde, Fulana'. Valide com a área jurídica.")
    with st.expander("Listas de permissão e bloqueio"):
        permitir = _linhas(st.text_area("Nunca tarjar (um por linha)", height=90,
                                        placeholder="Hospital Regional de Taguatinga"))
        bloquear = _linhas(st.text_area("Sempre tarjar (um por linha)", height=90, placeholder="Projeto Sigilo X"))
    st.divider()
    st.caption("O conteúdo é processado em memória e descartado ao fim da sessão. Nada é gravado, "
               "registrado em log ou enviado a terceiros.")
    st.caption("A ferramenta apoia, mas não substitui, a revisão humana do documento antes da publicação.")

if CFG.demo:
    st.warning("**Demonstração pública.** Não envie documentos reais com dados pessoais: para uso real, "
               "instale o Themis LGPD na sua máquina ou servidor (é gratuito e funciona sem internet).", icon="⚠️")

st.title("Anonimização de documentos públicos")
st.caption("Tarja nomes, CPF, CNPJ, RG, CNH, PIS, título de eleitor, Cartão SUS, contatos, endereços, dados "
           "bancários, processos e dados sensíveis (LGPD art. 5º, II) — com relatório de fundamentação (LAI art. 31).")


def _anonimizador(extra_bloquear: list[str] | None = None, extra_permitir: list[str] | None = None) -> Anonimizador:
    """Anonimizador com as opções da barra lateral e as decisões da revisão."""
    return Anonimizador(perfil, modo, permitir=permitir + (extra_permitir or []),
                        bloquear=bloquear + (extra_bloquear or []), preservar_agentes_publicos=preservar,
                        usar_ner=CFG.usar_ner, modelo_spacy=CFG.modelo_spacy)


def _downloads_relatorio(resultados, nome: str, chave: str) -> None:
    """Botões de download dos relatórios publicáveis e, fora da demonstração, do relatório interno."""
    c1, c2, c3 = st.columns(3)
    c1.download_button("Relatório de tarjamento (XLSX)", relatorio.para_xlsx(resultados),
                       f"{nome}_relatorio_tarjamento.xlsx", key=f"rx{chave}", width="stretch")
    c2.download_button("Relatório (JSON)", relatorio.para_json(resultados), f"{nome}_relatorio_tarjamento.json",
                       mime="application/json", key=f"rj{chave}", width="stretch")
    c3.download_button("Nota de tarjamento (TXT)", relatorio.nota_de_tarjamento(resultados, nome),
                       f"{nome}_nota_de_tarjamento.txt", key=f"rn{chave}", width="stretch")
    st.caption("Os relatórios acima **não** contêm os dados originais e podem acompanhar a resposta ao pedido.")
    if not CFG.demo:
        with st.expander("Relatório interno com os valores originais"):
            st.error("Este arquivo CONTÉM DADOS PESSOAIS. Use apenas internamente; não publique.")
            if st.checkbox("Entendo e quero gerar", key=f"ci{chave}"):
                st.download_button("Baixar relatório interno (CSV)", relatorio.para_csv(resultados, True),
                                   f"{nome}_auditoria_INTERNO.csv", key=f"rv{chave}")


aba_texto, aba_arquivo = st.tabs(["Texto", "Arquivo (PDF, DOCX, XLSX, CSV, TXT, imagem)"])

# ------------------------------------------------------------------ texto
with aba_texto:
    texto = st.text_area("Cole o texto", height=220, max_chars=CFG.max_caracteres, key="texto",
                         placeholder="Ex.: Eu, Maria Aparecida Souza, CPF 529.982.247-25, moradora da QNM 12 "
                                     "Conjunto B Casa 4, solicito cópia do processo 00410.002123/2024-11…")
    # A análise e o resultado guardados na sessão só valem para o mesmo texto e as mesmas opções.
    assinatura = hashlib.sha256(f"{texto}|{perfil}|{modo}|{preservar}|{permitir}|{bloquear}".encode()).hexdigest()
    if st.button("1 · Analisar", type="primary", disabled=not texto.strip()) and _cota():
        with st.spinner("Analisando…"):
            st.session_state["analise"] = (assinatura, _anonimizador().analisar(texto))
    analise = st.session_state.get("analise")
    if analise and analise[0] == assinatura:
        entidades = analise[1]
        st.subheader("2 · Revise")
        st.html(realcar_original(texto, entidades))
        st.caption("🟥 será tarjado · 🟨 alerta para revisão (não tarjado) · passe o mouse para ver a base legal")
        if entidades:
            import pandas as pd

            tabela = pd.DataFrame([{"Tarjar": e.acao == "tarjar", "Tipo": e.rotulo, "Trecho": e.valor[:80],
                                    "Motivo / base legal": e.motivo or e.base_legal, "Confiança": f"{e.score:.0%}"}
                                   for e in entidades])
            editada = st.data_editor(tabela, hide_index=True, width="stretch",
                                     disabled=["Tipo", "Trecho", "Motivo / base legal", "Confiança"], key="editor")
            for e, marcar in zip(entidades, editada["Tarjar"]):
                if e.acao != "manter":
                    e.acao = "tarjar" if marcar else "alertar"
        manuais = _linhas(st.text_area("Tarjar também (um trecho por linha)", height=70, key="manuais"))
        if st.button("3 · Gerar versão anonimizada", type="primary"):
            anon = _anonimizador(extra_bloquear=manuais)
            ents = entidades
            if manuais:
                # Nova análise para incluir os trechos manuais, preservando as decisões da revisão.
                decisoes = {(e.inicio, e.fim, e.tipo): e.acao for e in entidades}
                ents = anon.analisar(texto)
                for e in ents:
                    e.acao = decisoes.get((e.inicio, e.fim, e.tipo), e.acao)
            st.session_state["saida"] = (assinatura, anon.anonimizar(texto, ents))
        saida = st.session_state.get("saida")
        if saida and saida[0] == assinatura:
            r = saida[1]
            st.subheader("Resultado")
            st.html(realcar_saida(r))
            for aviso in r.avisos:
                st.info(aviso)
            st.download_button("Baixar texto anonimizado (TXT)", r.texto.encode("utf-8"), "texto_anonimizado.txt",
                               type="primary")
            _downloads_relatorio([r], "texto", "t")

# ------------------------------------------------------------------ arquivo
with aba_arquivo:
    enviado = st.file_uploader("Envie o arquivo", type=["pdf", "docx", "xlsx", "csv", "txt", "png", "jpg", "jpeg"],
                               help=f"Até {CFG.max_mb} MB" + (f" e {CFG.max_paginas} páginas" if CFG.max_paginas else ""))
    if enviado is not None:
        dados = enviado.getvalue()
        # Trechos que o revisor desmarcou; entram na lista de permissão da próxima execução.
        nao_tarjar = st.session_state.setdefault("nao_tarjar", [])
        if st.button("Anonimizar arquivo", type="primary") and _cota():
            with st.spinner("Processando (PDFs digitalizados passam por OCR e podem demorar)…"):
                try:
                    res = anonimizar_arquivo(dados, enviado.name, _anonimizador(extra_permitir=nao_tarjar),
                                             limite_bytes=CFG.max_mb * 1024 * 1024, limite_paginas=CFG.max_paginas)
                    st.session_state["arquivo"] = (enviado.name, len(dados), res)
                except (ArquivoInvalido, VazamentoDetectado, FalhaOCR) as erro:
                    st.error(str(erro))
                except Exception:  # noqa: BLE001 - os detalhes da exceção podem conter trechos do documento
                    st.error("Não foi possível processar o arquivo.")
        guardado = st.session_state.get("arquivo")
        if guardado and guardado[:2] == (enviado.name, len(dados)):
            res = guardado[2]
            tarjadas = [e for r in res.resultados for e in r.tarjadas]
            alertas = [e for r in res.resultados for e in r.alertas]
            c1, c2 = st.columns(2)
            c1.metric("Trechos tarjados", len(tarjadas))
            c2.metric("Alertas para revisão", len(alertas))
            for aviso in res.avisos:
                st.info(aviso)
            if res.formato == "pdf":
                import pypdfium2 as pdfium

                doc = pdfium.PdfDocument(res.dados)
                st.image(doc[0].render(scale=1.3).to_pil(), caption="Pré-visualização da 1ª página anonimizada")
                doc.close()
            elif res.formato == "png":
                st.image(res.dados, caption="Imagem anonimizada")
            st.download_button(f"Baixar {res.nome}", res.dados, res.nome, mime=res.mime, type="primary")
            if tarjadas or alertas:
                import pandas as pd

                st.markdown("**Revisão** — desmarque o que *não* deve ser tarjado e clique em *Anonimizar arquivo* "
                            "de novo; para tarjar algo a mais, use a lista *Sempre tarjar* na barra lateral.")
                vistos, linhas_tab = set(), []
                for e in tarjadas + alertas:
                    if (e.valor, e.tipo) not in vistos:
                        vistos.add((e.valor, e.tipo))
                        linhas_tab.append({"Tarjar": e.acao == "tarjar", "Tipo": e.rotulo, "Trecho": e.valor[:80],
                                           "Motivo / base legal": e.motivo or e.base_legal})
                tab = st.data_editor(pd.DataFrame(linhas_tab), hide_index=True, width="stretch",
                                     disabled=["Tipo", "Trecho", "Motivo / base legal"], key="editor_arquivo")
                st.session_state["nao_tarjar"] = [linha["Trecho"] for linha, marcado in
                                                  zip(linhas_tab, tab["Tarjar"]) if linha["Tarjar"] and not marcado]
            _downloads_relatorio(res.resultados, res.nome.rsplit(".", 1)[0], "a")

st.divider()
st.caption("Themis LGPD · software livre (MIT) · processamento local · "
           "[código-fonte](https://github.com/matheusteixeira-commits/themis-lgpd)")
