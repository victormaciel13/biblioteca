"""Menu de terminal do sistema de biblioteca (R7)."""

from datetime import datetime

from pymongo.errors import PyMongoError

from db import get_db
from exceptions import BibliotecaErro
from service import BibliotecaService, normalizar_data


# ---------------------------------------------------------------------------
# Helpers de entrada e saída
# ---------------------------------------------------------------------------
def ler(rotulo: str, opcional: bool = False) -> str | None:
    valor = input(f"{rotulo}: ").strip()
    return valor or (None if opcional else valor)


def ler_data(rotulo: str) -> datetime:
    while True:
        texto = input(f"{rotulo} (dd/mm/aaaa): ").strip()
        try:
            return datetime.strptime(texto, "%d/%m/%Y")
        except ValueError:
            print("  Data inválida, tente de novo.")


def fmt_data(valor) -> str:
    return valor.strftime("%d/%m/%Y") if valor else "-"


def mostrar_livros(livros: list[dict]) -> None:
    if not livros:
        print("  Nenhum livro encontrado.")
        return
    for l in livros:
        print(f"  [{l['isbn']}] {l['titulo']} — {l['autor']} ({l['ano']}) | {l['categoria']} | "
              f"disponíveis {l['exemplares_disponiveis']}/{l['exemplares_total']}")


