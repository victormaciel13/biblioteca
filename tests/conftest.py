"""Fixtures compartilhadas.

Por padrão os testes rodam com mongomock (MongoDB em memória), então não
precisam de banco. Para rodar contra um MongoDB real, defina MONGO_URI_TEST:
    MONGO_URI_TEST=mongodb://localhost:27017 pytest
"""

import os
from datetime import datetime

import mongomock
import pytest
from pymongo import MongoClient

from db import criar_indices
from service import BibliotecaService

NOME_BANCO_TESTE = "biblioteca_test"
HOJE = datetime(2026, 10, 1)

USANDO_MONGO_REAL = bool(os.getenv("MONGO_URI_TEST"))


@pytest.fixture
def db():
    if USANDO_MONGO_REAL:
        client = MongoClient(os.environ["MONGO_URI_TEST"])
        client.drop_database(NOME_BANCO_TESTE)
    else:
        client = mongomock.MongoClient()
    database = client[NOME_BANCO_TESTE]
    criar_indices(database)
    yield database
    if USANDO_MONGO_REAL:
        client.drop_database(NOME_BANCO_TESTE)
    client.close()


@pytest.fixture
def service(db):
    # mongomock não implementa collation; no Mongo real ela fica ligada
    return BibliotecaService(db, usar_collation=USANDO_MONGO_REAL)


@pytest.fixture
def hoje():
    return HOJE


@pytest.fixture
def acervo(service):
    """Acervo e alunos básicos usados pela maioria dos testes."""
    service.cadastrar_livro("111", "Dom Casmurro", "Machado de Assis", 1899, "Romance", 2)
    service.cadastrar_livro("222", "Python Fluente", "Luciano Ramalho", 2015, "Computação", 3)
    service.cadastrar_livro("333", "Código Limpo", "Robert C. Martin", 2008, "Computação", 1)
    service.cadastrar_livro("444", "Memórias Póstumas de Brás Cubas", "Machado de Assis", 1881, "Romance", 2)
    service.cadastrar_aluno("RM1", "Ana Souza", "Engenharia de Software", "ana@fiap.com.br")
    service.cadastrar_aluno("RM2", "Bruno Lima", "Sistemas de Informação", "bruno@fiap.com.br")
    service.cadastrar_aluno("RM3", "Carla Mendes", "Engenharia de Software", "carla@fiap.com.br")
    return service
