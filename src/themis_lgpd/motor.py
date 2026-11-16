"""Motor de anonimização.

Orquestra o fluxo completo para um texto ou um lote de textos do mesmo documento:

1. **Normalização** (:mod:`themis_lgpd.texto`): cópia do texto para detecção, com mapa de posições
   de volta ao original.
2. **Detecção** (:mod:`themis_lgpd.analisador`): ``AnalyzerEngine`` do Presidio com os
   reconhecedores brasileiros.
3. **Decisão por perfil** (:mod:`themis_lgpd.perfis`): cada achado é tarjado, sinalizado para
   revisão humana ou mantido, conforme a categoria do dado e a política LGPD × LAI.
4. **Propagação** (:mod:`themis_lgpd.propagacao`): valores tarjados são procurados em todo o
   documento, para que nenhuma outra ocorrência permaneça legível.
5. **Consolidação**: sobreposições resolvidas por prioridade do tipo de dado e trechos estendidos
   até a borda da palavra, para que nenhum fragmento do dado sobre ao lado da tarja.
6. **Substituição** (:mod:`themis_lgpd.operadores`): aplicada ao texto *original* pelo
   ``AnonymizerEngine`` do Presidio.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import regex as re
from presidio_analyzer import EntityRecognizer

from . import perfis as P
from . import propagacao
from .analisador import ReconhecedorThemis, analisar_textos, obter_analisador
from .catalogo import TIPOS, categoria_de
from .catalogo import tipo as info_tipo
from .operadores import Substituidor, aplicar_com_presidio
from .reconhecedores import base as B
from .reconhecedores import sensiveis as S
from .texto import TextoNormalizado, dobrar, normalizar

#: Marcadores que indicam pessoa determinada mesmo em enunciado com verbo deôntico: primeira pessoa,
#: pronome pessoal de terceira pessoa, autodeclaração ("declarou-se parda", "se reconhece como indígena")
#: e fala relatada da própria pessoa ("contou que é bissexual", "relatou que está grávida").
_VINCULO_FORTE = (
    r"eu|meu|minha|meus|minhas|me|mim|comigo|sou|estou|estive|tive|fui|sofro|sofri|"
    # "tenho interesse", "tenho as seguintes dúvidas": fórmulas do pedido, não situação pessoal.
    r"tenho(?!\s+(?:(?:as|algumas|alguns|umas?|seguintes|outras?|muitas?)\s+)*(?:interesse|d[úu]vidas?|perguntas|"
    r"quest[õo]es|curiosidade|conhecimento|ci[êe]ncia)\b)|"
    r"trato|tratei|tomo|tomei|sinto|senti|convivo|enfrento|enfrentei|descobri|fa[çc]o|fiz|fiquei|passei|"
    r"nasci|moro|recebi|realizei|internei|operei|preciso\s+de\s+(?:tratamento|rem[ée]dio|medica[çc][ãa]o|cirurgia)|"
    r"possuo|utilizo|dependo|realizo|perdi|desenvolvi|contra[íi]|pude|dei\s+entrada|"
    r"t[ôo]|tava|(?!solicitei|requisitei|pedi)\w{3,}ei|perten[çc]o|participo|frequento|"
    r"dele|dela|ele|ela|"
    r"(?:um|uma)\s+(?:familiar|parente)|"
    r"(?:auto)?declarou-se|(?:auto)?declara-se|se\s+(?:auto)?declara(?:va|ram|m)?|se\s+reconhece(?:m|u)?|reconhece-se|"
    r"se\s+identifica(?:va)?|identifica-se|"
    r"(?:contou|relatou|relata|admitiu|revelou|confidenciou|confessou|referiu)\s+(?:que\s+)?"
    r"(?:j[áa]\s+|ainda\s+|n[ãa]o\s+)?(?:[ée]|era|est[áa]|estava|tem|tinha|teve|foi|faz|fazia|usa|usava|toma|tomava|sente|sentia|"
    r"sofre|sofria|vem|mant[ée]m|mantinha|frequenta|frequentava|bebe|bebia|fuma|fumava|ouve|escuta|v[êe])"
)
#: Papéis com artigo ("o requerente", "a paciente", "a família") e possessivos de terceira pessoa: designam
#: a pessoa de que o texto trata, mas também qualquer pessoa num enunciado normativo ("O paciente com febre
#: persistente deve receber soro"). "Uso" é também o substantivo ("o uso de máscara"), e "deles" retoma
#: também um grupo ("doze deles com sífilis").
_VINCULO_PAPEL = (
    r"seu|sua|seus|suas|deles|delas|uso|"
    r"(?:o|a|do|da|ao|à|pel[oa])\s+(?:servidor|servidora|requerente|paciente|cidad[ãa]o|cidad[ãa]|interessad[oa]|"
    r"denunciante|v[íi]tima|solicitante|alun[oa]|estudante|funcion[áa]ri[oa]|empregad[oa]|segurad[oa]|"
    r"benefici[áa]ri[oa]|filh[oa]|espos[oa]|marido|mulher|companheir[oa]|m[ãa]e|pai|irm[ãa]o?|vizinh[oa]|colega|"
    r"chefe|menor|crian[çc]a|adolescente|idos[oa]|titular|candidat[oa]|reclamante|usu[áa]ri[oa]|"
    r"net[oa]|ti[oa]|av[ôóo]|sobrinh[oa]|prim[oa]|sogr[oa]|cunhad[oa]|entead[oa]|beb[êe]|detent[oa]|pres[oa]|"
    r"internad[oa]|client[ea]|assistid[oa]|dependente|familiar|"
    # Partes e pessoas atendidas em registros policiais, judiciais, prisionais e de assistência social.
    r"r[ée]u|acusad[oa]|indiciad[oa]|investigad[oa]|declarante|depoente|noticiante|comunicante|manifestante|"
    r"reeducand[oa]|apenad[oa]|custodiad[oa]|socioeducand[oa]|acolhid[oa]|genitor[a]?|padrasto|madrasta|"
    r"ex-marido|ex-mulher|ex-espos[oa]|ex-companheir[oa]|namorad[oa]|fam[íi]lia)"
)
# Marcadores de que a frase se refere a uma pessoa determinada: primeira pessoa ("tenho", "sofri",
# "minha"), possessivos e papéis ("o requerente", "a paciente"). Usados para decidir se um termo
# sensível isolado ("asma", "católico") deve ser tarjado ou apenas sinalizado para revisão.
_VINCULO = re.compile(r"\b(?:" + _VINCULO_FORTE + "|" + _VINCULO_PAPEL + r")\b", re.IGNORECASE)
_VINCULO_FORTE_RE = re.compile(r"\b(?:" + _VINCULO_FORTE + r")\b", re.IGNORECASE)
#: Verbo deôntico ou fórmula de norma, protocolo ou edital ("deve receber", "deverá apresentar", "tem
#: assegurada", "aplicam-se"): com só papéis genéricos na frase, o termo sensível não se refere a pessoa
#: determinada (LAI, art. 3º, I).
_NORMATIVO = re.compile(
    r"\b(?:deve|devem|dever[áã]o?|poder[áã]o?|precisa(?:m)?\s+ser|aplica(?:m)?-se|utiliza(?:m)?-se|considera(?:m)?-se|"
    r"(?:[ée]|s[ãa]o|ser[áã]o?|fica(?:m)?|t[êe]m|tem)\s+(?:assegurad|garantid|vedad|obrigat[óo]ri|facultad|dispensad)\w*|"
    r"ter[áã]o?\s+(?:direito|prioridade|prefer[êe]ncia)|faz(?:em)?\s+jus|compete|incumbe|vedad[oa]s?)\b", re.IGNORECASE)
#: Início de oração com sujeito genérico ("O paciente com febre persistente…", "Toda gestante…", "Nos casos
#: de abuso…", "Quando houver febre…"), depois da numeração do item. Num relato, a mesma frase com papel
#: retomado do contexto ("A pedido da mãe, a aluna poderá…") não é norma.
_INICIO_GENERICO = re.compile(
    r"\W*(?:\d+(?:\.\d+)*\.?\s+|[a-z]\)\s+|[–•-]\s+)?(?:(?:(?:o|a|os|as)\s+)?(?:pacientes?|gestantes?|crian[çc]as?|v[íi]timas?|"
    r"candidat[oa]s?|estudantes?|alun[oa]s?|usu[áa]ri[oa]s?|servidor(?:a|es|as)?|pessoas?|mulher(?:es)?|homens?|adolescentes?|"
    r"idos[oa]s?|benefici[áa]ri[oa]s?|segurad[oa]s?|requerentes?|interessad[oa]s?|trabalhador(?:a|es|as)?|profissionais?|"
    r"profissional|rec[ée]m-nascid[oa]s?|pu[ée]rperas?|portador(?:a|es|as)?|empregad[oa]s?|titulares?|dependentes?|"
    r"fam[íi]lias?|respons[áa]ve(?:l|is)|conselheir[oa]s?)\b|(?:todo|toda|todos|todas|cada|qualquer|nenhum|nenhuma)\b|"
    r"(?:nos|nas|em)\s+(?:casos?|registros|situa[çc][õo]es|hip[óo]teses?)\b|(?:quando|caso|se|com|sem)\b)", re.IGNORECASE)
_MOTIVO_NORMATIVO = "Termo sensível em enunciado normativo ou de protocolo, sem pessoa determinada — revisar"
#: Primeira pessoa em qualquer ponto do texto: num pedido ou relato pessoal, a frase com verbo deôntico ("o
#: paciente com tuberculose deve receber o remédio na unidade?") costuma tratar do caso de quem escreve.
_PRIMEIRA_PESSOA = re.compile(r"\b(?:eu|meu|minha|meus|minhas|comigo|sou|estou|tenho|tive|fui|sofro|sofri|preciso)\b",
                              re.IGNORECASE)
#: Achados contextuais que, em norma ou protocolo, descrevem a situação em abstrato ("A vítima de abuso deve
#: ser atendida no mesmo dia", "o portador de doença grave terá direito à isenção").
_CONTEXTUAIS_EM_NORMA = frozenset({"intimidade:violencia", "saude:cid", "saude:cid-sem-ponto", "saude:frase", "saude:possui"})

# Separação entre termos coordenados: vírgula, "e" ou "ou", com o determinante do segundo termo ("e o
# respectivo tratamento oncológico"), sem pontuação final nem quebra de parágrafo.
_COORDENACAO = re.compile(r"[ \t]*(?:,[ \t]*(?:(?:e|ou)[ \t]+)?|(?:e|ou)[ \t]+)(?:(?:o|a|os|as|seu|sua|seus|suas|"
                          r"respectiv[oa]s?)[ \t]+)*", re.IGNORECASE)

# Fronteiras de frase usadas para delimitar a janela da regra de vínculo.
_FIM_FRASE = re.compile(r"[.!?;]\s|\n\s*\n|\n(?=\s*[-•*\d])")

# Dado de saúde (LGPD, art. 5º, II): o pedido costuma nomear a condição numa frase e dizer de quem é
# na seguinte ("…o fornecimento de insulina glargina. Minha filha tem diabetes…"). Por isso, para o tipo
# SAUDE, o vínculo também é procurado nas frases vizinhas — exceto quando a frase do termo trata de um
# grupo ou de estatística ("o número de casos de dengue", "a campanha de vacinação", "pacientes com
# diabetes"), conteúdo de interesse público que deve permanecer legível (LAI, art. 3º, I).
_COLETIVO = re.compile(
    r"\b(?:quantitativos?|quantidades?|n[úu]mero|total\s+d[eoa]s?|totais|[íi]ndices?|taxas?|incid[êe]ncia|preval[êe]ncia|casos|"
    r"percentua(?:l|is)|propor[çc][ãa]o|m[ée]dia|planejamento|mutir[õo]es|"
    r"notifica[çc](?:[ãa]o|[õo]es)|s[ée]ries?\s+hist[óo]ricas?|estat[íi]stic\w*|relat[óo]rios?|levantamentos?|"
    r"campanhas?|pol[íi]ticas?|programas?|cobertura|preven[çc][ãa]o|combate|conscientiza[çc][ãa]o|epidemi\w*|"
    r"pandemia|endemia|surtos?|focos|popula[çc][ãa]o|pacientes|pessoas|usu[áa]rios|alunos|estudantes|servidores|"
    r"crian[çc]as|portadores|munic[íi]pios|or[çc]amentos?|gastos|licita[çc](?:[ãa]o|[õo]es)|aquisi[çc](?:[ãa]o|[õo]es)|"
    r"distribu[íi](?:[çc][ãa]o|dos?|das?))\b",
    re.IGNORECASE,
)
# Fórmulas de contato e de pedido de resposta ("meu e-mail é…", "me enviem…"): numa frase vizinha, não
# indicam que o termo de saúde se refere ao requerente.
_FORMULA_CONTATO = re.compile(
    r"\b(?:(?:meu|minha|meus|minhas)\s+(?:e-?mails?|endere[çc]os?\s+eletr[ôo]nicos?|telefones?|celular(?:es)?|"
    r"whats\w*|zap|contatos?)|me\s+(?:envi|respond|retorn|encaminh|mand|inform|pass|liga|contat)\w*)\b",
    re.IGNORECASE,
)

# Cargos públicos que, com a opção ``preservar_agentes_publicos``, mantêm o nome visível
# (transparência ativa sobre agentes no exercício da função).
_CARGOS = (
    r"secret[áa]ri[oa](?:-geral|-executiv[oa]|-adjunt[oa])?(?:\s+de\s+estado)?|governador(?:a)?|vice-governador(?:a)?|"
    r"ministr[oa]|deputad[oa](?:\s+distrital|\s+federal)?|senador(?:a)?|vereador(?:a)?|prefeit[oa]|"
    r"president[ea]|diretor(?:a)?(?:-geral|-presidente)?|ouvidor(?:a)?(?:-geral)?|controlador(?:a)?(?:-geral)?|"
    r"procurador(?:a)?(?:-geral)?|desembargador(?:a)?|ju[íi]z(?:a)?|subsecret[áa]ri[oa]|administrador(?:a)?\s+regional|"
    r"coordenador(?:a)?|superintendente|chefe\s+de\s+gabinete|corregedor(?:a)?(?:-geral)?|conselheir[oa]|"
    r"reitor(?:a)?|vice-reitor(?:a)?|pr[óo]-reitor(?:a)?|defensor(?:a)?\s+p[úu]blic[oa](?:-geral)?|"
    r"promotor(?:a)?\s+de\s+justi[çc]a|delegad[oa](?:-geral)?(?:\s+de\s+pol[íi]cia)?|comandante(?:-geral)?|"
    r"auditor(?:a)?(?:-geral)?|pregoeir[oa]|ordenador(?:a)?\s+de\s+despesas?|fiscal\s+do\s+contrato|"
    r"gestor(?:a)?\s+do\s+contrato|chefe\s+de\s+departamento|presidente\s+da\s+comiss[ãa]o"
)


def _regex_cargos(cargos: str) -> tuple[re.Pattern, re.Pattern]:
    """Expressões de cargo antes do nome ("Secretária de Saúde, …") e depois dele ("…, Prefeito")."""
    return (re.compile(r"(?:" + cargos + r")(?:\s+(?:de|do|da)\s+[\w\s]{2,40}?)?[\s,:]*$", re.IGNORECASE),
            re.compile(r"^\s*[,–-]\s*(?:" + cargos + r")(?!\w)", re.IGNORECASE))


_CARGOS_PUBLICOS, _CARGOS_DEPOIS = _regex_cargos(_CARGOS)
_MOTIVO_AGENTE = "Agente público no exercício da função (transparência ativa)"

_MOTIVO_PROPAGACAO = "Mesmo dado já tarjado em outro ponto do documento"
_MOTIVO_DOCUMENTO = "Dado sensível em documento centrado em pessoa identificada"
_MOTIVO_PRECAUCAO = "Identificador com confiança moderada — tarjado por precaução"
_MOTIVO_ENUMERACAO = "Item de enumeração com o mesmo formato de um identificador tarjado"

# Enumeração de identificadores ("as CDAs 2023.0012.345 e 2023.0012.346", "CPFs X, Y e Z"): o
# contexto que identifica o primeiro item também se aplica aos seguintes.
_CONECTIVO_ENUMERACAO = re.compile(r"\s*(?:,|;|\be\b|\bou\b)\s*")
_ITEM_ENUMERACAO = re.compile(r"[0-9A-Za-z](?:[0-9A-Za-z.\-/]*[0-9A-Za-z])?")


def _formato(valor: str) -> str:
    """Formato de um identificador: sequências de dígitos viram "9" e de letras, "A"."""
    return re.sub(r"[A-Za-z]+", "A", re.sub(r"\d+", "9", valor))


@dataclass
class Entidade:
    """Trecho identificado no texto original e a decisão tomada sobre ele.

    Attributes:
        inicio: Posição inicial no texto original (inclusiva).
        fim: Posição final no texto original (exclusiva).
        tipo: Código do tipo de dado (ver :data:`themis_lgpd.catalogo.TIPOS`).
        valor: Trecho do texto original. Nunca é serializado sem pedido explícito.
        score: Confiança da detecção, entre 0 e 1.
        origem: Reconhecedor (e, quando houver, palavra de contexto) que produziu o achado.
        camada: ``estrutural``, ``contextual``, ``semantica`` ou ``ner`` — usada pela política de perfis.
        validado: ``True``/``False`` se o dígito verificador foi conferido; ``None`` se não se aplica.
        acao: ``tarjar``, ``alertar`` (revisão humana) ou ``manter``.
        motivo: Justificativa da ação quando ela não decorre diretamente do perfil.
        inicio_saida: Início da substituição no texto anonimizado (preenchido na anonimização).
        fim_saida: Fim da substituição no texto anonimizado.
    """

    inicio: int
    fim: int
    tipo: str
    valor: str
    score: float
    origem: str
    camada: str = B.ESTRUTURAL
    validado: bool | None = None
    acao: str = P.TARJAR
    motivo: str = ""
    inicio_saida: int | None = None
    fim_saida: int | None = None

    @property
    def rotulo(self) -> str:
        """Nome legível do tipo de dado."""
        return info_tipo(self.tipo).nome

    @property
    def categoria(self) -> str:
        """Código da categoria (ver :data:`themis_lgpd.catalogo.CATEGORIAS`)."""
        return info_tipo(self.tipo).categoria

    @property
    def base_legal(self) -> str:
        """Fundamento legal da proteção deste tipo de dado."""
        return categoria_de(self.tipo).base_legal

    @property
    def prioridade(self) -> int:
        """Prioridade do tipo na resolução de sobreposições (maior prevalece)."""
        return info_tipo(self.tipo).prioridade

    def para_dict(self, incluir_valor: bool = False) -> dict:
        """Serializa a entidade.

        Args:
            incluir_valor: Inclui o trecho original. Desligado por padrão: a serialização é usada
                em relatórios e respostas de API que não devem conter dados pessoais.
        """
        d = {
            "inicio": self.inicio, "fim": self.fim, "tipo": self.tipo, "rotulo": self.rotulo,
            "categoria": self.categoria, "acao": self.acao, "score": round(self.score, 3),
            "camada": self.camada, "validado_por_digito": self.validado, "origem": self.origem,
            "base_legal": self.base_legal, "motivo": self.motivo,
        }
        if self.inicio_saida is not None:
            d["inicio_saida"], d["fim_saida"] = self.inicio_saida, self.fim_saida
        if incluir_valor:
            d["valor"] = self.valor
        return d


@dataclass
class Resultado:
    """Resultado da anonimização de um texto.

    Attributes:
        original: Texto original (com encoding corrigido, quando necessário). Mantido apenas em
            memória; não é serializado sem pedido explícito.
        texto: Texto anonimizado.
        entidades: Todas as entidades consideradas, com a ação de cada uma.
        perfil: Nome do perfil aplicado.
        modo: Modo de substituição aplicado.
        avisos: Avisos ao usuário (ex.: encoding corrigido, reconhecimento de nomes desativado).
        substituicoes: Registro de cada troca (posições no original e na saída, valor e substituto);
            base do cofre de reversão. Contém dados pessoais.
    """

    original: str
    texto: str
    entidades: list[Entidade]
    perfil: str
    modo: str
    avisos: list[str] = field(default_factory=list)
    substituicoes: list[dict] = field(default_factory=list, repr=False)

    @property
    def tarjadas(self) -> list[Entidade]:
        """Entidades substituídas no texto de saída."""
        return [e for e in self.entidades if e.acao == P.TARJAR]

    @property
    def alertas(self) -> list[Entidade]:
        """Entidades mantidas no texto, mas sinalizadas para revisão humana."""
        return [e for e in self.entidades if e.acao == P.ALERTAR]

    def estatisticas(self) -> dict:
        """Contagens agregadas (não contêm dados pessoais)."""
        return {
            "tarjadas": len(self.tarjadas),
            "alertas": len(self.alertas),
            "por_tipo": dict(Counter(e.tipo for e in self.tarjadas)),
            "por_categoria": dict(Counter(e.categoria for e in self.tarjadas)),
            "caracteres_original": len(self.original),
            "caracteres_saida": len(self.texto),
        }

    def para_dict(self, incluir_valores: bool = False, incluir_original: bool = False) -> dict:
        """Serializa o resultado.

        Args:
            incluir_valores: Inclui o trecho original de cada entidade.
            incluir_original: Inclui o texto original completo.
        """
        d = {
            "texto_anonimizado": self.texto,
            "perfil": self.perfil,
            "modo": self.modo,
            "estatisticas": self.estatisticas(),
            "entidades": [e.para_dict(incluir_valores) for e in self.entidades],
            "avisos": self.avisos,
        }
        if incluir_original:
            d["texto_original"] = self.original
        return d


class Anonimizador:
    """Ponto de entrada da biblioteca.

    Uma instância pode ser reutilizada para muitos textos; o modelo de linguagem e o
    ``AnalyzerEngine`` são carregados uma única vez por processo e compartilhados entre instâncias.

    Args:
        perfil: Nome do perfil (``lai``, ``identificadores``, ``saude``, ``maxima``) ou um
            :class:`~themis_lgpd.perfis.Perfil` personalizado.
        modo: Forma de substituição (ver :data:`themis_lgpd.operadores.MODOS`).
        permitir: Termos que nunca são tarjados (comparação sem distinção de caixa e acentos).
        bloquear: Termos sempre tarjados, em qualquer ocorrência.
        usar_ner: Usa o modelo de linguagem para reconhecer nomes. Desativar reduz a cobertura de nomes.
        modelo_spacy: Nome do pacote do modelo spaCy.
        preservar_agentes_publicos: Mantém visível o nome precedido ou seguido de cargo público.
        chave_hmac: Chave do modo ``hmac``. Sem chave, uma chave aleatória é gerada por instância.
        reconhecedores_extras: Reconhecedores adicionais — instâncias de ``EntityRecognizer`` do
            Presidio ou objetos com o método ``detectar(texto)``.
        cargos: Cargos públicos do órgão, somados aos reconhecidos com ``preservar_agentes_publicos``
            ("superintendente regional de ensino").

    Raises:
        ValueError: Perfil ou modo inexistente.
        RuntimeError: Modelo spaCy não instalado.

    Example:
        >>> anon = Anonimizador(perfil="lai")
        >>> anon.anonimizar("Eu, Maria Souza, CPF 529.982.247-25").texto
        'Eu, [NOME], CPF [CPF]'
    """

    def __init__(
        self,
        perfil: str | P.Perfil = P.PERFIL_PADRAO,
        modo: str = "etiqueta",
        *,
        permitir: Iterable[str] = (),
        bloquear: Iterable[str] = (),
        usar_ner: bool = True,
        modelo_spacy: str = "pt_core_news_lg",
        preservar_agentes_publicos: bool = False,
        chave_hmac: bytes | str | None = None,
        reconhecedores_extras: Sequence = (),
        cargos: Iterable[str] = (),
    ):
        self.perfil = P.obter_perfil(perfil)
        self.modo = modo
        self.substituidor = Substituidor(modo, chave_hmac)
        self.permitir = [t.strip() for t in permitir if t and t.strip()]
        self.bloquear = [t.strip() for t in bloquear if t and t.strip()]
        self.preservar_agentes_publicos = preservar_agentes_publicos
        # Cargos do órgão somados aos do Themis ("superintendente regional de ensino").
        extras = [r"\s+".join(re.escape(p) for p in c.split()) for c in cargos if c and c.strip()]
        self._cargos = _regex_cargos(_CARGOS + "".join("|" + c for c in extras)) if extras else             (_CARGOS_PUBLICOS, _CARGOS_DEPOIS)
        self.usar_ner = usar_ner
        self.modelo = modelo_spacy if usar_ner else None
        # Reconhecedores específicos desta instância entram no Presidio como "ad hoc", sem alterar o
        # AnalyzerEngine compartilhado.
        self._extras = [r if isinstance(r, EntityRecognizer) else
                        ReconhecedorThemis(r, list(TIPOS), getattr(r, "nome", type(r).__name__))
                        for r in reconhecedores_extras]
        if self.bloquear:
            self._extras.append(ReconhecedorThemis(_ListaBloqueio(self.bloquear), ["MANUAL"], "Lista_Bloqueio"))
        # Carrega o motor já na construção, para que a falta do modelo seja detectada antes do uso.
        obter_analisador(self.modelo)

    # ------------------------------------------------------------------ análise
    def analisar(self, texto: str) -> list[Entidade]:
        """Identifica os dados de um texto e decide a ação sobre cada um, sem alterar o texto.

        Returns:
            Entidades em ordem de posição, com ``acao`` definida. Podem ser revistas (alterando
            ``acao``) e repassadas a :meth:`anonimizar`.
        """
        return self.analisar_lote([texto])[0]

    def analisar_lote(self, textos: Sequence[str], *, mesmo_documento: bool = False,
                      definidas: Sequence[list[Entidade] | None] | None = None,
                      externos: Iterable[tuple[str, str]] = ()) -> list[list[Entidade]]:
        """Analisa vários textos de uma vez (o modelo de linguagem processa o lote em conjunto).

        Args:
            textos: Textos a analisar.
            mesmo_documento: Indica que os textos são partes de um único documento (páginas,
                parágrafos, células). Nesse caso, um valor tarjado em qualquer parte é tarjado em
                todas; caso contrário, a propagação ocorre dentro de cada texto.
            definidas: Entidades já definidas para alguns textos (``None`` nos demais), em posições
                do texto original. Esses textos não são analisados, mas participam da propagação —
                por exemplo, uma célula de coluna "Nome", tarjada por inteiro, propaga o nome para as
                demais células da planilha.
            externos: Pares ``(tipo, valor)`` tarjados em outra etapa do mesmo documento, também
                propagados para estes textos (ex.: valores das células, ao analisar os gráficos e as
                imagens de uma planilha).

        Returns:
            Uma lista de entidades por texto, na mesma ordem da entrada.
        """
        externos = list(externos)
        normais = [normalizar(t or "") for t in textos]
        definidas = list(definidas) if definidas is not None else [None] * len(normais)
        pendentes = [i for i, d in enumerate(definidas) if d is None]
        deteccoes = analisar_textos([normais[i].texto for i in pendentes], self.modelo, self._extras,
                                    self.perfil.score_alerta)
        lotes = [list(d) if d is not None else [] for d in definidas]
        # Partes de um mesmo documento (páginas, parágrafos) compartilham a classificação do documento.
        contexto = (S.contexto_documental("\n".join(n.texto for n in normais))
                    if mesmo_documento and len(normais) > 1 else None)
        for i, dets in zip(pendentes, deteccoes):
            lotes[i] = self._decidir(normais[i], dets, contexto)
            self._enumeracoes(normais[i].original, lotes[i])
        grupos = [list(range(len(normais)))] if mesmo_documento else [[i] for i in range(len(normais))]
        for grupo in grupos:
            if self.preservar_agentes_publicos:
                self._agentes_consistentes([lotes[i] for i in grupo])
            self._propagar([normais[i] for i in grupo], [lotes[i] for i in grupo], externos)
        return [self._consolidar(n.original, ents) for n, ents in zip(normais, lotes)]

    @staticmethod
    def _agentes_consistentes(lotes: list[list[Entidade]]) -> None:
        """Mantém visíveis todas as ocorrências do nome de um agente público citado com o cargo.

        "A Secretária de Saúde, Maria Souza, … Maria Souza informou" não deve tarjar a segunda
        ocorrência: a tarja seria inócua (o nome já está visível) e o documento ficaria incoerente.
        """
        def chave(e: Entidade) -> str:
            return " ".join(dobrar(e.valor).split())

        agentes = {chave(e) for ents in lotes for e in ents if e.tipo == "NOME" and e.motivo == _MOTIVO_AGENTE}
        if not agentes:
            return
        for ents in lotes:
            for e in ents:
                if e.tipo == "NOME" and e.acao == P.TARJAR and chave(e) in agentes:
                    e.acao, e.motivo = P.MANTER, _MOTIVO_AGENTE + " — mesmo nome citado com o cargo"

    def _intervalos_permitidos(self, norm: TextoNormalizado) -> list[tuple[int, int]]:
        """Intervalos (no texto normalizado) ocupados por termos da lista de permissão."""
        if not self.permitir:
            return []
        dobrado = dobrar(norm.texto)
        saida = []
        for termo in self.permitir:
            alvo = re.escape(dobrar(" ".join(termo.split()))).replace(r"\ ", r"\s+")
            saida += [m.span() for m in re.finditer(r"(?<!\w)" + alvo + r"(?!\w)", dobrado)]
        return saida

    @staticmethod
    def _frase(texto: str, ini: int, fim: int) -> tuple[int, int]:
        """Limites da frase que contém o trecho: pontuação final ou parágrafo, até 400 caracteres de cada lado."""
        a = max((m.end() for m in _FIM_FRASE.finditer(texto, max(0, ini - 400), ini)), default=max(0, ini - 400))
        m = _FIM_FRASE.search(texto, fim, min(len(texto), fim + 400))
        return a, m.start() + 1 if m else min(len(texto), fim + 400)

    def _vinculado(self, texto: str, ini: int, fim: int, ancoras: list[tuple[int, int]]) -> bool:
        """Indica se a frase que contém o trecho se refere a uma pessoa determinada.

        A frase é delimitada por pontuação final ou parágrafo (no máximo 400 caracteres para cada
        lado). Há vínculo quando ela contém um marcador de :data:`_VINCULO` ou um identificador
        pessoal já detectado (``ancoras``).
        """
        a, b = self._frase(texto, ini, fim)
        if _VINCULO.search(texto, a, b):
            return True
        return any(a <= x < b or a < y <= b for x, y in ancoras)

    def _pessoal(self, texto: str, ini: int, fim: int) -> bool:
        """Indica se a frase do trecho tem marcador de :data:`_VINCULO_FORTE` (primeira pessoa, pronome pessoal,
        autodeclaração ou fala relatada)."""
        return bool(_VINCULO_FORTE_RE.search(texto, *self._frase(texto, ini, fim)))

    def _normativa(self, texto: str, ini: int, fim: int, identificadores: list[tuple[int, int]]) -> bool:
        """Indica se a frase do trecho é enunciado normativo sem pessoa determinada (ver :data:`_NORMATIVO`).

        A frase tem verbo deôntico ou fórmula de norma e nenhum marcador de :data:`_VINCULO_FORTE` nem
        identificador direto (nome, documento, contato); os papéis com artigo ("o paciente", "a gestante")
        designam qualquer pessoa na situação descrita.
        """
        a, b = self._frase(texto, ini, fim)
        oracao = max(a, texto.rfind(";", a, ini) + 1, texto.rfind(":", a, ini) + 1, texto.rfind("\n", a, ini) + 1)
        if (not _NORMATIVO.search(texto, a, b) or not _INICIO_GENERICO.match(texto, oracao)
                or _VINCULO_FORTE_RE.search(texto, a, b)):
            return False
        return not any(a <= x < b or a < y <= b for x, y in identificadores)

    def _vinculado_vizinhas(self, texto: str, ini: int, fim: int) -> bool:
        """Indica se a frase anterior ou a seguinte se refere a uma pessoa determinada (ver :data:`_COLETIVO`).

        Só se aplica quando a frase do próprio trecho não trata de grupo ou estatística. Nas vizinhas,
        valem os marcadores de :data:`_VINCULO`, exceto os de fórmulas de contato ("meu telefone é…");
        identificadores detectados não bastam, pois uma assinatura não liga a pessoa ao termo.
        """
        a, b = self._frase(texto, ini, fim)
        if _COLETIVO.search(texto, a, b):
            return False
        vizinhas = []
        p = a - 1
        while p > 0 and texto[p].isspace():
            p -= 1
        if p > 0:
            vizinhas.append(self._frase(texto, p, p))
        q = b
        while q < len(texto) and texto[q].isspace():
            q += 1
        if q < len(texto):
            vizinhas.append(self._frase(texto, q, q))
        for x, y in vizinhas:
            formulas = [m.span() for m in _FORMULA_CONTATO.finditer(texto, x, y)]
            if any(not any(f <= m.start() and m.end() <= g for f, g in formulas) for m in _VINCULO.finditer(texto, x, y)):
                return True
        return False

    def _agente_publico(self, texto: str, ini: int, fim: int) -> bool:
        """Indica se o nome está junto a um cargo público ("Secretária de Estado de Saúde, Fulana")."""
        antes = texto[max(0, ini - 70):ini]
        antes_re, depois_re = self._cargos
        return bool(antes_re.search(antes) or depois_re.match(texto[fim:fim + 60]))

    def _coletiva(self, texto: str, ini: int, fim: int, nomes: Sequence[tuple[int, int]] = ()) -> bool:
        """Indica se a frase do trecho trata de grupo ou estatística (ver :data:`_COLETIVO`).

        A frase vai só até a quebra de linha, para que o título ("RELATÓRIO …") e os campos de
        identificação não contem, e as palavras dentro de nome próprio ("Sindicato dos Servidores …")
        são desconsideradas.
        """
        a, b = self._frase(texto, ini, fim)
        a = max(a, texto.rfind("\n", 0, ini) + 1)
        quebra = texto.find("\n", fim, b)
        b = b if quebra < 0 else quebra
        return any(not any(x <= m.start() and m.end() <= y for x, y in nomes) for m in _COLETIVO.finditer(texto, a, b))

    def _decidir(self, norm: TextoNormalizado, dets: list[B.Deteccao],
                 documento: S.ContextoDocumental | None = None) -> list[Entidade]:
        """Aplica o perfil a cada detecção e converte as posições para o texto original.

        Args:
            norm: Texto normalizado.
            dets: Detecções do texto.
            documento: Classificação do documento inteiro, quando o texto é uma de suas partes.
        """
        texto = norm.texto
        permitidos = self._intervalos_permitidos(norm)
        ancoras = [(d.inicio, d.fim) for d in dets
                   if info_tipo(d.tipo).categoria in {"PESSOA", "DOCUMENTO", "CONTATO", "PROCESSO", "DADO_PESSOAL"}
                   and d.score >= 0.6]
        identificadores = [(d.inicio, d.fim) for d in dets
                           if info_tipo(d.tipo).categoria in {"PESSOA", "DOCUMENTO", "CONTATO"} and d.score >= 0.6]
        primeira_pessoa = bool(_PRIMEIRA_PESSOA.search(texto))
        # Vínculo no nível do documento (ver themis_lgpd.reconhecedores.sensiveis.contexto_documental): num
        # documento centrado numa pessoa identificada, o dado sensível se refere a ela; num registro clínico,
        # o trecho tarjado vai até a fronteira da frase.
        saude = [(d.inicio, d.fim) for d in dets if d.tipo == "SAUDE"]
        ctx = S.contexto_documental(texto, documento, len(saude))
        localidades = [(d.inicio, d.fim) for d in dets if d.tipo == "LOCALIDADE"]
        perfil = self.perfil
        entidades: list[Entidade] = []
        for d in dets:
            cat = info_tipo(d.tipo).categoria
            regra = perfil.regra(cat)
            motivo = ""
            if d.score < perfil.score_alerta:
                continue
            if (d.origem.startswith(S.ORIGEM_CLINICA) and not ctx.centrado
                    or d.origem.startswith(S.ORIGEM_REGISTRO) and not ctx.clinico):
                continue
            if any(a <= d.inicio and d.fim <= b for a, b in permitidos):
                acao, motivo = P.MANTER, "Lista de permissão"
            elif regra == P.MANTER:
                continue
            elif d.score < perfil.score_minimo:
                # Para identificadores diretos, a dúvida resolve-se a favor da proteção: expor um CPF
                # ou telefone é irreversível; uma tarja a mais é corrigível na revisão.
                if regra == P.TARJAR and cat in P.CATEGORIAS_IDENTIFICADORAS:
                    acao, motivo = P.TARJAR, _MOTIVO_PRECAUCAO
                else:
                    acao, motivo = P.ALERTAR, "Confiança baixa — revisar"
            elif regra == P.VINCULADO:
                isencao = ("" if d.tipo in perfil.tarjar_sensivel_sempre
                           else ctx.isencao(texto, d.inicio, d.fim, d.camada, d.origem, d.tipo,
                                            pessoal=self._pessoal(texto, d.inicio, d.fim)))
                if isencao:
                    acao, motivo = P.ALERTAR, isencao
                elif (not ctx.centrado and not primeira_pessoa and d.tipo not in perfil.tarjar_sensivel_sempre
                      and (d.camada == B.SEMANTICA or d.origem in _CONTEXTUAIS_EM_NORMA)
                      and self._normativa(texto, d.inicio, d.fim, identificadores)):
                    acao, motivo = P.ALERTAR, _MOTIVO_NORMATIVO
                elif d.camada != B.SEMANTICA or d.tipo in perfil.tarjar_sensivel_sempre:
                    acao = P.TARJAR
                elif self._vinculado(texto, d.inicio, d.fim, ancoras):
                    acao, motivo = P.TARJAR, "Termo sensível em frase que se refere a pessoa"
                elif cat == "SENSIVEL" and ctx.centrado and (
                        ctx.clinico or not self._coletiva(texto, d.inicio, d.fim, [*ctx.protegidos, *ctx.nomes_proprios])):
                    acao, motivo = P.TARJAR, _MOTIVO_DOCUMENTO
                elif cat == "SENSIVEL" and ctx.em(ctx.linhas_pessoais, d.inicio, d.fim):
                    acao, motivo = P.TARJAR, "Dado sensível em linha de tabela que identifica a pessoa"
                elif d.tipo == "SAUDE" and self._vinculado_vizinhas(texto, d.inicio, d.fim):
                    acao, motivo = P.TARJAR, "Dado de saúde em relato sobre pessoa determinada (frase vizinha)"
                else:
                    acao, motivo = P.ALERTAR, "Termo sensível sem vínculo claro com pessoa — revisar"
            else:
                acao = regra
            if acao == P.TARJAR and d.tipo == "NOME" and self.preservar_agentes_publicos \
                    and self._agente_publico(texto, d.inicio, d.fim):
                acao, motivo = P.MANTER, _MOTIVO_AGENTE
            trechos = [(d.inicio, d.fim)]
            if acao == P.TARJAR and d.tipo == "SAUDE":
                trechos = ctx.recortar(texto, *ctx.estender(texto, d.inicio, d.fim, saude, localidades),
                                       achado=(d.inicio, d.fim))
            for inicio, final in trechos:
                ini, fim = norm.para_original(inicio, final)
                entidades.append(Entidade(ini, fim, d.tipo, norm.original[ini:fim], d.score, d.origem, d.camada,
                                          d.validado, acao, motivo))
        # Corpo de tabela de registro clínico (exames, prescrição, achados por dente ou por domínio).
        regra_saude = perfil.regra("SENSIVEL")
        if saude and regra_saude in (P.VINCULADO, P.TARJAR, P.ALERTAR) and ctx.linhas_clinicas:
            acao = P.ALERTAR if regra_saude == P.ALERTAR else P.TARJAR
            for a, b in ctx.linhas_clinicas:
                ini, fim = norm.para_original(a, b)
                entidades.append(Entidade(ini, fim, "SAUDE", norm.original[ini:fim], 0.65, S.ORIGEM_CLINICA + "tabela",
                                          B.SEMANTICA, None, acao, _MOTIVO_DOCUMENTO))
        self._saude_coordenada(norm.original, entidades)
        self._saude_consistente(entidades)
        return self._consolidar(norm.original, entidades)

    @staticmethod
    def _saude_coordenada(original: str, entidades: list[Entidade]) -> None:
        """Tarja o termo de saúde coordenado a outro já tarjado ("tinha febre e diarreia").

        A coordenação por vírgula, "e" ou "ou" atribui os dois termos à mesma pessoa; o que fica isolado
        de vínculo próprio é o segundo ("diarreia"), sinalizado sem esta regra.
        """
        tarjadas = sorted((e.inicio, e.fim) for e in entidades if e.tipo == "SAUDE" and e.acao == P.TARJAR)
        if not tarjadas:
            return
        for e in entidades:
            if (e.tipo != "SAUDE" or e.acao != P.ALERTAR or e.motivo in S.MOTIVOS_ISENCAO
                    or e.motivo == _MOTIVO_NORMATIVO):
                continue
            if any(_COORDENACAO.fullmatch(original, b, e.inicio) or _COORDENACAO.fullmatch(original, e.fim, a)
                   for a, b in tarjadas if b <= e.inicio or e.fim <= a):
                e.acao, e.motivo = P.TARJAR, "Termo de saúde coordenado a outro já tarjado"

    @staticmethod
    def _saude_consistente(entidades: list[Entidade]) -> None:
        """Tarja as demais ocorrências de um dado de saúde já tarjado no mesmo texto.

        Em "estou em tratamento de hepatite autoimune … a licença por hepatite autoimune suspende o
        estágio probatório?", a segunda menção revelaria a condição protegida na primeira. Só se
        aplica a ocorrências com o mesmo termo (sem distinção de caixa, acentos e espaços) ou contidas num
        trecho tarjado com qualificadores e atributos ("prótese" depois de "prótese na perna direita", "asma
        grave" depois de "crise de asma grave"), salvo os núcleos genéricos ("deficiência").
        """
        def chave(e: Entidade) -> str:
            return " ".join(dobrar(e.valor).split())

        tarjadas = {chave(e) for e in entidades if e.tipo == "SAUDE" and e.acao == P.TARJAR}
        for e in entidades:
            if e.tipo != "SAUDE" or e.acao != P.ALERTAR or e.motivo in S.MOTIVOS_ISENCAO:
                continue
            k = chave(e)
            if k in tarjadas or (len(k) >= 4 and not S.termo_generico(k)
                                 and any(f" {k} " in f" {t} " for t in tarjadas)):
                e.acao, e.motivo = P.TARJAR, "Mesmo dado de saúde já tarjado no texto"

    @staticmethod
    def _enumeracoes(original: str, entidades: list[Entidade]) -> None:
        """Tarja os demais itens de uma enumeração que começa por um identificador tarjado.

        Em "as CDAs 2023.0012.345 e 2023.0012.346", o contexto ("CDAs") identifica só o primeiro
        número. Itens seguintes ligados por vírgula, ponto e vírgula, "e" ou "ou", com o mesmo
        formato (mesma sequência de grupos de dígitos, letras e pontuação) e quantidade de dígitos
        próxima, recebem o mesmo tipo. Só se aplica a valores com quatro dígitos ou mais.
        """
        ocupados = [(e.inicio, e.fim) for e in entidades]
        novos: list[Entidade] = []
        for e in [e for e in entidades if e.acao == P.TARJAR and sum(c.isdigit() for c in e.valor) >= 4]:
            formato, digitos, fim = _formato(e.valor), sum(c.isdigit() for c in e.valor), e.fim
            while (conectivo := _CONECTIVO_ENUMERACAO.match(original, fim)) is not None:
                item = _ITEM_ENUMERACAO.match(original, conectivo.end())
                if item is None or _formato(item.group()) != formato or \
                        abs(sum(c.isdigit() for c in item.group()) - digitos) > 2:
                    break
                a, b = item.span()
                if not any(x < b and a < y for x, y in ocupados):
                    novos.append(Entidade(a, b, e.tipo, original[a:b], e.score, "enumeracao", e.camada, None,
                                          P.TARJAR, _MOTIVO_ENUMERACAO))
                    ocupados.append((a, b))
                fim = b
        entidades.extend(novos)

    def _propagar(self, normais: list[TextoNormalizado], lotes: list[list[Entidade]],
                  externos: Sequence[tuple[str, str]] = ()) -> None:
        """Tarja, em todos os textos do grupo, as demais ocorrências de valores já tarjados.

        As novas entidades são acrescentadas às listas de ``lotes``. Não são alteradas as ocorrências
        já cobertas por uma tarja, as protegidas pela lista de permissão ou mantidas por decisão
        explícita, e as que fazem parte de um nome de lugar ou de organização não tarjado.

        Args:
            normais: Textos do grupo.
            lotes: Entidades de cada texto.
            externos: Valores tarjados em outra etapa do mesmo documento.
        """
        tarjadas = [(e.tipo, e.valor) for ents in lotes for e in ents if e.acao == P.TARJAR] + list(externos)
        if not tarjadas:
            return
        originais = [n.original for n in normais]
        protegidos: list[list[tuple[int, int]]] = []
        for norm, ents in zip(normais, lotes):
            intervalos = [norm.para_original(a, b) for a, b in self._intervalos_permitidos(norm)]
            intervalos += [(e.inicio, e.fim) for e in ents
                           if e.acao == P.MANTER or (e.acao == P.ALERTAR and e.categoria in P.NOMES_NAO_PESSOAIS)]
            protegidos.append(intervalos)
        for oc in propagacao.localizar(originais, tarjadas):
            ents = lotes[oc.indice_texto]
            if any(e.acao == P.TARJAR and e.inicio < oc.fim and oc.inicio < e.fim for e in ents):
                continue
            if any(a <= oc.inicio and oc.fim <= b for a, b in protegidos[oc.indice_texto]):
                continue
            origem = "propagacao:parte-de-nome" if oc.parcial else "propagacao"
            ents.append(Entidade(oc.inicio, oc.fim, oc.tipo, originais[oc.indice_texto][oc.inicio:oc.fim], 0.9,
                                 origem, B.CONTEXTUAL, None, P.TARJAR, _MOTIVO_PROPAGACAO))

    # ------------------------------------------------------------------ consolidação
    @staticmethod
    def _expandir(texto: str, e: Entidade) -> None:
        """Estende o trecho até as bordas da palavra ou número em que começa ou termina.

        Impede que um fragmento do dado fique visível quando um reconhecedor delimita apenas parte
        dele (ex.: ``0[TELEFONE]`` em uma CNH). Números ligados por ``.``, ``-`` ou ``/`` são tratados
        como um único token. A extensão só ocorre se o corte cair no meio do token.
        """
        ini, fim = e.inicio, e.fim
        while fim > ini and texto[fim - 1].isspace():
            fim -= 1

        def colado_esq(i: int) -> bool:
            return texto[i - 1].isalnum() or (
                i > 1 and texto[i - 1] in ".-/" and texto[i - 2].isdigit() and texto[i].isdigit())

        def colado_dir(f: int) -> bool:
            return texto[f].isalnum() or (
                f + 1 < len(texto) and texto[f] in ".-/" and texto[f - 1].isdigit() and texto[f + 1].isdigit())

        if 0 < ini < len(texto) and texto[ini].isalnum():
            while ini > 0 and colado_esq(ini):
                ini -= 1
        if 0 < fim < len(texto) and texto[fim - 1].isalnum():
            while fim < len(texto) and colado_dir(fim):
                fim += 1
        if (ini, fim) != (e.inicio, e.fim):
            e.inicio, e.fim, e.valor = ini, fim, texto[ini:fim]

    @staticmethod
    def _unir_mesmo_tipo(original: str, tarjadas: list[Entidade]) -> list[Entidade]:
        """Funde entidades do mesmo tipo que se sobrepõem ou se tocam (ex.: duas fontes para o mesmo nome)."""
        saida: list[Entidade] = []
        for e in sorted(tarjadas, key=lambda e: (e.tipo, e.inicio)):
            ult = saida[-1] if saida else None
            if ult is not None and ult.tipo == e.tipo and e.inicio <= ult.fim:
                if e.fim > ult.fim:
                    ult.fim = e.fim
                    ult.valor = original[ult.inicio:ult.fim]
                ult.score = max(ult.score, e.score)
                if e.origem not in ult.origem:
                    ult.origem += "+" + e.origem
                ult.validado = ult.validado or e.validado
            else:
                saida.append(e)
        return saida

    def _consolidar(self, original: str, entidades: list[Entidade]) -> list[Entidade]:
        """Normaliza a lista de entidades de um texto.

        Estende as tarjas às bordas dos tokens, elimina duplicatas, funde entidades do mesmo tipo
        e remove do relatório os trechos já contidos em outro de prioridade igual ou maior (entre
        alertas, os contidos em outro alerta). A cobertura das tarjas nunca diminui nesta etapa.
        """
        tarjar = [e for e in entidades if e.acao == P.TARJAR]
        for e in tarjar:
            self._expandir(original, e)
        melhor: dict[tuple[int, int, str], Entidade] = {}
        for e in sorted(entidades, key=lambda e: (-_peso_acao(e.acao), -e.prioridade, -e.score)):
            chave = (e.inicio, e.fim, "T" if e.acao == P.TARJAR else e.acao)
            melhor.setdefault(chave, e)
        unicas = list(melhor.values())
        tarjadas = self._unir_mesmo_tipo(original, [e for e in unicas if e.acao == P.TARJAR])
        unicas = tarjadas + [e for e in unicas if e.acao != P.TARJAR]
        tarjadas.sort(key=lambda e: (-e.prioridade, -(e.fim - e.inicio), -e.score))
        aceitas: list[Entidade] = []
        for e in tarjadas:
            if any(a.inicio <= e.inicio and e.fim <= a.fim and a.prioridade >= e.prioridade for a in aceitas):
                continue
            aceitas.append(e)
        outras = [e for e in unicas if e.acao != P.TARJAR
                  and not any(a.inicio <= e.inicio and e.fim <= a.fim for a in aceitas)]
        outras.sort(key=lambda e: (-e.prioridade, -e.score))
        filtradas: list[Entidade] = []
        for e in outras:
            # Um alerta contido em outro já aceito é redundante; o que o contém não é: a frase de um
            # quase-identificador ("o atendente do guichê 4 na unidade de Campo Grande no dia…")
            # continua sinalizada inteira mesmo que o município nela citado já tenha alerta próprio.
            if not any(f.inicio <= e.inicio and e.fim <= f.fim and f.acao == e.acao for f in filtradas):
                filtradas.append(e)
        return sorted(aceitas + filtradas, key=lambda e: (e.inicio, -e.fim))

    # ------------------------------------------------------------------ anonimização
    def anonimizar(self, texto: str, entidades: list[Entidade] | None = None) -> Resultado:
        """Anonimiza um texto.

        Args:
            texto: Texto de entrada.
            entidades: Entidades previamente obtidas com :meth:`analisar` e, opcionalmente,
                revistas. Se omitidas, a análise é feita aqui.

        Returns:
            O :class:`Resultado`, com o texto anonimizado e as entidades.
        """
        return self.anonimizar_lote([texto], [entidades] if entidades is not None else None)[0]

    def anonimizar_lote(self, textos: Sequence[str], entidades: Sequence[list[Entidade] | None] | None = None,
                        consistente: bool = True, *, mesmo_documento: bool = False,
                        continuar: bool = False, externos: Iterable[tuple[str, str]] = ()) -> list[Resultado]:
        """Anonimiza vários textos.

        Args:
            textos: Textos de entrada.
            entidades: Entidades por texto, se já analisadas e revistas. Textos com ``None`` são
                analisados aqui; se todos tiverem entidades, nenhuma análise nem propagação é feita.
            consistente: Mantém o mesmo pseudônimo para a mesma pessoa ou valor em todo o lote.
            mesmo_documento: Os textos são partes de um mesmo documento (ver :meth:`analisar_lote`).
            continuar: Mantém a numeração de pseudônimos da chamada anterior, para partes de um
                mesmo arquivo processadas em etapas (ex.: células e, depois, gráficos de uma planilha).
            externos: Valores tarjados em etapa anterior do mesmo arquivo (ver :meth:`analisar_lote`).

        Returns:
            Um :class:`Resultado` por texto, na ordem da entrada.
        """
        normais = [normalizar(t or "") for t in textos]
        if entidades is None or any(e is None for e in entidades):
            entidades = self.analisar_lote(textos, mesmo_documento=mesmo_documento, definidas=entidades,
                                           externos=externos)
        resultados = []
        if not continuar:
            self.substituidor.reiniciar()
        for norm, ents in zip(normais, entidades):
            if not consistente:
                self.substituidor.reiniciar()
            resultados.append(self._aplicar(norm, list(ents)))
        return resultados

    def _aplicar(self, norm: TextoNormalizado, entidades: list[Entidade]) -> Resultado:
        """Substitui os trechos tarjados no texto original.

        Cada caractere coberto por mais de uma entidade pertence à de maior prioridade de tipo
        (ex.: um CPF validado prevalece sobre um telefone que o sobreponha). Trechos contíguos do
        mesmo dono formam um segmento; os segmentos, sem sobreposição, são entregues ao
        ``AnonymizerEngine`` do Presidio.
        """
        original = norm.original
        for e in entidades:
            e.inicio_saida = e.fim_saida = None
        tarjar = [e for e in entidades if e.acao == P.TARJAR]
        pontos = sorted({p for e in tarjar for p in (e.inicio, e.fim)})
        trechos: list[tuple[int, int, Entidade]] = []
        for a, b in zip(pontos, pontos[1:]):
            cobrindo = [e for e in tarjar if e.inicio <= a and b <= e.fim]
            if not cobrindo:
                continue
            dono = max(cobrindo, key=lambda e: (e.prioridade, e.fim - e.inicio, e.score))
            if trechos and trechos[-1][1] == a and trechos[-1][2].tipo == dono.tipo:
                trechos[-1] = (trechos[-1][0], b, dono)
            else:
                trechos.append((a, b, dono))
        segmentos: list[tuple[int, int, Entidade]] = []
        for a, b, dono in trechos:
            if not any(ch.isalnum() for ch in original[a:b]):
                continue
            # Um fragmento de entidade cortado por outra não deve absorver espaços ou pontuação
            # das bordas, que pertencem ao texto ao redor.
            while a < b and not original[a].isalnum() and a != dono.inicio:
                a += 1
            while b > a and not original[b - 1].isalnum() and b != dono.fim:
                b -= 1
            segmentos.append((a, b, dono))
        texto_saida, subs = aplicar_com_presidio(original, segmentos, self.substituidor)
        for s, (_, _, dono) in zip(subs, segmentos):
            if dono.inicio_saida is None:
                dono.inicio_saida = s["inicio_saida"]
            dono.fim_saida = s["fim_saida"]
        avisos = []
        if norm.encoding_corrigido:
            avisos.append("O texto tinha caracteres corrompidos (mojibake) e foi corrigido antes da análise.")
        if not self.usar_ner:
            avisos.append("Reconhecimento de nomes por modelo de linguagem desativado: cobertura de nomes reduzida.")
        return Resultado(original, texto_saida, entidades, self.perfil.nome, self.modo, avisos, subs)


class _ListaBloqueio:
    """Reconhecedor dos termos que o usuário manda tarjar sempre.

    A comparação ignora caixa e acentos e tolera variação de espaços entre as palavras do termo.
    """

    nome = "lista:bloquear"

    def __init__(self, termos: Sequence[str]):
        self._res = [re.compile(r"(?<!\w)" + re.escape(dobrar(" ".join(t.split()))).replace(r"\ ", r"\s+") + r"(?!\w)")
                     for t in termos]

    def detectar(self, texto: str) -> list[B.Deteccao]:
        dobrado = dobrar(texto)
        return [B.Deteccao(m.start(), m.end(), "MANUAL", 1.0, self.nome, B.CONTEXTUAL, contexto_aplicado=True)
                for r in self._res for m in r.finditer(dobrado)]


def _peso_acao(acao: str) -> int:
    """Ordem de precedência entre ações para a mesma posição: tarjar > manter > alertar."""
    return {P.TARJAR: 3, P.MANTER: 2, P.ALERTAR: 1}.get(acao, 0)


def anonimizar(texto: str, perfil: str = P.PERFIL_PADRAO, modo: str = "etiqueta", **kwargs) -> Resultado:
    """Atalho para anonimizar um único texto.

    Para vários textos, reutilize um :class:`Anonimizador`; criar uma instância por texto repete a
    configuração do motor.

    Example:
        >>> anonimizar("CPF 529.982.247-25").texto
        'CPF [CPF]'
    """
    return Anonimizador(perfil, modo, **kwargs).anonimizar(texto)
