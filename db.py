"""Camada de acesso ao banco: conexão com o MongoDB e criação dos índices."""

import os

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "biblioteca")


def get_client(uri: str | None = None) -> MongoClient:
    """Cria o cliente. O timeout curto faz o erro aparecer logo se o Mongo estiver fora."""
    return MongoClient(uri or MONGO_URI, serverSelectionTimeoutMS=5000)


def get_db(client: MongoClient | None = None, nome: str | None = None) -> Database:
    """Retorna o banco já com os índices garantidos."""
    client = client or get_client()
    db = client[nome or MONGO_DB]
    criar_indices(db)
    return db


def criar_indices(db: Database) -> None:
    """Cria os índices (operação idempotente: pode rodar a cada inicialização)."""
    # Unicidade garantida pelo próprio banco (R1 e R2)
    db.livros.create_index([("isbn", ASCENDING)], unique=True, name="uk_livros_isbn")
    db.alunos.create_index([("matricula", ASCENDING)], unique=True, name="uk_alunos_matricula")

    # Apoio às buscas e listagens ordenadas (R3)
    db.livros.create_index([("titulo", ASCENDING)], name="ix_livros_titulo")
    db.livros.create_index([("categoria", ASCENDING)], name="ix_livros_categoria")

    # Consultas frequentes de empréstimos em aberto / atrasados (R1, R4, R6)
    db.emprestimos.create_index(
        [("matricula", ASCENDING), ("data_devolucao", ASCENDING)], name="ix_emp_aluno_aberto"
    )
    db.emprestimos.create_index(
        [("isbn", ASCENDING), ("data_devolucao", ASCENDING)], name="ix_emp_livro_aberto"
    )
    db.emprestimos.create_index(
        [("data_devolucao", ASCENDING), ("data_prevista", ASCENDING)], name="ix_emp_atrasos"
    )
