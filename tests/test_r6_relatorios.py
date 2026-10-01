"""R6 — Relatórios com Aggregation Pipeline."""

from datetime import timedelta

import pytest


@pytest.fixture
def historico(acervo, hoje):
    """Cria um histórico de empréstimos e devoluções variado."""
    # Python Fluente: 3 empréstimos | Dom Casmurro: 2 | Código Limpo: 1
    e1 = acervo.emprestar("222", "RM1", hoje=hoje)
    e2 = acervo.emprestar("222", "RM2", hoje=hoje)
    acervo.devolver(e1["id"], hoje=hoje + timedelta(days=10))  # 3 dias -> R$ 6
    acervo.devolver(e2["id"], hoje=hoje + timedelta(days=9))   # 2 dias -> R$ 4
    acervo.emprestar("222", "RM3", hoje=hoje)                  # aberto

    acervo.emprestar("111", "RM1", hoje=hoje)                  # aberto
    acervo.emprestar("111", "RM2", hoje=hoje + timedelta(days=3))  # aberto
    acervo.emprestar("333", "RM3", hoje=hoje)                  # aberto
    return acervo


def test_top_5_mais_emprestados(historico):
    top = historico.relatorio_mais_emprestados()
    assert [(l["titulo"], l["total"]) for l in top] == [
        ("Python Fluente", 3),
        ("Dom Casmurro", 2),
        ("Código Limpo", 1),
    ]


def test_top_respeita_limite_de_5(acervo, hoje):
    for i in range(7):
        acervo.cadastrar_livro(f"X{i}", f"Livro {i}", "Autor", 2000, "Teste", 1)
        acervo.cadastrar_aluno(f"T{i}", f"Aluno {i}", "Curso", f"t{i}@fiap.com")
        acervo.emprestar(f"X{i}", f"T{i}", hoje=hoje)
    assert len(acervo.relatorio_mais_emprestados()) == 5


def test_emprestimos_por_curso(historico):
    por_curso = {l["curso"]: l["total"] for l in historico.relatorio_por_curso()}
    # RM1 e RM3 -> Engenharia de Software (4) | RM2 -> Sistemas de Informação (2)
    assert por_curso == {"Engenharia de Software": 4, "Sistemas de Informação": 2}


def test_alunos_com_atraso(historico, hoje):
    atrasados = historico.relatorio_atrasados(hoje=hoje + timedelta(days=12))
    linhas = {(l["nome"], l["livro"], l["dias_atraso"]) for l in atrasados}
    assert linhas == {
        ("Carla Mendes", "Python Fluente", 5),
        ("Ana Souza", "Dom Casmurro", 5),
        ("Bruno Lima", "Dom Casmurro", 2),
        ("Carla Mendes", "Código Limpo", 5),
    }
    # ordenado do maior atraso para o menor
    dias = [l["dias_atraso"] for l in atrasados]
    assert dias == sorted(dias, reverse=True)


def test_sem_atrasos_dentro_do_prazo(historico, hoje):
    assert historico.relatorio_atrasados(hoje=hoje + timedelta(days=7)) == []


def test_total_arrecadado_em_multas(historico):
    assert historico.relatorio_total_multas() == 10.00


def test_total_multas_sem_emprestimos(service):
    assert service.relatorio_total_multas() == 0.0