def mostrar_emprestimos(emprestimos: list[dict]) -> None:
    if not emprestimos:
        print("  Nenhum empréstimo encontrado.")
        return
    for e in emprestimos:
        print(f"  id {e['id']} | ISBN {e['isbn']} | emprestado {fmt_data(e['data_emprestimo'])} | "
              f"previsto {fmt_data(e['data_prevista'])} | devolvido {fmt_data(e['data_devolucao'])} | "
              f"multa R$ {e['multa']:.2f}")


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
class Menu:
    def __init__(self, service: BibliotecaService):
        self.s = service
        self.hoje = normalizar_data()  # pode ser alterada para simular atrasos
        self.opcoes = {
            "1": ("Cadastrar livro", self.cadastrar_livro),
            "2": ("Buscar livro por ISBN", self.buscar_livro),
            "3": ("Listar livros", lambda: mostrar_livros(self.s.listar_livros())),
            "4": ("Atualizar livro", self.atualizar_livro),
            "5": ("Remover livro", self.remover_livro),
            "6": ("Pesquisar livros (título/autor/categoria)", self.pesquisar),
            "7": ("Cadastrar aluno", self.cadastrar_aluno),
            "8": ("Buscar aluno por matrícula", self.buscar_aluno),
            "9": ("Emprestar livro", self.emprestar),
            "10": ("Devolver livro", self.devolver),
            "11": ("Empréstimos em aberto de um aluno", self.abertos_do_aluno),
            "12": ("Relatório: 5 livros mais emprestados", self.rel_top),
            "13": ("Relatório: empréstimos por curso", self.rel_curso),
            "14": ("Relatório: alunos com atraso", self.rel_atrasados),
            "15": ("Relatório: total arrecadado em multas", self.rel_multas),
            "16": ("Alterar data atual (simulação)", self.alterar_data),
        }

    def exibir(self) -> None:
        print(f"\n===== BIBLIOTECA ===== (data atual: {fmt_data(self.hoje)})")
        secoes = {"1": "Livros", "7": "Alunos", "9": "Empréstimos", "12": "Relatórios", "16": "Sistema"}
        for chave, (texto, _) in self.opcoes.items():
            if chave in secoes:
                print(f" -- {secoes[chave]}")
            print(f" {chave:>2}. {texto}")
        print("  0. Sair")

    def executar(self) -> None:
        while True:
            self.exibir()
            escolha = input("Opção: ").strip()
            if escolha == "0":
                print("Até logo!")
                return
            opcao = self.opcoes.get(escolha)
            if not opcao:
                print("  Opção inválida.")
                continue
            try:
                opcao[1]()
            except BibliotecaErro as erro:
                print(f"  ✗ {type(erro).__name__}: {erro}")
            except PyMongoError as erro:
                print(f"  ✗ Erro de banco de dados: {erro}")
            # Pausa para o resultado não sumir quando o menu for redesenhado
            input("\nPressione Enter para continuar...")

    # --- Livros ---------------------------------------------------------------
    def cadastrar_livro(self):
        livro = self.s.cadastrar_livro(
            ler("ISBN"), ler("Título"), ler("Autor"), ler("Ano"),
            ler("Categoria"), ler("Quantidade de exemplares"),
        )
        print(f"  ✓ Livro '{livro['titulo']}' cadastrado.")

    def buscar_livro(self):
        mostrar_livros([self.s.buscar_livro(ler("ISBN"))])

    def atualizar_livro(self):
        isbn = ler("ISBN do livro")
        mostrar_livros([self.s.buscar_livro(isbn)])
        print("  Deixe em branco o que não quiser alterar.")
        campos = {
            "titulo": ler("Novo título", True),
            "autor": ler("Novo autor", True),
            "ano": ler("Novo ano", True),
            "categoria": ler("Nova categoria", True),
            "exemplares_total": ler("Novo total de exemplares", True),
        }
        campos = {k: v for k, v in campos.items() if v is not None}
        mostrar_livros([self.s.atualizar_livro(isbn, **campos)])
        print("  ✓ Livro atualizado.")

    def remover_livro(self):
        isbn = ler("ISBN do livro")
        if input(f"  Confirma a remoção de {isbn}? (s/n): ").strip().lower() == "s":
            self.s.remover_livro(isbn)
            print("  ✓ Livro removido.")

    def pesquisar(self):
        termo = ler("Parte do título ou autor (opcional)", True)
        categoria = ler("Categoria (opcional)", True)
        mostrar_livros(self.s.pesquisar_livros(termo, categoria))

    # --- Alunos ---------------------------------------------------------------
    def cadastrar_aluno(self):
        aluno = self.s.cadastrar_aluno(ler("Matrícula"), ler("Nome"), ler("Curso"), ler("E-mail"))
        print(f"  ✓ Aluno '{aluno['nome']}' cadastrado.")

    def buscar_aluno(self):
        a = self.s.buscar_aluno(ler("Matrícula"))
        print(f"  [{a['matricula']}] {a['nome']} | {a['curso']} | {a['email']}")

    # --- Empréstimos ------------------------------------------------------------
    def emprestar(self):
        e = self.s.emprestar(ler("ISBN"), ler("Matrícula do aluno"), hoje=self.hoje)
        print(f"  ✓ Empréstimo registrado (id {e['id']}). Devolver até {fmt_data(e['data_prevista'])}.")

    def devolver(self):
        matricula = ler("Matrícula do aluno")
        abertos = self.s.listar_emprestimos(matricula, somente_abertos=True)
        mostrar_emprestimos(abertos)
        if not abertos:
            return
        emprestimo_id = ler("Id do empréstimo a devolver")
        e = self.s.devolver(emprestimo_id, hoje=self.hoje)
        if e["multa"]:
            print(f"  ✓ Devolvido com {e['dias_atraso']} dia(s) de atraso. Multa: R$ {e['multa']:.2f}")
        else:
            print("  ✓ Devolvido no prazo, sem multa.")

    def abertos_do_aluno(self):
        mostrar_emprestimos(self.s.listar_emprestimos(ler("Matrícula"), somente_abertos=True))

    # --- Relatórios -------------------------------------------------------------
    def rel_top(self):
        linhas = self.s.relatorio_mais_emprestados()
        for pos, l in enumerate(linhas, 1):
            print(f"  {pos}º {l['titulo']} ({l['isbn']}) — {l['total']} empréstimo(s)")
        if not linhas:
            print("  Nenhum empréstimo registrado.")

    def rel_curso(self):
        linhas = self.s.relatorio_por_curso()
        for l in linhas:
            print(f"  {l['curso']}: {l['total']}")
        if not linhas:
            print("  Nenhum empréstimo registrado.")

    def rel_atrasados(self):
        linhas = self.s.relatorio_atrasados(hoje=self.hoje)
        for l in linhas:
            print(f"  {l['nome']} ({l['matricula']}) — '{l['livro']}' — {l['dias_atraso']} dia(s) de atraso")
        if not linhas:
            print("  Nenhum aluno com atraso.")

    def rel_multas(self):
        print(f"  Total arrecadado em multas: R$ {self.s.relatorio_total_multas():.2f}")

    def alterar_data(self):
        self.hoje = normalizar_data(ler_data("Nova data atual"))
        print(f"  ✓ Data atual definida para {fmt_data(self.hoje)}.")


def main():
    try:
        db = get_db()
        db.client.admin.command("ping")
    except PyMongoError as erro:
        print(f"Não foi possível conectar ao MongoDB: {erro}")
        print("Suba o banco com 'docker compose up -d' ou configure a variável MONGO_URI.")
        return
    Menu(BibliotecaService(db)).executar()


if __name__ == "__main__":
    main()