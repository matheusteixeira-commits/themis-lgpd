"""Anonimização de planilhas CSV e XLSX, célula a célula, preservando a estrutura.

**Colunas de dado pessoal.** Colunas cujo cabeçalho indica dado pessoal ("Nome", "CPF", "E-mail",
"Endereço"…) são tarjadas por inteiro: numa coluna "Nome", "Maria" sozinha não teria contexto para
ser reconhecida. As demais células — inclusive as do cabeçalho, já que nem toda planilha tem
cabeçalho — são analisadas como texto.

**Conteúdo do XLSX além das células.** São analisados e tarjados: literais de texto em fórmulas
(``="Maria Souza"``), nomes de abas (com atualização das referências nas fórmulas e gráficos),
cabeçalhos e rodapés de impressão, mensagens e listas de validação de dados, regras de formatação
condicional, critérios de filtros, nomes definidos e o texto de gráficos e desenhos. Os caches dos
gráficos — cópia dos valores originais das células — são descartados; o Excel os recalcula ao
abrir. São removidos: comentários, hiperlinks, tabelas dinâmicas (cujo cache guarda cópia dos
dados), vínculos com outras pastas de trabalho, macros e propriedades do documento.

Em ambos os formatos, o conteúdo é analisado em lote como um único documento e o arquivo gerado é
relido para confirmar que nenhum valor tarjado permanece.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable

from ..catalogo import tipo as info_tipo
from ..motor import Anonimizador, Entidade, Resultado
from ..texto import dobrar
from . import ArquivoInvalido, ResultadoArquivo, VazamentoDetectado
from . import xml_office as X
from .docx import IMAGENS
from .pacote import Pacote, gravar_xml, ler_xml
from .texto import decodificar
from .verificacao import texto_de_pacote, valores_protegidos, valores_tarjados, verificar_ausencia

# Cabeçalhos que contêm palavras de dado pessoal mas descrevem entidades públicas ou estrutura.
_EXCLUI_CABECALHO = re.compile(r"orgao|empresa|unidade|secretaria|razao social|fantasia|setor|departamento|"
                               r"municipio|cidade|uf\b|arquivo|campo|produto|servico|projeto")

#: Padrões de cabeçalho (sem acentos, minúsculas) e o tipo de dado atribuído à coluna inteira.
COLUNAS_PESSOAIS: list[tuple[str, str]] = [
    (r"\bcpf\b", "CPF"),
    (r"\brg\b|identidade", "RG"),
    (r"e-?mail|correio eletronico", "EMAIL"),
    (r"telefone|celular|\bfone\b|whats|contato", "TELEFONE"),
    (r"endereco|logradouro|residencia|domicilio", "ENDERECO"),
    (r"\bcep\b", "CEP"),
    (r"nascimento|\bdt_?nasc|\bdn\b", "DATA_NASCIMENTO"),
    (r"matricula|siape", "MATRICULA"),
    (r"\bnis\b|\bpis\b|pasep|\bnit\b", "PIS"),
    (r"titulo de eleitor|titulo eleitoral", "TITULO_ELEITOR"),
    (r"\bcns\b|cartao sus|cartao nacional de saude", "CNS"),
    (r"\bcnh\b", "CNH"),
    (r"\bplaca\b", "PLACA"),
    (r"\bnome\b|requerente|solicitante|interessad|titular|paciente|cidadao|denunciante|beneficiari|"
     r"responsavel|mae\b|pai\b|conjuge", "NOME"),
]

_LITERAL = re.compile(r'"((?:[^"]|"")*)"')
_PROIBIDOS_ABA = re.compile(r"[\[\]:*?/\\]")
_NOME_SIMPLES = re.compile(r"[A-Za-z_][\w.]*")
_CACHES_GRAFICO = frozenset({X.q("c", "strCache"), X.q("c", "numCache"), X.q("c", "multiLvlStrCache")})
_LIMITE_TITULO_ABA = 31


def tipo_da_coluna(cabecalho: str) -> str | None:
    """Tipo de dado pessoal indicado pelo cabeçalho de uma coluna, ou ``None``."""
    h = dobrar(str(cabecalho or "")).replace("_", " ")
    if not h.strip() or _EXCLUI_CABECALHO.search(h):
        return None
    for padrao, tipo in COLUNAS_PESSOAIS:
        if re.search(padrao, h):
            return tipo
    return None


def _decidir_colunas(cabecalhos: list[str], colunas: list[str] | None, integrais: list[str] | None) -> list[str | None]:
    """Tratamento de cada coluna.

    Returns:
        Para cada coluna: ``None`` (não processar, fora da seleção do usuário), ``""`` (analisar o
        texto de cada célula) ou um tipo de dado (tarjar a coluna inteira com esse tipo).
    """
    alvo = {dobrar(c) for c in colunas} if colunas else None
    forcadas = {dobrar(c) for c in integrais} if integrais else set()
    plano: list[str | None] = []
    for h in cabecalhos:
        d = dobrar(str(h or ""))
        if alvo is not None and d not in alvo and d not in forcadas:
            plano.append(None)
        elif d in forcadas:
            plano.append(tipo_da_coluna(h) or "MANUAL")
        else:
            plano.append(tipo_da_coluna(h) or "")
    return plano


class _Formula:
    """Fórmula cujos literais de texto são analisados; referências e funções ficam intactas."""

    def __init__(self, texto: str, gravar: Callable[[str], None]):
        self.texto = texto
        self.gravar = gravar
        self.literais = [(m.start(1), m.end(1), m.group(1).replace('""', '"')) for m in _LITERAL.finditer(texto)]
        self.novos: dict[int, str] = {}

    def unidades(self) -> list[X.Unidade]:
        return [X.Unidade(literal, self._aplicador(k)) for k, (_, _, literal) in enumerate(self.literais)
                if X.tem_conteudo(literal)]

    def _aplicador(self, k: int) -> Callable[[Resultado], list[Resultado]]:
        def aplicar(r: Resultado) -> list[Resultado]:
            if r.tarjadas:
                self.novos[k] = r.texto
                self.gravar(self._montar())
            return []
        return aplicar

    def _montar(self) -> str:
        partes, posicao = [], 0
        for k, (a, b, _) in enumerate(self.literais):
            partes.append(self.texto[posicao:a])
            partes.append(self.novos[k].replace('"', '""') if k in self.novos else self.texto[a:b])
            posicao = b
        partes.append(self.texto[posicao:])
        return "".join(partes)


def _unidades_da_grade(linhas: list[list], gravar: Callable[[int, int, object], None],
                       colunas: list[str] | None, integrais: list[str] | None, *, formulas: bool,
                       ) -> tuple[list[X.Unidade], list[tuple[int, str]]]:
    """Unidades de análise de uma grade de células.

    Células de colunas de dado pessoal viram unidades com a entidade já definida (a célula inteira):
    não são analisadas, mas participam do mesmo lote, o que propaga seus valores para as demais
    células e mantém a numeração de pseudônimos única na planilha.

    Args:
        linhas: Valores das células, com o cabeçalho na primeira linha.
        gravar: Grava um valor na célula ``(linha, coluna)`` da grade.
        colunas: Restringe o processamento a estas colunas (pelo cabeçalho).
        integrais: Colunas a tarjar por inteiro, além das detectadas pelo cabeçalho.
        formulas: Trata valores iniciados por ``=`` como fórmulas (XLSX).

    Returns:
        ``(unidades, colunas tarjadas por inteiro)``; as colunas são informadas como ``(índice, tipo)``.
    """
    if not linhas:
        return [], []
    cabecalhos = [str(c) if c is not None else "" for c in linhas[0]]
    plano = _decidir_colunas(cabecalhos, colunas, integrais)
    padrao_extra = "" if colunas is None else None  # colunas além do cabeçalho
    unidades: list[X.Unidade] = []
    for i, linha in enumerate(linhas):
        for j, valor in enumerate(linha):
            regra = plano[j] if j < len(plano) else padrao_extra
            if regra is None or valor is None or valor == "":
                continue
            if i > 0 and regra:
                texto = str(valor)
                ent = Entidade(0, len(texto), regra, texto, 1.0, "planilha:coluna", motivo="Coluna de dado pessoal")
                unidades.append(X.Unidade(texto, X.aplicador(lambda t, i=i, j=j: gravar(i, j, t)), [ent]))
                continue
            formula = getattr(valor, "text", None) if formulas else None
            if formulas and isinstance(valor, str) and valor.startswith("="):
                unidades += _Formula(valor, lambda t, i=i, j=j: gravar(i, j, t)).unidades()
            elif isinstance(formula, str):  # fórmula matricial
                unidades += _Formula(formula, lambda t, v=valor: setattr(v, "text", t)).unidades()
            elif isinstance(valor, str) or (isinstance(valor, int | float) and not isinstance(valor, bool)
                                            and sum(c.isdigit() for c in str(valor)) >= 8):
                unidades.append(X.Unidade(str(valor), X.aplicador(lambda t, i=i, j=j: gravar(i, j, t))))
    integrais_detectadas = [(j, t) for j, t in enumerate(plano) if t]
    return unidades, integrais_detectadas


def _aviso_colunas(colunas: list[tuple[str, str]]) -> list[str]:
    """Aviso sobre as colunas tarjadas por inteiro.

    As colunas são identificadas pela letra (e pela aba, no XLSX), nunca pelo texto do cabeçalho: o
    cabeçalho de uma planilha sem linha de títulos é um dado como outro qualquer.
    """
    if not colunas:
        return []
    descricao = ", ".join(f"{local} ({info_tipo(t).nome})" for local, t in colunas)
    return [f"Colunas tarjadas por inteiro pelo cabeçalho: {descricao}."]


def _verificar(texto: str, resultados: list[Resultado], anon: Anonimizador, formato: str) -> None:
    sobras = verificar_ausencia(texto, valores_tarjados(resultados), valores_protegidos(resultados, anon.permitir))
    if sobras:
        raise VazamentoDetectado(f"{len(sobras)} trecho(s) tarjado(s) ainda presente(s) no {formato} gerado.")


# ---------------------------------------------------------------------------- CSV
def anonimizar_csv(dados: bytes, anon: Anonimizador, nome: str, colunas: list[str] | None = None,
                   integrais: list[str] | None = None, *, verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza um CSV, preservando o delimitador e a estrutura.

    O arquivo de saída é gravado em UTF-8 com BOM, para que o Excel reconheça a codificação.

    Raises:
        VazamentoDetectado: A verificação encontrou valor tarjado no arquivo gerado.
    """
    texto, _ = decodificar(dados)
    amostra = texto[:20000]
    try:
        dialeto = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
    except csv.Error:
        class dialeto(csv.excel):  # noqa: N801 - subclasse local para não alterar csv.excel global
            delimiter = ";" if amostra.count(";") > amostra.count(",") else ","
    linhas = list(csv.reader(io.StringIO(texto), dialeto))

    def gravar(i: int, j: int, valor: object) -> None:
        linhas[i][j] = valor

    from openpyxl.utils import get_column_letter

    unidades, detectadas = _unidades_da_grade(linhas, gravar, colunas, integrais, formulas=False)
    resultados = X.analisar(unidades, anon)
    detectadas = [(f"coluna {get_column_letter(j + 1)}", t) for j, t in detectadas]
    buf = io.StringIO()
    escritor = csv.writer(buf, delimiter=dialeto.delimiter, quotechar='"', quoting=csv.QUOTE_MINIMAL,
                          lineterminator="\n")
    escritor.writerows(linhas)
    saida = buf.getvalue()
    if verificar:
        _verificar(saida, resultados, anon, "CSV")
    return ResultadoArquivo((chr(0xFEFF) + saida).encode("utf-8"), "csv", nome, resultados, _aviso_colunas(detectadas))


