"""Regras de negócio do sistema de empréstimo de livros.

O serviço recebe o `db` por injeção de dependência: em produção vem do
db.get_db(); nos testes, de um banco em memória (mongomock) ou de teste.

Todas as operações que dependem do "hoje" aceitam o parâmetro `hoje`,
para permitir testar atrasos sem esperar dias.
"""

import re
from datetime import date, datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from exceptions import (
    AlunoComAtraso,
    AlunoJaCadastrado,
    AlunoNaoEncontrado,
    DadosInvalidos,
    EmailInvalido,
    EmprestimoJaDevolvido,
    EmprestimoNaoEncontrado,
    LimiteEmprestimos,
    LivroComEmprestimoAberto,
    LivroIndisponivel,
    LivroJaCadastrado,
    LivroNaoEncontrado,
)

PRAZO_DIAS = 7
LIMITE_EMPRESTIMOS = 3
MULTA_POR_DIA = 2.00
MS_POR_DIA = 24 * 60 * 60 * 1000

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+$")
CAMPOS_ATUALIZAVEIS = {"titulo", "autor", "ano", "categoria", "exemplares_total"}
COLLATION_PT = {"locale": "pt", "strength": 1}  # ignora maiúsculas e acentos na ordenação


def normalizar_data(hoje: date | datetime | None = None) -> datetime:
    """Converte para datetime à meia-noite.

    O MongoDB não tem tipo "só data", então guardamos tudo como datetime
    00:00. Assim, atraso e multa são contados em dias inteiros.
    """
    if hoje is None:
        hoje = date.today()
    if isinstance(hoje, datetime):
        hoje = hoje.date()
    return datetime(hoje.year, hoje.month, hoje.day)


