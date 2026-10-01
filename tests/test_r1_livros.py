"""R1 — CRUD de livros."""

import pytest

from exceptions import (
    DadosInvalidos,
    LivroComEmprestimoAberto,
    LivroJaCadastrado,
    LivroNaoEncontrado,
)


def test_cadastrar_e_buscar_livro_por_isbn(service):
    service.cadastrar_livro("123", "Duna", "Frank Herbert", 1965, "Ficção", 2)
    livro = service.buscar_livro("123")
    assert livro["titulo"] == "Duna"
    assert livro["exemplares_total"] == 2
    assert livro["exemplares_disponiveis"] == 2
    assert "_id" not in livro


def test_isbn_duplicado_e_barrado_pelo_indice_unico(service):
    service.cadastrar_livro("123", "Duna", "Frank Herbert", 1965, "Ficção", 2)
    with pytest.raises(LivroJaCadastrado):
        service.cadastrar_livro("123", "Outro", "Outro Autor", 2000, "Ficção", 1)
    assert service.livros.count_documents({"isbn": "123"}) == 1


def test_indice_unico_de_isbn_existe(db):
    indices = db.livros.index_information()
    assert indices["uk_livros_isbn"]["unique"] is True


def test_buscar_livro_inexistente(service):
    with pytest.raises(LivroNaoEncontrado):
        service.buscar_livro("999")


def test_cadastro_com_dados_invalidos(service):
    with pytest.raises(DadosInvalidos):
        service.cadastrar_livro("", "Sem ISBN", "Autor", 2000, "X", 1)
    with pytest.raises(DadosInvalidos):
        service.cadastrar_livro("1", "Livro", "Autor", 2000, "X", 0)


def test_listar_livros_ordenados_por_titulo(acervo):
    titulos = [l["titulo"] for l in acervo.listar_livros()]
    assert titulos == sorted(titulos)
    assert len(titulos) == 4


def test_atualizar_livro(acervo):
    livro = acervo.atualizar_livro("111", titulo="Dom Casmurro (ed. revisada)", ano=2020)
    assert livro["titulo"] == "Dom Casmurro (ed. revisada)"
    assert livro["ano"] == 2020


def test_atualizar_total_ajusta_disponiveis(acervo, hoje):
    acervo.emprestar("222", "RM1", hoje=hoje)  # 3 total, 2 disponíveis
    livro = acervo.atualizar_livro("222", exemplares_total=5)
    assert livro["exemplares_total"] == 5
    assert livro["exemplares_disponiveis"] == 4


def test_nao_reduz_total_abaixo_dos_emprestados(acervo, hoje):
    acervo.emprestar("111", "RM1", hoje=hoje)
    acervo.emprestar("111", "RM2", hoje=hoje)  # os 2 exemplares emprestados
    with pytest.raises(DadosInvalidos):
        acervo.atualizar_livro("111", exemplares_total=1)


def test_nao_permite_alterar_isbn_nem_disponiveis_diretamente(acervo):
    with pytest.raises(DadosInvalidos):
        acervo.atualizar_livro("111", isbn="novo")
    with pytest.raises(DadosInvalidos):
        acervo.atualizar_livro("111", exemplares_disponiveis=99)


def test_remover_livro(acervo):
    acervo.remover_livro("333")
    with pytest.raises(LivroNaoEncontrado):
        acervo.buscar_livro("333")


def test_nao_remove_livro_com_emprestimo_aberto(acervo, hoje):
    acervo.emprestar("333", "RM1", hoje=hoje)
    with pytest.raises(LivroComEmprestimoAberto):
        acervo.remover_livro("333")
    assert acervo.buscar_livro("333")


def test_remove_livro_depois_da_devolucao(acervo, hoje):
    emp = acervo.emprestar("333", "RM1", hoje=hoje)
    acervo.devolver(emp["id"], hoje=hoje)
    acervo.remover_livro("333")
    with pytest.raises(LivroNaoEncontrado):
        acervo.buscar_livro("333")