# ---------------------------------------------------------------------------- XLSX
def _unidades_da_aba(ws) -> list[X.Unidade]:
    """Unidades de análise do conteúdo da aba que não está nas células."""
    unidades: list[X.Unidade] = []

    def texto(obj, atributo: str) -> None:
        valor = getattr(obj, atributo, None)
        if isinstance(valor, str) and X.tem_conteudo(valor):
            unidades.append(X.Unidade(valor, X.aplicador(lambda t: setattr(obj, atributo, t))))

    def formula(obj, atributo: str) -> None:
        valor = getattr(obj, atributo, None)
        if isinstance(valor, str):
            unidades.extend(_Formula(valor, lambda t: setattr(obj, atributo, t)).unidades())

    for item in (ws.oddHeader, ws.oddFooter, ws.evenHeader, ws.evenFooter, ws.firstHeader, ws.firstFooter):
        for parte in (item.left, item.center, item.right):
            texto(parte, "text")
    for validacao in ws.data_validations.dataValidation:
        for atributo in ("prompt", "promptTitle", "error", "errorTitle"):
            texto(validacao, atributo)
        formula(validacao, "formula1")
        formula(validacao, "formula2")
    for formatacao in ws.conditional_formatting:
        for regra in formatacao.rules:
            texto(regra, "text")
            for k, f in enumerate(regra.formula or []):
                unidades.extend(_Formula(f, lambda t, lista=regra.formula, k=k: lista.__setitem__(k, t)).unidades())
    filtros = [ws.auto_filter] + [t.autoFilter for t in ws.tables.values() if t.autoFilter is not None]
    for filtro in filtros:
        for coluna in filtro.filterColumn:
            if coluna.filters is not None:
                for k, valor in enumerate(coluna.filters.filter):
                    if X.tem_conteudo(valor):
                        lista = coluna.filters.filter
                        unidades.append(X.Unidade(valor, X.aplicador(lambda t, lista=lista, k=k: lista.__setitem__(k, t))))
            if coluna.customFilters is not None:
                for criterio in coluna.customFilters.customFilter:
                    texto(criterio, "val")
    for nome in ws.defined_names.values():
        formula(nome, "attr_text")
    return unidades


