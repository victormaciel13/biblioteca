"""R3 — Busca de livros."""


def titulos(livros):
    return [l["titulo"] for l in livros]


def test_busca_por_parte_do_titulo_sem_diferenciar_maiusculas(acervo):
    assert titulos(acervo.pesquisar_livros("PYTHON")) == ["Python Fluente"]
    assert titulos(acervo.pesquisar_livros("casmu")) == ["Dom Casmurro"]


def test_busca_por_autor(acervo):
    resultado = titulos(acervo.pesquisar_livros("machado"))
    assert resultado == ["Dom Casmurro", "Memórias Póstumas de Brás Cubas"]


def test_filtro_por_categoria(acervo):
    resultado = titulos(acervo.pesquisar_livros(categoria="computação"))
    assert resultado == ["Código Limpo", "Python Fluente"]


def test_termo_e_categoria_combinados(acervo):
    assert titulos(acervo.pesquisar_livros("machado", "Computação")) == []
    assert titulos(acervo.pesquisar_livros("martin", "Computação")) == ["Código Limpo"]


def test_resultados_ordenados_por_titulo(acervo):
    resultado = titulos(acervo.pesquisar_livros())
    assert resultado == sorted(resultado)


def test_termo_com_caracteres_especiais_nao_quebra_a_regex(acervo):
    assert acervo.pesquisar_livros("(") == []
    assert acervo.pesquisar_livros(".*") == []
