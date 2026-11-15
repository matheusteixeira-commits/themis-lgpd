"""Configuração por órgão (themis.toml), perfis de ouvidoria e de educação e agentes públicos."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from themis_lgpd import Anonimizador
from themis_lgpd.cli import main
from themis_lgpd.configuracao import ConfiguracaoInvalida, carregar, interpretar

EXEMPLO = Path(__file__).resolve().parents[1] / "exemplos" / "orgao.toml"


@pytest.fixture(scope="module")
def cfg():
    return carregar(EXEMPLO)


@pytest.fixture(scope="module")
def anon_orgao(cfg):
    return Anonimizador(**cfg.argumentos())


def test_exemplo_carrega(cfg):
    assert cfg.perfil.nome == "ouvidoria_estadual"
    assert cfg.perfil.regras["EMPRESA"] == "manter" and cfg.perfil.regras["LOCALIDADE"] == "tarjar"
    assert "SAUDE" in cfg.perfil.tarjar_sensivel_sempre and len(cfg.padroes) == 2


def test_reconhecedor_proprio_com_tipo_proprio(anon_orgao):
    r = anon_orgao.anonimizar("O adolescente do PSE nº 2024/00123 foi transferido.")
    assert "2024/00123" not in r.texto and "[PRONTUÁRIO]" in r.texto and "PSE" in r.texto
    assert {e.tipo for e in r.tarjadas} >= {"PRONTUARIO_SOCIOEDUCATIVO"}


def test_reconhecedor_proprio_sensivel_a_caixa(cfg, anon_orgao):
    assert "OUV-2024-000123" not in anon_orgao.anonimizar("Manifestação OUV-2024-000123 recebida.").texto
    regra = next(p for p in cfg.padroes if p.nome == "orgao:protocolo-ouvidoria")
    assert regra.detectar("OUV-2024-000123") and not regra.detectar("ouv-2024-000123")


def test_lista_de_permissao_e_cargos_do_orgao(anon_orgao):
    texto = "Participei do Programa Maria da Penha vai à Escola. O inspetor escolar João Pereira Lima respondeu."
    saida = anon_orgao.anonimizar(texto).texto
    assert "Programa Maria da Penha vai à Escola" in saida
    assert "João Pereira Lima" in saida  # cargo do órgão, com preservar_agentes_publicos = true


def test_perfil_do_orgao_tarja_localidade(anon_orgao):
    saida = anon_orgao.anonimizar("Sou servidora em Taguatinga e venho registrar a reclamação.").texto
    assert "Taguatinga" not in saida


def test_linha_de_comando_sobrepoe_a_configuracao(cfg):
    args = cfg.argumentos(perfil="lai", permitir=["Termo Extra"])
    assert args["perfil"] == "lai" and "Termo Extra" in args["permitir"]
    assert "Programa Maria da Penha vai à Escola" in args["permitir"]


@pytest.mark.parametrize("dados,trecho", [
    ({"padrao": {"perfil": "inexistente"}}, "[padrao] perfil"),
    ({"padrao": {"modo": "apagar"}}, "[padrao] modo"),
    ({"padrao": {"campo_errado": 1}}, "campo(s) desconhecido(s): campo_errado"),
    ({"seção": {}}, "[raiz]"),
    ({"tipos": [{"codigo": "X_Y", "nome": "x", "categoria": "INEXISTENTE"}]}, "[tipos nº 1] categoria"),
    ({"tipos": [{"codigo": "minusculo", "nome": "x", "categoria": "DOCUMENTO"}]}, "[tipos nº 1] codigo"),
    ({"reconhecedores": [{"nome": "x", "tipo": "NAO_EXISTE", "regex": "a"}]}, "[reconhecedores nº 1] tipo"),
    ({"reconhecedores": [{"nome": "x", "tipo": "CPF", "regex": "(abc"}]}, "[reconhecedores nº 1] regex"),
    ({"reconhecedores": [{"nome": "x", "tipo": "CPF", "regex": "\\d*"}]}, "aceita texto vazio"),
    ({"reconhecedores": [{"nome": "x", "tipo": "CPF", "regex": "\\d+", "grupo": "v"}]}, "grupo"),
    ({"reconhecedores": [{"nome": "x", "tipo": "CPF", "regex": "\\d+", "validador": "md5"}]}, "validador"),
    ({"reconhecedores": [{"nome": "x", "tipo": "CPF", "regex": "\\d+", "contexto_obrigatorio": True}]},
     "contexto_obrigatorio exige"),
    ({"reconhecedores": [{"nome": "x", "tipo": "CPF", "regex": "\\d+", "score": 2}]}, "score"),
    ({"perfis": {"lai": {"base": "lai"}}}, "já é um perfil do Themis"),
    ({"perfis": {"meu": {"base": "lai", "regras": {"PESSOA": "ocultar"}}}}, "regras.PESSOA"),
    ({"perfis": {"meu": {"base": "lai", "tarjar_sensivel_sempre": ["CPF"]}}}, "tarjar_sensivel_sempre"),
    ({"listas": {"permitir_arquivo": "nao-existe.txt"}}, "[listas] permitir_arquivo"),
])
def test_erros_indicam_secao_e_campo(dados, trecho, tmp_path):
    with pytest.raises(ConfiguracaoInvalida) as erro:
        interpretar(dados, pasta=tmp_path)
    assert trecho in str(erro.value)


def test_toml_malformado(tmp_path):
    arq = tmp_path / "orgao.toml"
    arq.write_text("[padrao\nperfil = 1", encoding="utf-8")
    with pytest.raises(ConfiguracaoInvalida, match="TOML inválido"):
        carregar(arq)


def test_cli_com_configuracao_invalida(tmp_path, capsys):
    arq = tmp_path / "orgao.toml"
    arq.write_text('[padrao]\nperfil = "nenhum"\n', encoding="utf-8")
    txt = tmp_path / "a.txt"
    txt.write_text("CPF 529.982.247-25", encoding="utf-8")
    assert main(["anonimizar", str(txt), "--config", str(arq)]) == 1
    assert "[padrao] perfil" in capsys.readouterr().err


def test_variavel_de_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("THEMIS_CONFIG", str(EXEMPLO))
    assert carregar().perfil.nome == "ouvidoria_estadual"


def test_identificador_estavel_entre_processos():
    """O identificador do manifesto não pode depender da ordem de conjuntos (hash aleatório por processo)."""
    codigo = ("from themis_lgpd.lote import Opcoes; "
              f"print(Opcoes(config={str(EXEMPLO)!r}, sobrepor={{'perfil': 'lai'}}).identificador())")
    valores = set()
    for semente in ("1", "2", "3"):
        env = {**os.environ, "PYTHONHASHSEED": semente}
        valores.add(subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, env=env,  # noqa: S603
                                   check=True).stdout.strip())
    assert len(valores) == 1


# ------------------------------------------------------------------ perfis e agentes públicos
def test_perfil_ouvidoria_protege_identidade_do_manifestante():
    anon = Anonimizador("ouvidoria", usar_ner=False)
    r = anon.anonimizar("Sou atendente do guichê 4 na unidade de Ceilândia, no turno da tarde, e moro em Sobradinho.")
    assert "Ceilândia" not in r.texto and "Sobradinho" not in r.texto and "guichê 4" not in r.texto


def test_perfil_educacao_tarja_ra_e_dados_de_menores():
    anon = Anonimizador("educacao", usar_ner=False)
    r = anon.anonimizar("O aluno, RA 123456789-X, tem 9 anos e cursa o 4º ano. A criança tem asma.")
    assert "123456789-X" not in r.texto and "asma" not in r.texto
    lai = Anonimizador("lai", usar_ner=False).anonimizar("A política escolar prevê atendimento a alunos com asma.")
    edu = anon.anonimizar("A política escolar prevê atendimento a alunos com asma.")
    assert "asma" in lai.texto and "asma" not in edu.texto  # educação: saúde de estudantes sempre tarjada


def test_agente_publico_consistente_em_todas_as_ocorrencias():
    anon = Anonimizador("lai", usar_ner=False, preservar_agentes_publicos=True)
    texto = "A Secretária de Saúde, Maria Aparecida Souza, informou o prazo. Maria Aparecida Souza assinou o ofício."
    r = anon.anonimizar(texto)
    assert r.texto.count("Maria Aparecida Souza") == 2


def test_cargos_extras_so_valem_na_instancia_configurada():
    texto = "O inspetor escolar João Pereira Lima respondeu."
    com = Anonimizador("lai", usar_ner=False, preservar_agentes_publicos=True, cargos=["inspetor escolar"])
    sem = Anonimizador("lai", usar_ner=False, preservar_agentes_publicos=True)
    assert "João Pereira Lima" in com.anonimizar(texto).texto
    assert "João Pereira Lima" not in sem.anonimizar(texto).texto