def _titulo_valido(texto: str, usados: set[str]) -> str:
    """Título de aba válido para o Excel (sem ``[]:*?/\\``, até 31 caracteres) e não repetido."""
    base = _PROIBIDOS_ABA.sub("", texto).strip().strip("'").strip()[:_LIMITE_TITULO_ABA] or "Planilha"
    titulo, n = base, 2
    while titulo.lower() in usados:
        sufixo = f" ({n})"
        titulo = base[:_LIMITE_TITULO_ABA - len(sufixo)] + sufixo
        n += 1
    return titulo


def _trocar_abas(formula: str, mapa: dict[str, str]) -> str:
    """Atualiza as referências a abas renomeadas (``'Antigo'!A1`` ou ``Antigo!A1``)."""
    for antigo, novo in mapa.items():
        citado = "'" + novo.replace("'", "''") + "'!"
        formula = formula.replace("'" + antigo.replace("'", "''") + "'!", citado)
        if _NOME_SIMPLES.fullmatch(antigo):
            formula = re.sub(rf"(?<![\w.'!]){re.escape(antigo)}!", lambda _m, c=citado: c, formula)
    return formula


def _renomear_abas(wb, novos: dict) -> dict[str, str]:
    """Aplica os novos títulos e atualiza as referências nas fórmulas da pasta de trabalho."""
    folhas = list(wb.worksheets) + list(wb.chartsheets)
    usados = {f.title.lower() for f in folhas if f not in novos}
    mapa: dict[str, str] = {}
    for folha, texto in novos.items():
        titulo = _titulo_valido(texto, usados)
        usados.add(titulo.lower())
        mapa[folha.title] = titulo
        folha.title = titulo
    if not mapa:
        return mapa

    def trocar(valor: str | None) -> str | None:
        return _trocar_abas(valor, mapa) if isinstance(valor, str) else valor

    for ws in wb.worksheets:
        for linha in ws.iter_rows():
            for celula in linha:
                valor = celula.value
                if isinstance(valor, str) and valor.startswith("="):
                    celula.value = trocar(valor)
                elif isinstance(getattr(valor, "text", None), str):
                    valor.text = trocar(valor.text)
        for validacao in ws.data_validations.dataValidation:
            validacao.formula1, validacao.formula2 = trocar(validacao.formula1), trocar(validacao.formula2)
        for formatacao in ws.conditional_formatting:
            for regra in formatacao.rules:
                regra.formula = [trocar(f) for f in regra.formula or []]
        for nome in ws.defined_names.values():
            nome.attr_text = trocar(nome.attr_text)
    for nome in wb.defined_names.values():
        nome.attr_text = trocar(nome.attr_text)
    return mapa


