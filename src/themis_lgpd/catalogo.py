"""Catálogo dos tipos de informação reconhecidos, com categoria, etiqueta e base legal.

Cada tipo de dado (CPF, nome, endereço…) pertence a uma categoria. A categoria determina a regra
aplicada pelos perfis (ver :mod:`themis_lgpd.perfis`) e fornece a base legal e a justificativa
registradas no relatório de tarjamento, conforme a orientação da LAI de que toda restrição de acesso
seja motivada.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Categoria:
    """Grupo de tipos de dado com o mesmo tratamento e a mesma fundamentação.

    Attributes:
        codigo: Identificador usado nos perfis.
        nome: Nome legível.
        base_legal: Dispositivos legais que fundamentam a restrição de acesso.
        justificativa: Texto da justificativa registrada no relatório de tarjamento.
    """

    codigo: str
    nome: str
    base_legal: str
    justificativa: str


@dataclass(frozen=True)
class TipoInfo:
    """Tipo de dado reconhecido.

    Attributes:
        codigo: Identificador do tipo (ex.: ``CPF``).
        nome: Nome legível.
        categoria: Código da categoria (ver :data:`CATEGORIAS`).
        etiqueta: Substituto usado no modo ``etiqueta`` (ex.: ``[CPF]``).
        prioridade: Precedência na resolução de sobreposições: quando dois achados disputam o mesmo
            trecho, o de maior prioridade define a etiqueta. Identificadores validados por dígito
            verificador têm prioridade sobre padrões genéricos, como telefone.
    """

    codigo: str
    nome: str
    categoria: str
    etiqueta: str
    prioridade: int


_BASE_PESSOAL = "LGPD, art. 5º, I; LAI, art. 31, § 1º, I"
_BASE_SENSIVEL = "LGPD, art. 5º, II, e art. 11; LAI, art. 31"

#: Categorias de dado, pelo código.
CATEGORIAS: dict[str, Categoria] = {
    c.codigo: c
    for c in [
        Categoria("PESSOA", "Nome de pessoa natural", _BASE_PESSOAL,
                  "Identifica diretamente pessoa natural; informação pessoal de acesso restrito."),
        Categoria("DOCUMENTO", "Documento de identificação", _BASE_PESSOAL,
                  "Número de documento que identifica pessoa natural."),
        Categoria("DADO_PESSOAL", "Dado pessoal", _BASE_PESSOAL,
                  "Dado que, combinado a outros, permite identificar a pessoa."),
        Categoria("CONTATO", "Contato pessoal", _BASE_PESSOAL,
                  "Meio de contato que permite localizar ou identificar a pessoa."),
        Categoria("LOCALIZACAO", "Endereço", _BASE_PESSOAL,
                  "Endereço residencial ou de localização de pessoa natural."),
        Categoria("FINANCEIRO", "Dado financeiro", _BASE_PESSOAL + "; LC 105/2001",
                  "Dado bancário ou de pagamento vinculado a pessoa natural."),
        Categoria("ECONOMICO", "Situação econômica de pessoa natural", _BASE_PESSOAL,
                  "Valor recebido, pago ou devido por pessoa natural (renda, remuneração, benefício, dívida, "
                  "multa), que expõe sua situação econômica."),
        Categoria("VEICULO", "Identificação de veículo", _BASE_PESSOAL,
                  "Identificador de veículo que permite chegar ao proprietário."),
        Categoria("PROCESSO", "Número de processo ou protocolo", _BASE_PESSOAL,
                  "Identificador indireto: permite consultar autos com dados do interessado."),
        Categoria("SENSIVEL", "Dado pessoal sensível", _BASE_SENSIVEL,
                  "Dado pessoal sensível vinculado a pessoa natural."),
        Categoria("INTIMIDADE", "Intimidade e vida privada", "LAI, art. 31, caput e § 1º, I; CF, art. 5º, X",
                  "Relato que expõe intimidade, vida privada, honra ou situação de risco."),
        Categoria("MENOR", "Dado de criança ou adolescente", "LGPD, art. 14; ECA, arts. 17 e 143",
                  "Dado de criança ou adolescente, que exige proteção integral."),
        Categoria("EMPRESA", "Identificação de pessoa jurídica", "LAI, art. 22 (quando houver sigilo legal)",
                  "Tarjado apenas por configuração do perfil; CNPJ, em regra, é informação pública."),
        Categoria("LOCALIDADE", "Localidade", _BASE_PESSOAL,
                  "Quase-identificador: cidade ou região administrativa."),
        Categoria("URL", "Endereço de internet", "LAI, art. 31 (quando pessoal)",
                  "Endereço de internet sem indício de vínculo pessoal."),
        Categoria("INSTITUCIONAL", "Dado de órgão ou entidade", "LAI, art. 8º, § 1º, I; LGPD, art. 5º, I (a contrario)",
                  "Contato, endereço ou veículo do órgão, de divulgação obrigatória; não é dado pessoal."),
        Categoria("QUASE_IDENTIFICADOR", "Quase-identificador", _BASE_PESSOAL,
                  "Informação que, combinada a outras, pode reidentificar a pessoa."),
        Categoria("MANUAL", "Tarja manual", "Decisão do revisor",
                  "Trecho incluído manualmente pelo revisor."),
    ]
}

#: Tipos de dado reconhecidos, pelo código.
TIPOS: dict[str, TipoInfo] = {
    t.codigo: t
    for t in [
        TipoInfo("NOME", "Nome de pessoa", "PESSOA", "[NOME]", 75),
        TipoInfo("CPF", "CPF", "DOCUMENTO", "[CPF]", 100),
        TipoInfo("RG", "RG / Carteira de identidade", "DOCUMENTO", "[RG]", 95),
        TipoInfo("CNH", "CNH", "DOCUMENTO", "[CNH]", 95),
        TipoInfo("PIS", "PIS/PASEP/NIS/NIT", "DOCUMENTO", "[PIS]", 95),
        TipoInfo("TITULO_ELEITOR", "Título de eleitor", "DOCUMENTO", "[TÍTULO DE ELEITOR]", 95),
        TipoInfo("CNS", "Cartão Nacional de Saúde (SUS)", "DOCUMENTO", "[CARTÃO SUS]", 95),
        TipoInfo("PASSAPORTE", "Passaporte", "DOCUMENTO", "[PASSAPORTE]", 90),
        TipoInfo("CTPS", "Carteira de trabalho", "DOCUMENTO", "[CTPS]", 90),
        TipoInfo("CERTIDAO", "Matrícula de certidão civil", "DOCUMENTO", "[CERTIDÃO]", 90),
        TipoInfo("MATRICULA", "Matrícula funcional", "DOCUMENTO", "[MATRÍCULA]", 85),
        TipoInfo("REGISTRO_PROFISSIONAL", "Registro profissional (OAB, CRM…)", "DOCUMENTO",
                 "[REGISTRO PROFISSIONAL]", 85),
        TipoInfo("BENEFICIO", "Número de benefício previdenciário ou social (NB do INSS)", "DOCUMENTO",
                 "[BENEFÍCIO]", 90),
        TipoInfo("REGISTRO_SAUDE", "Prontuário, DNV, AIH ou cartão de vacina", "DOCUMENTO", "[REGISTRO DE SAÚDE]", 85),
        TipoInfo("MATRICULA_ESCOLAR", "Matrícula escolar ou registro acadêmico (RA)", "DOCUMENTO",
                 "[MATRÍCULA ESCOLAR]", 85),
        TipoInfo("INSCRICAO_IMOVEL", "Inscrição imobiliária ou cadastral (IPTU, CCM)", "DOCUMENTO", "[INSCRIÇÃO]", 80),
        TipoInfo("CAR", "Recibo do Cadastro Ambiental Rural (CAR)", "LOCALIZACAO", "[CAR]", 90),
        TipoInfo("DOCUMENTO", "Número de documento", "DOCUMENTO", "[DOCUMENTO]", 80),
        TipoInfo("DATA_NASCIMENTO", "Data de nascimento", "DADO_PESSOAL", "[DATA DE NASCIMENTO]", 85),
        TipoInfo("IDADE", "Idade de pessoa", "DADO_PESSOAL", "[IDADE]", 80),
        TipoInfo("EMAIL", "E-mail", "CONTATO", "[E-MAIL]", 90),
        TipoInfo("TELEFONE", "Telefone", "CONTATO", "[TELEFONE]", 85),
        TipoInfo("PERFIL_REDE_SOCIAL", "Perfil em rede social", "CONTATO", "[PERFIL]", 85),
        TipoInfo("IP", "Endereço IP", "CONTATO", "[IP]", 80),
        TipoInfo("ENDERECO", "Endereço", "LOCALIZACAO", "[ENDEREÇO]", 70),
        TipoInfo("CEP", "CEP", "LOCALIZACAO", "[CEP]", 80),
        TipoInfo("CONTA_BANCARIA", "Agência/conta bancária", "FINANCEIRO", "[CONTA BANCÁRIA]", 85),
        TipoInfo("CARTAO", "Cartão de pagamento", "FINANCEIRO", "[CARTÃO]", 90),
        TipoInfo("CHAVE_PIX", "Chave PIX", "FINANCEIRO", "[CHAVE PIX]", 90),
        TipoInfo("CARTEIRA_CRIPTO", "Carteira de criptomoeda", "FINANCEIRO", "[CARTEIRA CRIPTO]", 85),
        TipoInfo("VALOR_PESSOAL", "Valor recebido ou devido por pessoa natural", "ECONOMICO", "[VALOR]", 70),
        TipoInfo("PLACA", "Placa de veículo", "VEICULO", "[PLACA]", 85),
        TipoInfo("RENAVAM", "RENAVAM", "VEICULO", "[RENAVAM]", 90),
        TipoInfo("CHASSI", "Chassi (VIN)", "VEICULO", "[CHASSI]", 90),
        TipoInfo("PROCESSO_ADMINISTRATIVO", "Processo administrativo (SEI/NUP)", "PROCESSO", "[PROCESSO]", 80),
        TipoInfo("PROCESSO_JUDICIAL", "Processo judicial (CNJ)", "PROCESSO", "[PROCESSO JUDICIAL]", 85),
        TipoInfo("PROTOCOLO", "Protocolo", "PROCESSO", "[PROTOCOLO]", 75),
        TipoInfo("CNPJ", "CNPJ", "EMPRESA", "[CNPJ]", 90),
        TipoInfo("SAUDE", "Dado de saúde", "SENSIVEL", "[DADO DE SAÚDE]", 60),
        TipoInfo("RELIGIAO", "Convicção religiosa", "SENSIVEL", "[CONVICÇÃO RELIGIOSA]", 60),
        TipoInfo("OPINIAO_POLITICA", "Opinião política", "SENSIVEL", "[OPINIÃO POLÍTICA]", 60),
        TipoInfo("FILIACAO_SINDICAL", "Filiação sindical ou associativa", "SENSIVEL", "[FILIAÇÃO]", 60),
        TipoInfo("VIDA_SEXUAL", "Vida sexual / orientação sexual", "SENSIVEL", "[VIDA SEXUAL]", 60),
        TipoInfo("GENETICO_BIOMETRICO", "Dado genético ou biométrico", "SENSIVEL", "[DADO BIOMÉTRICO]", 60),
        TipoInfo("ORIGEM_RACIAL", "Origem racial ou étnica", "SENSIVEL", "[ORIGEM RACIAL]", 60),
        TipoInfo("VIOLENCIA", "Situação de violência ou risco", "INTIMIDADE", "[SITUAÇÃO DE VIOLÊNCIA]", 60),
        TipoInfo("DADO_DE_MENOR", "Dado de criança ou adolescente", "MENOR", "[DADO DE MENOR]", 60),
        TipoInfo("LOCALIDADE", "Cidade ou região administrativa", "LOCALIDADE", "[LOCALIDADE]", 30),
        TipoInfo("URL", "Endereço de internet", "URL", "[URL]", 20),
        TipoInfo("CONTATO_INSTITUCIONAL", "Telefone ou e-mail de órgão ou setor", "INSTITUCIONAL",
                 "[CONTATO INSTITUCIONAL]", 20),
        TipoInfo("ENDERECO_INSTITUCIONAL", "Endereço de sede ou unidade de órgão", "INSTITUCIONAL",
                 "[ENDEREÇO INSTITUCIONAL]", 20),
        TipoInfo("PLACA_OFICIAL", "Placa de veículo da frota oficial", "INSTITUCIONAL", "[PLACA OFICIAL]", 20),
        TipoInfo("QUASE_IDENTIFICADOR", "Quase-identificador", "QUASE_IDENTIFICADOR", "[QUASE-IDENTIFICADOR]", 15),
        TipoInfo("NUMERO_NAO_IDENTIFICADO", "Número longo não identificado", "QUASE_IDENTIFICADOR", "[NÚMERO]", 10),
        TipoInfo("MANUAL", "Trecho tarjado manualmente", "MANUAL", "[TARJADO]", 110),
    ]
}


def tipo(codigo: str) -> TipoInfo:
    """Informações de um tipo de dado.

    Tipos desconhecidos — por exemplo, produzidos por um reconhecedor externo registrado pelo
    usuário — são tratados como dado pessoal genérico, para que nunca deixem de ser tarjados por
    falta de cadastro.
    """
    try:
        return TIPOS[codigo]
    except KeyError:
        return TipoInfo(codigo, codigo.replace("_", " ").title(), "DADO_PESSOAL", f"[{codigo}]", 50)


def categoria_de(codigo_tipo: str) -> Categoria:
    """Categoria de um tipo de dado (ver :func:`tipo`)."""
    return CATEGORIAS[tipo(codigo_tipo).categoria]


#: Tipos do catálogo original, que não podem ser redefinidos por configuração.
_TIPOS_ORIGINAIS = frozenset(TIPOS)


def registrar_tipo(info: TipoInfo) -> None:
    """Acrescenta ao catálogo um tipo definido pelo órgão (ver :mod:`themis_lgpd.configuracao`).

    Registrar de novo um tipo idêntico não tem efeito, o que permite repetir o registro em cada
    processo de trabalho de um lote.

    Raises:
        ValueError: Categoria inexistente, código de tipo do catálogo original ou já registrado com
            outra definição.
    """
    if info.categoria not in CATEGORIAS:
        raise ValueError(f"categoria desconhecida {info.categoria!r} no tipo {info.codigo!r}; "
                         f"opções: {', '.join(CATEGORIAS)}")
    atual = TIPOS.get(info.codigo)
    if atual == info:
        return
    if info.codigo in _TIPOS_ORIGINAIS or atual is not None:
        raise ValueError(f"o tipo {info.codigo!r} já existe no catálogo; escolha outro código")
    TIPOS[info.codigo] = info
