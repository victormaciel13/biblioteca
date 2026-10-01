"""Popula o banco com dados de exemplo para demonstração. Uso: python seed.py"""

from db import get_db
from exceptions import BibliotecaErro
from service import BibliotecaService

LIVROS = [
    ("978-85-359-0277-5", "Dom Casmurro", "Machado de Assis", 1899, "Romance", 3),
    ("978-85-7232-144-9", "Memórias Póstumas de Brás Cubas", "Machado de Assis", 1881, "Romance", 2),
    ("978-85-216-1938-6", "Estruturas de Dados e Algoritmos em Python", "Michael Goodrich", 2013, "Computação", 2),
    ("978-85-7522-408-3", "Python Fluente", "Luciano Ramalho", 2015, "Computação", 4),
    ("978-85-508-0460-6", "Código Limpo", "Robert C. Martin", 2008, "Computação", 1),
    ("978-85-352-1105-9", "Sistemas de Banco de Dados", "Ramez Elmasri", 2011, "Banco de Dados", 2),
]
ALUNOS = [
    ("RM1001", "Ana Souza", "Engenharia de Software", "ana@fiap.com.br"),
    ("RM1002", "Bruno Lima", "Sistemas de Informação", "bruno@fiap.com.br"),
    ("RM1003", "Carla Mendes", "Engenharia de Software", "carla@fiap.com.br"),
]

if __name__ == "__main__":
    service = BibliotecaService(get_db())
    for dados in LIVROS:
        try:
            service.cadastrar_livro(*dados)
        except BibliotecaErro as erro:
            print(f"Ignorado: {erro}")
    for dados in ALUNOS:
        try:
            service.cadastrar_aluno(*dados)
        except BibliotecaErro as erro:
            print(f"Ignorado: {erro}")
    print("Dados de exemplo carregados.")
