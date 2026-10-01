"""R4 — Emprestar livro."""

from datetime import timedelta

import pytest

from exceptions import (
    AlunoComAtraso,
    AlunoNaoEncontrado,
    LimiteEmprestimos,
    LivroIndisponivel,
    LivroNaoEncontrado,
)
from service import LIMITE_EMPRESTIMOS, PRAZO_DIAS


def test_emprestimo_decrementa_estoque_e_define_prazo(acervo, hoje):
    emp = acervo.emprestar("222", "RM1", hoje=hoje)
    assert acervo.buscar_livro("222")["exemplares_disponiveis"] == 2
    assert emp["data_emprestimo"] == hoje
    assert emp["data_prevista"] == hoje + timedelta(days=PRAZO_DIAS)
    assert emp["data_devolucao"] is None
    assert emp["multa"] == 0


def test_prazo_e_de_7_dias(acervo, hoje):
    emp = acervo.emprestar("222", "RM1", hoje=hoje)
    assert (emp["data_prevista"] - emp["data_emprestimo"]).days == 7


def test_sem_exemplar_disponivel(acervo, hoje):
    acervo.emprestar("333", "RM1", hoje=hoje)  # único exemplar
    with pytest.raises(LivroIndisponivel):
        acervo.emprestar("333", "RM2", hoje=hoje)
    assert acervo.buscar_livro("333")["exemplares_disponiveis"] == 0


def test_estoque_nunca_fica_negativo(acervo, hoje):
    for matricula in ("RM1", "RM2"):
        acervo.emprestar("111", matricula, hoje=hoje)  # 2 exemplares
    with pytest.raises(LivroIndisponivel):
        acervo.emprestar("111", "RM3", hoje=hoje)
    assert acervo.buscar_livro("111")["exemplares_disponiveis"] == 0


def test_update_atomico_usa_filtro_maior_que_zero(acervo):
    """Simula a 'corrida': o update só casa se ainda houver exemplar."""
    acervo.livros.update_one({"isbn": "333"}, {"$set": {"exemplares_disponiveis": 0}})
    resultado = acervo.livros.update_one(
        {"isbn": "333", "exemplares_disponiveis": {"$gt": 0}},
        {"$inc": {"exemplares_disponiveis": -1}},
    )
    assert resultado.modified_count == 0


def test_limite_de_3_emprestimos_abertos(acervo, hoje):
    for isbn in ("111", "222", "444"):
        acervo.emprestar(isbn, "RM1", hoje=hoje)
    with pytest.raises(LimiteEmprestimos):
        acervo.emprestar("333", "RM1", hoje=hoje)
    assert len(acervo.listar_emprestimos("RM1", somente_abertos=True)) == LIMITE_EMPRESTIMOS
    assert acervo.buscar_livro("333")["exemplares_disponiveis"] == 1  # não reservou


def test_devolver_libera_vaga_no_limite(acervo, hoje):
    emps = [acervo.emprestar(isbn, "RM1", hoje=hoje) for isbn in ("111", "222", "444")]
    acervo.devolver(emps[0]["id"], hoje=hoje)
    acervo.emprestar("333", "RM1", hoje=hoje)


def test_aluno_com_atraso_nao_pega_outro_livro(acervo, hoje):
    acervo.emprestar("111", "RM1", hoje=hoje)
    depois_do_prazo = hoje + timedelta(days=PRAZO_DIAS + 1)
    with pytest.raises(AlunoComAtraso):
        acervo.emprestar("222", "RM1", hoje=depois_do_prazo)


def test_no_ultimo_dia_do_prazo_ainda_nao_esta_atrasado(acervo, hoje):
    acervo.emprestar("111", "RM1", hoje=hoje)
    acervo.emprestar("222", "RM1", hoje=hoje + timedelta(days=PRAZO_DIAS))


def test_aluno_ou_livro_inexistente(acervo, hoje):
    with pytest.raises(AlunoNaoEncontrado):
        acervo.emprestar("111", "RM999", hoje=hoje)
    with pytest.raises(LivroNaoEncontrado):
        acervo.emprestar("999", "RM1", hoje=hoje)


@pytest.mark.skipif(
    not __import__("os").getenv("MONGO_URI_TEST"),
    reason="Concorrência real só faz sentido contra um MongoDB de verdade",
)
def test_concorrencia_real_nao_deixa_estoque_negativo(service, hoje):
    """20 alunos tentam pegar o único exemplar ao mesmo tempo: só 1 consegue."""
    from concurrent.futures import ThreadPoolExecutor

    service.cadastrar_livro("777", "Livro Disputado", "Autor", 2020, "Teste", 1)
    for i in range(20):
        service.cadastrar_aluno(f"C{i}", f"Aluno {i}", "Curso", f"c{i}@fiap.com")

    def tentar(i):
        try:
            service.emprestar("777", f"C{i}", hoje=hoje)
            return True
        except LivroIndisponivel:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        sucessos = sum(pool.map(tentar, range(20)))

    assert sucessos == 1
    assert service.buscar_livro("777")["exemplares_disponiveis"] == 0
    assert service.emprestimos.count_documents({"isbn": "777"}) == 1
