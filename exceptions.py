"""Exceções de negócio do sistema de biblioteca.

Todas herdam de BibliotecaErro, assim o menu (main.py) consegue tratar
qualquer erro de regra de negócio com um único `except`.
"""


class BibliotecaErro(Exception):
    """Base de todos os erros de negócio."""


# --- Validação ---------------------------------------------------------------
class DadosInvalidos(BibliotecaErro):
    """Algum campo obrigatório veio vazio ou com valor inválido."""


class EmailInvalido(DadosInvalidos):
    """E-mail sem '@' (ou em formato claramente inválido)."""


# --- Livros ------------------------------------------------------------------
class LivroJaCadastrado(BibliotecaErro):
    """Já existe um livro com o mesmo ISBN (violação do índice único)."""


class LivroNaoEncontrado(BibliotecaErro):
    """Nenhum livro com o ISBN informado."""


class LivroComEmprestimoAberto(BibliotecaErro):
    """Tentativa de remover um livro que ainda tem exemplar emprestado."""


class LivroIndisponivel(BibliotecaErro):
    """Não há exemplar disponível para empréstimo."""


# --- Alunos ------------------------------------------------------------------
class AlunoJaCadastrado(BibliotecaErro):
    """Já existe um aluno com a mesma matrícula."""


class AlunoNaoEncontrado(BibliotecaErro):
    """Nenhum aluno com a matrícula informada."""


class LimiteEmprestimos(BibliotecaErro):
    """O aluno já tem o máximo de empréstimos em aberto."""


class AlunoComAtraso(BibliotecaErro):
    """O aluno tem empréstimo atrasado e não pode pegar outro livro."""


# --- Empréstimos ---------------------------------------------------------------
class EmprestimoNaoEncontrado(BibliotecaErro):
    """Nenhum empréstimo com o id informado."""


class EmprestimoJaDevolvido(BibliotecaErro):
    """O empréstimo já foi devolvido anteriormente."""
