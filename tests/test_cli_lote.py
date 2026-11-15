"""Lotes na linha de comando: árvore de pastas, paralelismo, manifesto, retomada e códigos de saída."""

import json
from pathlib import Path

import pytest

from themis_lgpd import lote
from themis_lgpd.cli import main

CPF = "529.982.247-25"


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Duas pastas com arquivos de mesmo nome, uma subpasta e um arquivo inválido."""
    ent = tmp_path / "entrada"
    (ent / "a").mkdir(parents=True)
    (ent / "b" / "c").mkdir(parents=True)
    (ent / "a" / "despacho.txt").write_text(f"Requerente com CPF {CPF}.", encoding="utf-8")
    (ent / "b" / "despacho.txt").write_text("Contato: joao.silva@gmail.com", encoding="utf-8")
    (ent / "b" / "c" / "oficio.txt").write_text("RG 1.234.567 SSP/DF", encoding="utf-8")
    (ent / "b" / "c" / "renomeado.pdf").write_text("isto não é um PDF", encoding="utf-8")
    (ent / ".oculto.txt").write_text(f"CPF {CPF}", encoding="utf-8")
    return ent


def _manifesto(caminho: Path) -> list[dict]:
    return [json.loads(linha) for linha in caminho.read_text(encoding="utf-8").splitlines()]


def test_arvore_preservada_sem_colisao_e_manifesto(arvore, tmp_path):
    saida, manifesto = tmp_path / "saida", tmp_path / "custodia.jsonl"
    codigo = main(["anonimizar", str(arvore), "-R", "-o", str(saida), "--manifesto", str(manifesto), "--sem-ner"])
    assert codigo == 1  # o arquivo renomeado é rejeitado; os demais são gerados
    a = (saida / "a" / "despacho_anonimizado.txt").read_text(encoding="utf-8")
    b = (saida / "b" / "despacho_anonimizado.txt").read_text(encoding="utf-8")
    assert CPF not in a and "[CPF]" in a and "[E-MAIL]" in b
    assert (saida / "b" / "c" / "oficio_anonimizado.txt").exists()
    assert not list(saida.rglob("*oculto*"))
    linhas = {item["arquivo"]: item for item in _manifesto(manifesto)}
    assert set(linhas) == {"a/despacho.txt", "b/despacho.txt", "b/c/oficio.txt", "b/c/renomeado.pdf"}
    ok = linhas["a/despacho.txt"]
    assert ok["situacao"] == "ok" and ok["por_tipo"] == {"CPF": 1} and len(ok["sha256_entrada"]) == 64
    assert ok["sha256_saida"] == lote.sha256((saida / "a" / "despacho_anonimizado.txt").read_bytes())
    assert linhas["b/c/renomeado.pdf"]["situacao"] == "rejeitado"


def test_manifesto_nao_contem_conteudo(arvore, tmp_path):
    manifesto = tmp_path / "m.jsonl"
    main(["anonimizar", str(arvore / "a"), "-o", str(tmp_path / "s"), "--manifesto", str(manifesto), "--sem-ner",
          "--permitir", "Termo Secreto"])
    texto = manifesto.read_text(encoding="utf-8")
    assert CPF not in texto and "52998224725" not in texto and "Termo Secreto" not in texto


def test_sem_recursivo_so_le_o_primeiro_nivel(arvore, tmp_path):
    saida = tmp_path / "saida"
    assert main(["anonimizar", str(arvore / "b"), "-o", str(saida), "--sem-ner"]) == 0
    assert [p.name for p in saida.rglob("*.txt")] == ["despacho_anonimizado.txt"]


def test_arquivos_de_mesmo_nome_indicados_um_a_um(arvore, tmp_path):
    saida = tmp_path / "saida"
    assert main(["anonimizar", str(arvore / "a" / "despacho.txt"), str(arvore / "b" / "despacho.txt"),
                 "-o", str(saida), "--sem-ner"]) == 0
    assert (saida / "a" / "despacho_anonimizado.txt").exists() and (saida / "b" / "despacho_anonimizado.txt").exists()


def test_retomada_pula_concluidos_e_refaz_alterados(arvore, tmp_path, capsys):
    saida, manifesto = tmp_path / "saida", tmp_path / "m.jsonl"
    args = ["anonimizar", str(arvore), "-R", "-o", str(saida), "--manifesto", str(manifesto), "--sem-ner"]
    main(args)
    (arvore / "b" / "despacho.txt").write_text("Telefone (61) 99999-8888", encoding="utf-8")
    capsys.readouterr()
    main([*args, "--retomar"])
    err = capsys.readouterr().err
    assert "↷ a/despacho.txt" in err and "✓ b/despacho.txt" in err
    assert "[TELEFONE]" in (saida / "b" / "despacho_anonimizado.txt").read_text(encoding="utf-8")
    # Outra configuração (perfil) invalida a retomada.
    capsys.readouterr()
    main([*args, "--retomar", "--perfil", "maxima"])
    assert "↷" not in capsys.readouterr().err


def test_retomar_exige_manifesto(arvore):
    assert main(["anonimizar", str(arvore), "--retomar"]) == 1


def test_paralelo_produz_o_mesmo_resultado(arvore, tmp_path):
    seq, par = tmp_path / "seq", tmp_path / "par"
    main(["anonimizar", str(arvore), "-R", "-o", str(seq), "--sem-ner"])
    main(["anonimizar", str(arvore), "-R", "-o", str(par), "--sem-ner", "-j", "2"])
    arquivos = sorted(p.relative_to(seq) for p in seq.rglob("*") if p.is_file())
    assert arquivos == sorted(p.relative_to(par) for p in par.rglob("*") if p.is_file())
    for rel in arquivos:
        assert (seq / rel).read_bytes() == (par / rel).read_bytes()


def test_interrupcao_mantem_manifesto_parcial(arvore, tmp_path, monkeypatch):
    original = lote.processar
    chamadas = []

    def interrompe(tarefa):
        chamadas.append(tarefa)
        if len(chamadas) == 2:
            raise KeyboardInterrupt
        return original(tarefa)

    monkeypatch.setattr(lote, "processar", interrompe)
    manifesto = tmp_path / "m.jsonl"
    codigo = main(["anonimizar", str(arvore), "-R", "-o", str(tmp_path / "s"), "--manifesto", str(manifesto), "--sem-ner"])
    assert codigo == 130
    assert len(_manifesto(manifesto)) == 1


def test_codigo_de_saida_e_a_maior_gravidade(arvore, tmp_path, monkeypatch):
    def falha_interna(tarefa):
        if tarefa.relativo.name == "oficio.txt":
            return {"arquivo": "b/c/oficio.txt", "situacao": lote.ERRO, "mensagem": "erro interno (X)"}
        return original(tarefa)

    original = lote.processar
    monkeypatch.setattr(lote, "processar", falha_interna)
    # O erro interno (2) não é rebaixado pelo arquivo rejeitado (1) processado depois.
    assert main(["anonimizar", str(arvore), "-R", "-o", str(tmp_path / "s"), "--sem-ner"]) == 2


def test_relatorio_consolidado_identifica_o_arquivo(arvore, tmp_path):
    rel = tmp_path / "rel.json"
    main(["anonimizar", str(arvore / "a"), str(arvore / "b"), "-o", str(tmp_path / "s"), "-r", str(rel), "--sem-ner"])
    itens = json.loads(rel.read_text(encoding="utf-8"))["itens"]
    assert {i["documento"] for i in itens} == {"a/despacho.txt", "b/despacho.txt"}


def test_cofre_por_arquivo(arvore, tmp_path, monkeypatch):
    monkeypatch.setenv("THEMIS_SENHA_COFRE", "senha-muito-longa-123")
    cofres = tmp_path / "cofres"
    assert main(["anonimizar", str(arvore), "-R", "-o", str(tmp_path / "s"), "--modo", "pseudonimo",
                 "--cofre", str(cofres), "--sem-ner"]) == 1
    assert (cofres / "a" / "despacho.txt.cofre").exists() and (cofres / "b" / "despacho.txt.cofre").exists()


def test_cofre_com_senha_curta_e_recusado(arvore, tmp_path, monkeypatch):
    monkeypatch.setenv("THEMIS_SENHA_COFRE", "curta")
    assert main(["anonimizar", str(arvore / "a"), "--cofre", str(tmp_path / "c"), "--sem-ner"]) == 1


def test_analisar_e_reverter_com_arquivo_inexistente(tmp_path, capsys):
    assert main(["analisar", str(tmp_path / "nao-existe.txt"), "--sem-ner"]) == 1
    assert main(["reverter", str(tmp_path / "x.txt"), str(tmp_path / "x.cofre")]) == 1
    assert "Traceback" not in capsys.readouterr().err


def test_entrada_inexistente(tmp_path):
    assert main(["anonimizar", str(tmp_path / "nao-existe")]) == 1
