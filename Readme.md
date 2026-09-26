# PlannerTrip

Aplicação web para planejamento de viagens, controle financeiro e organização de itinerários. O sistema permite cadastrar usuários, criar viagens, acompanhar o valor estimado do destino, monitorar gastos e visualizar informações do país de destino com cotação de moeda em tempo real.

## Deploy

A versão publicada está disponível em:

https://plannertrip.gabrielsantiago.dev.br

## Visão geral

O projeto foi construído com Python e Flask, usando MySQL como banco de dados e templates HTML/CSS/JS para a interface. A proposta é centralizar os principais dados de uma viagem em um painel, como:

- cadastro e login do usuário;
- criação e seleção de viagens;
- informações do destino e dias da viagem;
- gastos e movimentações financeiras;
- cotação de moedas e cálculo de metas;
- armazenamento de anotações e acompanhamento do orçamento.

## Funcionalidades principais

- Autenticação de usuários com login e cadastro;
- Dashboard de viagens com dados do destino;
- Cálculo de meta financeira baseada no custo diário do país;
- Consulta de cotação de moedas via API externa;
- Cache de câmbio para reduzir chamadas repetidas;
- Gerenciamento de notas/anotações da viagem;
- Interface responsiva usando Flask + templates.

## Requisitos

Antes de rodar o projeto, você precisa ter instalado:

- Python 3.10+
- pip
- MySQL
- Git
- Ambiente virtual (opcional, mas recomendado)

## Como baixar o projeto

1. Abra o terminal.
2. Clone o repositório:

```bash
git clone <URL_DO_REPOSITORIO>
cd Projeto
```

Se o projeto já estiver baixado na sua máquina, basta entrar na pasta do projeto.

## Como instalar as dependências

Dentro da pasta do projeto, execute:

```bash
python -m venv venv
```

Ative o ambiente virtual:

### Windows (PowerShell)

```powershell
.\venv\Scripts\Activate.ps1
```

### Windows (CMD)

```cmd
venv\Scripts\activate.bat
```

### Linux/macOS

```bash
source venv/bin/activate
```

Depois, instale as bibliotecas:

```bash
pip install -r requirements.txt
```

## Variáveis de ambiente

O projeto usa um arquivo `.env` para configurar a conexão com o banco de dados e a chave secreta da sessão.

Crie um arquivo `.env` na raiz do projeto com o seguinte conteúdo:

```env
DB_HOST=localhost
DB_NAME=seu_banco
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_PORT=3306
SECRET_KEY=sua_chave_secreta
```

Exemplo de configuração:

```env
DB_HOST=localhost
DB_NAME=plannertrip
DB_USER=root
DB_PASSWORD=123456
DB_PORT=3306
SECRET_KEY=tripplan-secret-key
```

> Importante: ajuste os valores conforme o seu banco MySQL local.

## Como rodar o projeto

Na raiz do projeto, execute:

```bash
python app.py
```

A aplicação ficará disponível em:

```text
http://localhost:5000
```

Se preferir, também pode iniciar com Flask:

```bash
set FLASK_APP=app.py
flask run
```

## Estrutura do projeto

A organização dos arquivos está assim:

```text
Projeto/
├─ .env
├─ .gitignore
├─ app.py
├─ database.py
├─ requirements.txt
├─ Readme.md
├─ controller/
│  └─ routes.py
├─ static/
│  ├─ img/
│  ├─ script.js
│  └─ style.css
├─ templates/
│  ├─ cadastro.html
│  ├─ index.html
│  └─ login.html
├─ utils/
│  ├─ currency.py
│  └─ currency_cache.json
└─ __pycache__/
```

## Como o projeto está organizado

### `app.py`
Arquivo principal da aplicação Flask. Ele cria a aplicação, define a chave secreta, registra os blueprints e inicia o servidor.

### `database.py`
Centraliza a conexão com o banco de dados MySQL. Contém a função `get_db_connection()` e utilidades para abrir e fechar conexão/cursor.

### `controller/routes.py`
Arquivo com a lógica principal da aplicação. Aqui ficam as rotas, autenticação, busca de dados, dashboard da viagem, login, cadastro, seleção de viagem e outras regras de negócio.

### `templates/`
Armazena os arquivos HTML usados na interface:

- `login.html`: tela de login;
- `cadastro.html`: cadastro de usuário;
- `index.html`: dashboard principal com dados da viagem.

### `static/`
Arquivos frontend da aplicação:

- `style.css`: estilos visuais;
- `script.js`: interações JavaScript;
- `img/`: imagens e assets visuais.

### `utils/`
Contém utilitários do sistema:

- `currency.py`: busca cotação de moedas, aplica cache e formata valores;
- `currency_cache.json`: armazenamento local das cotações consultadas.

## Dependências principais

O projeto utiliza as seguintes bibliotecas:

```text
Flask
mysql-connector-python
python-dotenv
requests
gunicorn
```

Essas dependências estão listadas em `requirements.txt`.

## Observações

- O projeto foi pensado para uso em ambiente com banco MySQL configurado;
- As conversões de moeda dependem da API de economia externa;
- O cache em `utils/currency_cache.json` ajuda a evitar consultas repetidas e acelera a aplicação;
- O deploy em produção pode exigir ajustes de ambiente, domínio e variáveis de servidor.

## Fluxo de uso básico

1. Faça cadastro ou login;
2. Crie uma viagem;
3. Selecione o destino;
4. Acompanhe o painel financeiro da viagem;
5. Consulte cotação, meta e movimentações;
6. Use anotações para organizar o planejamento.

## Conclusão

O PlannerTrip é um projeto de gestão de viagens com foco em organização financeira e planejamento do destino. Ele reúne funcionalidades essenciais para acompanhar orçamento, cotação e informações do itinerário em um único painel.

Se quiser, posso também criar uma segunda versão do README com foco em:

- documentação para apresentação acadêmica;
- README mais profissional para GitHub;
- instruções de deploy em produção com Nginx + Gunicorn.