class BibliotecaService:
    def __init__(self, db, usar_collation: bool = True):
        self.livros = db.livros
        self.alunos = db.alunos
        self.emprestimos = db.emprestimos
        # O mongomock (usado nos testes) não implementa collation
        self.usar_collation = usar_collation

    # ======================================================================
    # Validações auxiliares
    # ======================================================================
    @staticmethod
    def _texto(valor, campo: str) -> str:
        if valor is None or not str(valor).strip():
            raise DadosInvalidos(f"O campo '{campo}' é obrigatório.")
        return str(valor).strip()

    @staticmethod
    def _inteiro(valor, campo: str, minimo: int | None = None) -> int:
        try:
            numero = int(valor)
        except (TypeError, ValueError):
            raise DadosInvalidos(f"O campo '{campo}' deve ser um número inteiro.")
        if minimo is not None and numero < minimo:
            raise DadosInvalidos(f"O campo '{campo}' deve ser no mínimo {minimo}.")
        return numero

    @staticmethod
    def _object_id(emprestimo_id) -> ObjectId:
        try:
            return ObjectId(str(emprestimo_id))
        except (InvalidId, TypeError):
            raise EmprestimoNaoEncontrado(f"Id de empréstimo inválido: {emprestimo_id}.")

    def _ordenar_por_titulo(self, cursor):
        cursor = cursor.sort("titulo", 1)
        return cursor.collation(COLLATION_PT) if self.usar_collation else cursor

    @staticmethod
    def _emprestimo_para_dict(emp: dict) -> dict:
        emp = dict(emp)
        emp["id"] = str(emp.pop("_id"))
        return emp

    # ======================================================================
    # R1 — CRUD de livros
    # ======================================================================
    def cadastrar_livro(self, isbn, titulo, autor, ano, categoria, exemplares_total) -> dict:
        total = self._inteiro(exemplares_total, "exemplares_total", minimo=1)
        livro = {
            "isbn": self._texto(isbn, "isbn"),
            "titulo": self._texto(titulo, "titulo"),
            "autor": self._texto(autor, "autor"),
            "ano": self._inteiro(ano, "ano"),
            "categoria": self._texto(categoria, "categoria"),
            "exemplares_total": total,
            "exemplares_disponiveis": total,
        }
        try:
            self.livros.insert_one(livro)
        except DuplicateKeyError:
            # Quem garante a unicidade é o índice único, não um find_one antes
            raise LivroJaCadastrado(f"Já existe livro com o ISBN {livro['isbn']}.")
        livro.pop("_id", None)
        return livro

    def buscar_livro(self, isbn) -> dict:
        livro = self.livros.find_one({"isbn": str(isbn).strip()}, {"_id": 0})
        if not livro:
            raise LivroNaoEncontrado(f"Livro com ISBN {isbn} não encontrado.")
        return livro

    def listar_livros(self) -> list[dict]:
        return list(self._ordenar_por_titulo(self.livros.find({}, {"_id": 0})))

    def atualizar_livro(self, isbn, /, **campos) -> dict:
        invalidos = set(campos) - CAMPOS_ATUALIZAVEIS
        if invalidos:
            raise DadosInvalidos(f"Campos não podem ser alterados: {', '.join(sorted(invalidos))}.")
        if not campos:
            raise DadosInvalidos("Nenhum campo para atualizar.")

        atual = self.buscar_livro(isbn)
        set_campos = {}
        for campo in ("titulo", "autor", "categoria"):
            if campo in campos:
                set_campos[campo] = self._texto(campos[campo], campo)
        if "ano" in campos:
            set_campos["ano"] = self._inteiro(campos["ano"], "ano")

        filtro = {"isbn": atual["isbn"]}
        update = {}
        if set_campos:
            update["$set"] = set_campos

        if "exemplares_total" in campos:
            novo_total = self._inteiro(campos["exemplares_total"], "exemplares_total", minimo=1)
            delta = novo_total - atual["exemplares_total"]
            if delta:
                # Total e disponíveis mudam juntos, de forma atômica. O filtro
                # garante que não se reduza abaixo do que já está emprestado
                # (e que ninguém alterou o total no meio do caminho).
                filtro["exemplares_total"] = atual["exemplares_total"]
                if delta < 0:
                    filtro["exemplares_disponiveis"] = {"$gte": -delta}
                update["$inc"] = {"exemplares_total": delta, "exemplares_disponiveis": delta}

        if update:
            resultado = self.livros.update_one(filtro, update)
            if resultado.matched_count == 0:
                raise DadosInvalidos(
                    "Não é possível reduzir o total para menos que os exemplares emprestados."
                )
        return self.buscar_livro(atual["isbn"])

    def remover_livro(self, isbn) -> None:
        isbn = str(isbn).strip()
        self.buscar_livro(isbn)
        if self.emprestimos.count_documents({"isbn": isbn, "data_devolucao": None}, limit=1):
            raise LivroComEmprestimoAberto(
                f"O livro {isbn} tem empréstimo em aberto e não pode ser removido."
            )
        self.livros.delete_one({"isbn": isbn})

    # ======================================================================
    # R2 — Cadastro de alunos
    # ======================================================================
    def cadastrar_aluno(self, matricula, nome, curso, email) -> dict:
        email = self._texto(email, "email").lower()
        if not EMAIL_REGEX.match(email):
            raise EmailInvalido(f"E-mail inválido: {email} (precisa conter '@').")
        aluno = {
            "matricula": self._texto(matricula, "matricula"),
            "nome": self._texto(nome, "nome"),
            "curso": self._texto(curso, "curso"),
            "email": email,
        }
        try:
            self.alunos.insert_one(aluno)
        except DuplicateKeyError:
            raise AlunoJaCadastrado(f"Já existe aluno com a matrícula {aluno['matricula']}.")
        aluno.pop("_id", None)
        return aluno

    def buscar_aluno(self, matricula) -> dict:
        aluno = self.alunos.find_one({"matricula": str(matricula).strip()}, {"_id": 0})
        if not aluno:
            raise AlunoNaoEncontrado(f"Aluno com matrícula {matricula} não encontrado.")
        return aluno

    def listar_alunos(self) -> list[dict]:
        return list(self.alunos.find({}, {"_id": 0}).sort("nome", 1))

    # ======================================================================
    # R3 — Busca de livros
    # ======================================================================
    def pesquisar_livros(self, termo: str | None = None, categoria: str | None = None) -> list[dict]:
        filtro = {}
        if termo and termo.strip():
            # re.escape evita que caracteres como "(" ou "." virem regex
            padrao = {"$regex": re.escape(termo.strip()), "$options": "i"}
            filtro["$or"] = [{"titulo": padrao}, {"autor": padrao}]
        if categoria and categoria.strip():
            filtro["categoria"] = {"$regex": f"^{re.escape(categoria.strip())}$", "$options": "i"}
        return list(self._ordenar_por_titulo(self.livros.find(filtro, {"_id": 0})))

    # ======================================================================
    # R4 — Emprestar livro
    # ======================================================================
    def emprestar(self, isbn, matricula, hoje: date | datetime | None = None) -> dict:
        hoje = normalizar_data(hoje)
        isbn, matricula = str(isbn).strip(), str(matricula).strip()

        self.buscar_aluno(matricula)
        self.buscar_livro(isbn)

        atrasados = self.emprestimos.count_documents(
            {"matricula": matricula, "data_devolucao": None, "data_prevista": {"$lt": hoje}},
            limit=1,
        )
        if atrasados:
            raise AlunoComAtraso(f"O aluno {matricula} tem empréstimo atrasado.")

        abertos = self.emprestimos.count_documents({"matricula": matricula, "data_devolucao": None})
        if abertos >= LIMITE_EMPRESTIMOS:
            raise LimiteEmprestimos(
                f"O aluno {matricula} já tem {abertos} empréstimos em aberto (máx. {LIMITE_EMPRESTIMOS})."
            )

        # Reserva atômica do exemplar: o filtro "> 0" e o $inc acontecem na
        # mesma operação, então dois empréstimos simultâneos nunca deixam o
        # estoque negativo — um deles simplesmente não encontra o documento.
        reserva = self.livros.update_one(
            {"isbn": isbn, "exemplares_disponiveis": {"$gt": 0}},
            {"$inc": {"exemplares_disponiveis": -1}},
        )
        if reserva.modified_count == 0:
            raise LivroIndisponivel(f"Não há exemplar disponível do livro {isbn}.")

        emprestimo = {
            "isbn": isbn,
            "matricula": matricula,
            "data_emprestimo": hoje,
            "data_prevista": hoje + timedelta(days=PRAZO_DIAS),
            "data_devolucao": None,
            "multa": 0.0,
        }
        try:
            self.emprestimos.insert_one(emprestimo)
        except Exception:
            # Se não conseguiu registrar, devolve o exemplar reservado
            self.livros.update_one({"isbn": isbn}, {"$inc": {"exemplares_disponiveis": 1}})
            raise
        return self._emprestimo_para_dict(emprestimo)

    # ======================================================================
    # R5 — Devolver livro
    # ======================================================================
    def devolver(self, emprestimo_id, hoje: date | datetime | None = None) -> dict:
        hoje = normalizar_data(hoje)
        oid = self._object_id(emprestimo_id)

        emprestimo = self.emprestimos.find_one({"_id": oid})
        if not emprestimo:
            raise EmprestimoNaoEncontrado(f"Empréstimo {emprestimo_id} não encontrado.")
        if emprestimo.get("data_devolucao") is not None:
            raise EmprestimoJaDevolvido(f"O empréstimo {emprestimo_id} já foi devolvido.")
        if hoje < emprestimo["data_emprestimo"]:
            raise DadosInvalidos("A data de devolução não pode ser anterior ao empréstimo.")

        dias_atraso = max(0, (hoje - emprestimo["data_prevista"]).days)
        multa = round(dias_atraso * MULTA_POR_DIA, 2)

        # O filtro data_devolucao=None torna a devolução idempotente: se duas
        # devoluções chegarem juntas, só uma altera o documento.
        resultado = self.emprestimos.update_one(
            {"_id": oid, "data_devolucao": None},
            {"$set": {"data_devolucao": hoje, "multa": multa}},
        )
        if resultado.modified_count == 0:
            raise EmprestimoJaDevolvido(f"O empréstimo {emprestimo_id} já foi devolvido.")

        self.livros.update_one({"isbn": emprestimo["isbn"]}, {"$inc": {"exemplares_disponiveis": 1}})

        emprestimo.update(data_devolucao=hoje, multa=multa, dias_atraso=dias_atraso)
        return self._emprestimo_para_dict(emprestimo)

    def listar_emprestimos(self, matricula=None, somente_abertos: bool = False) -> list[dict]:
        filtro = {}
        if matricula:
            filtro["matricula"] = str(matricula).strip()
        if somente_abertos:
            filtro["data_devolucao"] = None
        cursor = self.emprestimos.find(filtro).sort("data_emprestimo", 1)
        return [self._emprestimo_para_dict(e) for e in cursor]

    # ======================================================================
    # R6 — Relatórios (Aggregation Pipeline)
    # ======================================================================
    def relatorio_mais_emprestados(self, limite: int = 5) -> list[dict]:
        pipeline = [
            {"$group": {"_id": "$isbn", "total": {"$sum": 1}}},
            {"$sort": {"total": -1, "_id": 1}},
            {"$limit": limite},
            {"$lookup": {"from": "livros", "localField": "_id",
                         "foreignField": "isbn", "as": "livro"}},
            {"$unwind": {"path": "$livro", "preserveNullAndEmptyArrays": True}},
            {"$project": {"_id": 0, "isbn": "$_id", "total": 1,
                          "titulo": {"$ifNull": ["$livro.titulo", "(livro removido)"]}}},
        ]
        return list(self.emprestimos.aggregate(pipeline))

    def relatorio_por_curso(self) -> list[dict]:
        pipeline = [
            {"$lookup": {"from": "alunos", "localField": "matricula",
                         "foreignField": "matricula", "as": "aluno"}},
            {"$unwind": "$aluno"},
            {"$group": {"_id": "$aluno.curso", "total": {"$sum": 1}}},
            {"$sort": {"total": -1, "_id": 1}},
            {"$project": {"_id": 0, "curso": "$_id", "total": 1}},
        ]
        return list(self.emprestimos.aggregate(pipeline))

    def relatorio_atrasados(self, hoje: date | datetime | None = None) -> list[dict]:
        hoje = normalizar_data(hoje)
        pipeline = [
            {"$match": {"data_devolucao": None, "data_prevista": {"$lt": hoje}}},
            {"$lookup": {"from": "alunos", "localField": "matricula",
                         "foreignField": "matricula", "as": "aluno"}},
            {"$unwind": "$aluno"},
            {"$lookup": {"from": "livros", "localField": "isbn",
                         "foreignField": "isbn", "as": "livro"}},
            {"$unwind": "$livro"},
            {"$project": {
                "_id": 0,
                "matricula": 1,
                "nome": "$aluno.nome",
                "livro": "$livro.titulo",
                "data_prevista": 1,
                # data - data = milissegundos -> dividimos por ms/dia
                "dias_atraso": {"$toInt": {"$floor": {"$divide": [
                    {"$subtract": [hoje, "$data_prevista"]}, MS_POR_DIA]}}},
            }},
            {"$sort": {"dias_atraso": -1, "nome": 1}},
        ]
        return list(self.emprestimos.aggregate(pipeline))

    def relatorio_total_multas(self) -> float:
        pipeline = [{"$group": {"_id": None, "total": {"$sum": "$multa"}}}]
        resultado = list(self.emprestimos.aggregate(pipeline))
        return round(resultado[0]["total"], 2) if resultado else 0.0
