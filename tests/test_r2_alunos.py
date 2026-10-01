"""R2 — Cadastro de alunos."""

import pytest

from exceptions import AlunoJaCadastrado, AlunoNaoEncontrado, EmailInvalido


def test_cadastrar_e_buscar_aluno(service):
    service.cadastrar_aluno("RM10", "Davi Rocha", "ADS", "Davi@FIAP.com.br")
    aluno = service.buscar_aluno("RM10")
    assert aluno["nome"] == "Davi Rocha"
    assert aluno["email"] == "davi@fiap.com.br"  # normalizado em minúsculas


def test_matricula_duplicada(service):
    service.cadastrar_aluno("RM10", "Davi Rocha", "ADS", "davi@fiap.com.br")
    with pytest.raises(AlunoJaCadastrado):
        service.cadastrar_aluno("RM10", "Outra Pessoa", "ADS", "outra@fiap.com.br")


def test_indice_unico_de_matricula_existe(db):
    assert db.alunos.index_information()["uk_alunos_matricula"]["unique"] is True


@pytest.mark.parametrize("email", ["davifiap.com.br", "@fiap.com.br", "davi@", "da vi@fiap.com"])
def test_email_invalido(service, email):
    with pytest.raises(EmailInvalido):
        service.cadastrar_aluno("RM10", "Davi Rocha", "ADS", email)
    assert service.alunos.count_documents({}) == 0


def test_buscar_aluno_inexistente(service):
    with pytest.raises(AlunoNaoEncontrado):
        service.buscar_aluno("RM404")
