# Sistema de Empréstimo de Livros — Backend com MongoDB

Backend do novo sistema da biblioteca da faculdade, substituindo a planilha de
controle. Gerencia livros, alunos e empréstimos no MongoDB, com regras de negócio
que impedem, por exemplo, emprestar um livro que não está mais na estante.

## Equipe

| Nome | RM |
|------|----|
| _preencher_ | _preencher_ |

## Estrutura do projeto

```
biblioteca/
├── db.py               # conexão com o MongoDB e criação dos índices
├── service.py          # regras de negócio (R1 a R6)
├── exceptions.py       # exceções de negócio
├── main.py             # menu de terminal (R7)
├── seed.py             # carrega dados de exemplo
├── tests/              # testes pytest, um arquivo por requisito
│   ├── conftest.py
│   ├── test_r1_livros.py
│   ├── test_r2_alunos.py
│   ├── test_r3_busca.py
│   ├── test_r4_emprestimo.py
│   ├── test_r5_devolucao.py
│   └── test_r6_relatorios.py
├── docker-compose.yml
├── requirements.txt
└── pytest.ini
```

## Como rodar

### 1. Instalar as dependências

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Subir o MongoDB

**Opção A — Docker (recomendado):**

```bash
docker compose up -d
```

O MongoDB fica disponível em `mongodb://localhost:27017`, que já é o padrão do projeto.

**Opção B — MongoDB Atlas:**

1. Crie um cluster gratuito (M0) em <https://cloud.mongodb.com>.
2. Em *Database Access*, crie um usuário e senha.
3. Em *Network Access*, libere o seu IP (ou `0.0.0.0/0` só para testes).
4. Em *Connect → Drivers*, copie a connection string e defina a variável:

```bash
export MONGO_URI="mongodb+srv://usuario:senha@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
# Windows (PowerShell): $env:MONGO_URI="..."
```

Opcionalmente, `MONGO_DB` muda o nome do banco (padrão: `biblioteca`).

### 3. (Opcional) Carregar dados de exemplo

```bash
python seed.py
```

### 4. Rodar o sistema

```bash
python main.py
```

A opção **16 — Alterar data atual** muda a data usada pelo sistema, o que permite
demonstrar atrasos e multas sem esperar dias. Por exemplo: empreste um livro, mude a
data para 10 dias depois, veja o relatório de atrasados e faça a devolução com multa.

### 5. Rodar os testes

```bash
pytest -v
```

Por padrão os testes usam o **mongomock** (MongoDB em memória), então rodam sem
nenhum banco ligado. Para rodar contra um MongoDB real — o que também ativa o teste
de concorrência com 20 threads disputando o último exemplar:

```bash
MONGO_URI_TEST=mongodb://localhost:27017 pytest -v
```

Os testes usam o banco `biblioteca_test`, que é apagado a cada teste.

## Modelo de dados

| Coleção | Campos |
|---|---|
| `livros` | isbn, titulo, autor, ano, categoria, exemplares_total, exemplares_disponiveis |
| `alunos` | matricula, nome, curso, email |
| `emprestimos` | isbn, matricula, data_emprestimo, data_prevista, data_devolucao (null enquanto aberto), multa |

### Índices

| Coleção | Índice | Motivo |
|---|---|---|
| livros | `isbn` (único) | R1 — ISBN não pode repetir |
| alunos | `matricula` (único) | R2 — matrícula não pode repetir |
| livros | `titulo`, `categoria` | listagem ordenada e filtro por categoria (R3) |
| emprestimos | `(matricula, data_devolucao)` | empréstimos em aberto do aluno (R4) |
| emprestimos | `(isbn, data_devolucao)` | impedir remoção de livro emprestado (R1) |
| emprestimos | `(data_devolucao, data_prevista)` | busca de atrasados (R4 e R6) |

## Principais decisões da equipe

**Camadas e injeção de dependência.** O `BibliotecaService` recebe o objeto `db` no
construtor em vez de abrir a conexão sozinho. Assim o mesmo código roda com o banco
real (via `db.get_db()`) e com o banco em memória nos testes.