def _limpar(wb) -> tuple[int, int]:
    """Remove comentários, hiperlinks, tabelas dinâmicas e propriedades do documento.

    Returns:
        ``(comentários removidos, hiperlinks removidos)``.
    """
    comentarios = hiperlinks = 0
    for ws in wb.worksheets:
        for linha in ws.iter_rows():
            for celula in linha:
                if celula.comment is not None:
                    celula.comment = None
                    comentarios += 1
                if celula.hyperlink is not None:
                    celula.hyperlink = None
                    hiperlinks += 1
        ws._pivots = []  # noqa: SLF001 - a API pública não oferece remoção de tabelas dinâmicas
        ws.legacy_drawing = None
    propriedades = wb.properties
    for campo in ("creator", "lastModifiedBy", "title", "subject", "description", "keywords", "category",
                  "identifier", "contentStatus", "version", "revision", "lastPrinted"):
        setattr(propriedades, campo, None)
    for propriedade in list(wb.custom_doc_props.props):
        wb.custom_doc_props.props.remove(propriedade)
    wb.template = False
    return comentarios, hiperlinks


def _atualizar_tabelas(wb) -> None:
    """Mantém os nomes das colunas das tabelas iguais às células de cabeçalho (exigência do Excel)."""
    from openpyxl.utils import range_boundaries

    for ws in wb.worksheets:
        for tabela in ws.tables.values():
            if tabela.headerRowCount == 0:
                continue
            coluna_inicial, linha_cabecalho, _, _ = range_boundaries(tabela.ref)
            for k, coluna in enumerate(tabela.tableColumns):
                valor = ws.cell(row=linha_cabecalho, column=coluna_inicial + k).value
                if valor is not None:
                    coluna.name = str(valor)


