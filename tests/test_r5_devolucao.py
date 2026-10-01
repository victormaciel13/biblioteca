"""R5 — Devolver livro."""

from datetime import timedelta

import pytest

from exceptions import DadosInvalidos, EmprestimoJaDevolvido, EmprestimoNaoEncontrado


def test_devolucao_no_prazo_sem_multa(acervo, hoje):
    emp = acervo.emprestar("222", "RM1", hoje=hoje)
    devolvido = acervo.devolver(emp["id"], hoje=hoje + timedelta(days=7))
    assert devolvido["data_devolucao"] == hoje + timedelta(days=7)
    assert devolvido["multa"] == 0
    assert acervo.buscar_livro("222")["exemplares_disponiveis"] == 3


def test_devolucao_atrasada_gera_multa_de_2_reais_por_dia(acervo, hoje):
    emp = acervo.emprestar("222", "RM1", hoje=hoje)
    devolvido = acervo.devolver(emp["id"], hoje=hoje + timedelta(days=12))  # 5 dias de atraso
    assert devolvido["dias_atraso"] == 5
    assert devolvido["multa"] == 10.00
    salvo = acervo.emprestimos.find_one({"isbn": "222"})
    assert salvo["multa"] == 10.00


def test_devolver_duas_vezes_gera_erro(acervo, hoje):
    emp = acervo.emprestar("222", "RM1", hoje=hoje)
    acervo.devolver(emp["id"], hoje=hoje)
    with pytest.raises(EmprestimoJaDevolvido):
        acervo.devolver(emp["id"], hoje=hoje)
    # o estoque não pode ter sido incrementado duas vezes
    assert acervo.buscar_livro("222")["exemplares_disponiveis"] == 3


def test_devolver_emprestimo_inexistente(acervo, hoje):
    with pytest.raises(EmprestimoNaoEncontrado):
        acervo.devolver("0123456789abcdef01234567", hoje=hoje)
    with pytest.raises(EmprestimoNaoEncontrado):
        acervo.devolver("id-invalido", hoje=hoje)


def test_devolucao_antes_do_emprestimo_e_invalida(acervo, hoje):
    emp = acervo.emprestar("222", "RM1", hoje=hoje)
    with pytest.raises(DadosInvalidos):
        acervo.devolver(emp["id"], hoje=hoje - timedelta(days=1))


def test_devolucao_libera_aluno_com_atraso(acervo, hoje):
    emp = acervo.emprestar("111", "RM1", hoje=hoje)
    depois = hoje + timedelta(days=10)
    acervo.devolver(emp["id"], hoje=depois)
    acervo.emprestar("222", "RM1", hoje=depois)