**Unicidade garantida pelo banco.** Não fazemos `find_one` antes de inserir para
checar se o ISBN existe, porque entre a checagem e o insert outro processo poderia
inserir o mesmo ISBN. O índice único rejeita a duplicata e o serviço converte o
`DuplicateKeyError` na exceção `LivroJaCadastrado`.

**Empréstimo atômico (R4).** A reserva do exemplar é feita em uma única operação:

```python
livros.update_one(
    {"isbn": isbn, "exemplares_disponiveis": {"$gt": 0}},
    {"$inc": {"exemplares_disponiveis": -1}},
)
```

Como o filtro e o decremento acontecem juntos no servidor, se dois alunos tentarem
pegar o último exemplar ao mesmo tempo, só um update encontra o documento; o outro
recebe `modified_count == 0` e vira `LivroIndisponivel`. Se a gravação do empréstimo
falhar depois da reserva, o exemplar é devolvido ao estoque.

**Devolução idempotente (R5).** A devolução usa o filtro `data_devolucao: None` no
`update_one`. Se o mesmo empréstimo for devolvido duas vezes (mesmo que ao mesmo
tempo), só a primeira altera o documento e a segunda gera `EmprestimoJaDevolvido`,
sem devolver o exemplar ao estoque em dobro.

**Datas como "dia".** O MongoDB não tem tipo só-data, então toda data é gravada como
`datetime` à meia-noite. Assim atraso e multa são contados em dias inteiros, e o
aluno ainda pode devolver no próprio dia previsto sem multa. Todas as funções que
dependem do dia atual recebem o parâmetro `hoje` (padrão: data de hoje).

**Multa.** R$ 2,00 por dia de atraso, calculada e gravada no momento da devolução.
O valor é sempre múltiplo de R$ 2,00, então `float` com arredondamento em 2 casas é
suficiente; num sistema financeiro real usaríamos `Decimal128` ou centavos inteiros.

**Atualização do total de exemplares.** Ao mudar `exemplares_total`, o
`exemplares_disponiveis` muda junto com o mesmo `$inc`. O filtro impede reduzir o
total para menos do que já está emprestado. ISBN e `exemplares_disponiveis` não podem
ser alterados diretamente.

**Busca (R3).** Usamos `$regex` com a opção `i` e `re.escape` no termo, para que
caracteres como `(` ou `.` digitados pelo usuário não sejam interpretados como
expressão regular. A ordenação por título usa *collation* `pt` com `strength: 1`,
que ignora maiúsculas e acentos. Optamos por regex em vez de índice de texto porque o
índice `$text` busca palavras inteiras, e o requisito pede busca por *parte* do título.

**Relatórios (R6).** Todos feitos com Aggregation Pipeline (`$group`, `$lookup`,
`$unwind`, `$project`, `$sort`). Os dias de atraso são calculados no próprio pipeline:
`(hoje - data_prevista)` retorna milissegundos, que dividimos por 86.400.000.

**Exceções próprias.** Todas herdam de `BibliotecaErro`, então o menu trata qualquer
erro de negócio num único `except` e mostra uma mensagem amigável.

## Limitações conhecidas

- **Limite de 3 empréstimos sob concorrência:** a contagem de empréstimos abertos e a
  reserva do exemplar são operações separadas. Se o mesmo aluno fizer dois pedidos
  exatamente ao mesmo tempo, ele poderia passar do limite. Para fechar essa brecha,
  poderíamos usar uma transação multi-documento (exige replica set) ou manter um
  contador `emprestimos_abertos` no documento do aluno, atualizado com
  `update_one({"emprestimos_abertos": {"$lt": 3}}, {"$inc": ...})`.
- **mongomock nos testes:** ele não implementa *collation*, por isso o serviço tem a
  flag `usar_collation`, desligada só nos testes em memória. Rodando com
  `MONGO_URI_TEST`, os testes usam o comportamento completo do MongoDB.
- A busca com regex sem âncora no início não aproveita índice; para um acervo grande,
  o ideal seria o Atlas Search.