def _sanear_desenhos(dados: bytes, anon: Anonimizador, mapa: dict[str, str]) -> tuple[bytes, list[Resultado]]:
    """Analisa o texto de gráficos e desenhos e descarta os caches de dados dos gráficos."""
    pacote = Pacote.ler(dados)
    alvos = [n for n in pacote.ordem if n.lower().startswith(("xl/charts/", "xl/drawings/", "xl/chartsheets/"))
             and n.lower().endswith(".xml") and n not in pacote.relacionamentos]
    if not alvos:
        return dados, []
    arvores, unidades = {}, []
    for parte in alvos:
        raiz = ler_xml(pacote.partes[parte])
        for el in list(raiz.iter(*_CACHES_GRAFICO)):
            el.getparent().remove(el)
        for referencia in raiz.iter(X.q("c", "f")):
            if referencia.text and mapa:
                referencia.text = _trocar_abas(referencia.text, mapa)
        unidades += X.unidades(raiz, anon)
        arvores[parte] = raiz
    # Mesma numeração de pseudônimos das células: "Pessoa 1" no gráfico é a "Pessoa 1" da planilha.
    resultados = X.analisar(unidades, anon, continuar=True)
    return pacote.gravar(set(pacote.ordem), {p: gravar_xml(r) for p, r in arvores.items()}), resultados


def anonimizar_xlsx(dados: bytes, anon: Anonimizador, nome: str, colunas: list[str] | None = None,
                    integrais: list[str] | None = None, *, verificar: bool = True) -> ResultadoArquivo:
    """Anonimiza uma pasta de trabalho do Excel.

    Args:
        dados: Conteúdo do arquivo.
        anon: Anonimizador configurado.
        nome: Nome do arquivo de saída.
        colunas: Restringe o processamento a estas colunas (pelo cabeçalho).
        integrais: Colunas a tarjar por inteiro, além das detectadas pelo cabeçalho.
        verificar: Relê o pacote gerado e confirma que nenhum valor tarjado continua presente.

    Raises:
        ArquivoInvalido: Pasta de trabalho corrompida ou ilegível.
        VazamentoDetectado: A verificação encontrou valor tarjado na pasta de trabalho gerada.
    """
    import openpyxl

    nomes_originais = [n.lower() for n in Pacote.ler(dados).ordem]
    try:
        wb = openpyxl.load_workbook(io.BytesIO(dados), data_only=False, keep_links=False, keep_vba=False)
    except Exception as erro:
        raise ArquivoInvalido("Planilha inválida ou corrompida.") from erro

    unidades: list[X.Unidade] = []
    resultados: list[Resultado] = []
    detectadas: list[tuple[object, int, str]] = []
    for ws in wb.worksheets:
        linhas = [[c.value for c in linha] for linha in ws.iter_rows()]
        deslocamento = 0
        while linhas and all(v in (None, "") for v in linhas[0]):
            linhas.pop(0)
            deslocamento += 1

        def gravar(i: int, j: int, valor: object, ws=ws, deslocamento=deslocamento) -> None:
            ws.cell(row=i + 1 + deslocamento, column=j + 1).value = valor

        u, d = _unidades_da_grade(linhas, gravar, colunas, integrais, formulas=True)
        unidades += u + _unidades_da_aba(ws)
        detectadas += [(ws, j, t) for j, t in d]
    for nome_definido in wb.defined_names.values():
        if isinstance(nome_definido.attr_text, str):
            unidades += _Formula(nome_definido.attr_text,
                                 lambda t, n=nome_definido: setattr(n, "attr_text", t)).unidades()
    novos_titulos: dict = {}
    for folha in list(wb.worksheets) + list(wb.chartsheets):
        unidades.append(X.Unidade(folha.title, X.aplicador(lambda t, f=folha: novos_titulos.__setitem__(f, t))))

    resultados += X.analisar(unidades, anon)
    mapa = _renomear_abas(wb, novos_titulos)
    _atualizar_tabelas(wb)
    comentarios, hiperlinks = _limpar(wb)
    buf = io.BytesIO()
    wb.save(buf)
    saida, extras = _sanear_desenhos(buf.getvalue(), anon, mapa)
    resultados += extras

    from openpyxl.utils import get_column_letter

    # Os títulos das abas já estão anonimizados neste ponto.
    avisos = _aviso_colunas([(f"{ws.title}!{get_column_letter(j + 1)}", t) for ws, j, t in detectadas])
    if mapa:
        avisos.append(f"{len(mapa)} aba(s) renomeada(s) por conter dado pessoal no nome.")
    if comentarios:
        avisos.append(f"{comentarios} comentário(s) removido(s).")
    if hiperlinks:
        avisos.append(f"{hiperlinks} hiperlink(s) removido(s).")
    if any(n.startswith("xl/pivotcache") for n in nomes_originais):
        avisos.append("Tabelas dinâmicas removidas (o cache delas guarda cópia dos dados originais).")
    if any(n.startswith("xl/externallinks/") for n in nomes_originais):
        avisos.append("Vínculos com outras pastas de trabalho removidos (guardavam cópia dos dados e o caminho "
                      "do arquivo).")
    if any(n.endswith("vbaproject.bin") for n in nomes_originais):
        avisos.append("Macros removidas.")
    imagens = sum(1 for n in Pacote.ler(saida).ordem if n.lower().endswith(IMAGENS))
    if imagens:
        avisos.append(f"A planilha tem {imagens} imagem(ns) não analisada(s) (fotos ou documentos digitalizados "
                      "podem conter dados pessoais): revise-as manualmente.")
    if verificar:
        _verificar(texto_de_pacote(saida), resultados, anon, "XLSX")
    return ResultadoArquivo(saida, "xlsx", nome, resultados, avisos)
