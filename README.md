
# Jornal Cienc.IA

Plataforma Web para Divulgação Científica em Saúde no Contexto da Ciência Aberta.

Projeto desenvolvido como parte de um Trabalho de Conclusão de Curso (TCC) na Universidade Federal de Viçosa (UFV).

## 1. Sobre o projeto

O Jornal Cienc.IA é uma plataforma de divulgação científica em saúde que utiliza artigos científicos como fonte para produzir conteúdos em diferentes níveis de linguagem.

O objetivo é facilitar o acesso e a compreensão de informações científicas, preservando a fidelidade intelectual às evidências utilizadas.

O sistema possui quatro componentes principais:

1. Coletor de artigos científicos.
2. Painel de revisão editorial.
3. Processo de simplificação e avaliação de fidelidade.
4. Portal público de divulgação científica.

A seleção de artigos científicos pode ser iniciada de duas maneiras:

- **TEMAS:** pesquisas por assuntos gerais de saúde.
- **PERGUNTAS:** pesquisas orientadas por dúvidas formuladas em linguagem cotidiana.

As duas modalidades utilizam o mesmo fluxo de triagem e revisão científica.

---

## 2. Estrutura do projeto

A organização principal dos arquivos é:

```text
jornal-ciencia/
│
├── coletor_artigos.py
├── revisor_jornal_ciencia.py
│
├── index.html
├── artigo.html
├── app.js
├── artigo.js
├── styles.css
│
├── artigos_coletados.json
├── noticias.json
├── rascunhos.json
├── estado_editorial.json
├── historico_editorial.json
├── traducoes_base.json
│
├── .env
├── .gitignore
└── README.md
```

Alguns arquivos JSON são gerados ou atualizados durante a utilização do sistema.

O portal público utiliza `noticias.json`, que deve conter apenas matérias efetivamente publicadas.

---

## 3. Preparação do ambiente

### Criar ambiente virtual

No Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

No Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Instalar dependências

Dependências básicas do coletor:

```bash
pip install requests python-dotenv
```

Para o painel editorial:

```bash
pip install streamlit
```

O painel pode exigir outras bibliotecas utilizadas no arquivo `revisor_jornal_ciencia.py`.

### Configuração do .env

As credenciais e configurações devem ser armazenadas no arquivo `.env`.

Exemplo:

```env
USER_EMAIL=seu_email@exemplo.com

NCBI_API_KEY=

GEMINI_API_KEY=
GEMINI_MODEL_BUSCA=

EMBASE_API_KEY=
EMBASE_INSTTOKEN=
ATIVAR_EMBASE=1
```

O `GEMINI_MODEL_BUSCA` deve conter o identificador de um modelo Gemini disponível para a chave configurada.

A variável `GEMINI_MODEL` também pode ser utilizada caso `GEMINI_MODEL_BUSCA` não esteja definida.

As credenciais não devem ser publicadas ou incluídas no repositório.

---

# 4. Coletor de artigos científicos

Arquivo:

```text
coletor_artigos.py
```

O coletor realiza a descoberta e seleção de artigos biomédicos em bases científicas.

A implementação utiliza:

- PubMed;
- OpenAlex;
- Embase, quando houver acesso autorizado à API.

Semantic Scholar, Crossref e Europe PMC não fazem parte da coleta desta versão.

O coletor realiza:

1. Preparação das consultas.
2. Busca nas bases científicas.
3. Deduplicação dos registros.
4. Triagem objetiva de elegibilidade.
5. Ordenação editorial.
6. Seleção dos artigos.
7. Exportação dos resultados para JSON.

O coletor não utiliza uma pontuação numérica de qualidade científica.

A preferência por revisões sistemáticas e meta-análises é uma regra editorial, não uma avaliação automática da qualidade metodológica de cada estudo.

---

# 5. Modalidades de coleta

O sistema possui duas modalidades de entrada: TEMAS e PERGUNTAS.

## 5.1. TEMAS — busca por assuntos gerais

Utiliza o parâmetro:

```bash
--temas
```

A consulta informada é enviada diretamente às bases científicas.

Exemplo:

```bash
python coletor_artigos.py --temas "sleep health"
```

Múltiplos temas:

```bash
python coletor_artigos.py --temas "sleep health" "nutrition migraine" "vaccine safety"
```

Essa modalidade é indicada quando se deseja explorar um assunto geral.

Exemplos de temas:

- Sono e saúde.
- Alimentação e enxaqueca.
- Segurança das vacinas.
- Exercício físico e saúde mental.
- Prevenção de doenças cardiovasculares.

No código, os temas padrão estão definidos na variável `TEMAS_PADRAO`.

Executar o coletor sem informar `--temas` ou `--perguntas` utiliza os temas padrão.

## 5.2. PERGUNTAS — busca por dúvidas populares

Utiliza o parâmetro:

```bash
--perguntas
```

Essa modalidade permite informar perguntas escritas em linguagem cotidiana.

Exemplo:

```bash
python coletor_artigos.py --perguntas "Creatina faz mal aos rins?"
```

Também é possível pesquisar várias perguntas:

```bash
python coletor_artigos.py --perguntas "Vermífugo cura câncer?" "Colágeno em pó melhora a pele?" "Dormir pouco faz engordar?"
```

Diferentemente de TEMAS, as perguntas são processadas por um modelo de linguagem antes da busca bibliográfica.

O modelo utilizado nessa etapa é o Gemini.

### Funcionamento

```text
PERGUNTA INFORMAL
       |
       v
GEMINI
       |
       v
FORMULAÇÃO CIENTÍFICA
       |
       v
CONSULTAS EM INGLÊS
       |
       v
PUBMED / OPENALEX / EMBASE
       |
       v
ARTIGOS CIENTÍFICOS
       |
       v
TRIAGEM E SELEÇÃO
```

Exemplo:

**Entrada original:**

```text
Creatina faz mal aos rins?
```

**Formulação científica esperada:**

```text
Relação entre suplementação de creatina
e indicadores de função renal.
```

**Termos de pesquisa:**

```text
creatine supplementation renal function
```

O exemplo é ilustrativo. As consultas reais são produzidas pelo Gemini e podem utilizar operadores booleanos e sinônimos.

### Regras da conversão

O Gemini deve:

- Preservar o significado da pergunta original.
- Utilizar terminologia científica apropriada.
- Traduzir os termos para inglês.
- Preparar consultas específicas para cada base.
- Não presumir que uma afirmação seja verdadeira.
- Não acrescentar condições ou populações arbitrariamente.
- Não escolher medicamentos ou doenças específicos quando a pergunta for genérica.
- Não responder à pergunta durante a preparação da busca.

Por exemplo, a pergunta:

```text
Vermífugo cura câncer?
```

Não deve ser interpretada automaticamente como uma pesquisa sobre um único medicamento ou tipo de câncer.

O sistema deve procurar literatura relacionada à questão, mantendo uma estratégia de pesquisa neutra.

### Importante

O Gemini não decide se determinada substância funciona ou não.

A preparação das consultas serve exclusivamente para localizar possíveis fontes científicas.

Um artigo encontrado não é necessariamente suficiente para responder à pergunta original.

A interpretação dos resultados permanece sujeita à revisão científica e editorial.

---

# 6. Conferência das consultas antes da coleta

É possível visualizar como a pergunta será transformada em consulta científica sem executar a busca nas bases.

Utilize:

```bash
python coletor_artigos.py --perguntas "Creatina faz mal aos rins?" --somente-planejar
```

Nesse modo, o coletor:

1. Recebe a pergunta original.
2. Solicita ao Gemini a formulação científica.
3. Prepara as consultas por fonte.
4. Exibe as consultas no terminal.
5. Salva o planejamento em JSON.
6. Não consulta as bases bibliográficas.

O planejamento é salvo em:

```text
artigos_coletados.json.consultas.json
```

Essa etapa permite verificar se a conversão manteve o sentido da pergunta.

O processo é útil para a rastreabilidade metodológica da pesquisa.

---

# 7. Utilização conjunta de TEMAS e PERGUNTAS

O coletor permite utilizar as duas modalidades na mesma execução.

Exemplo:

```bash
python coletor_artigos.py --temas "sleep health" --perguntas "Tomar café à tarde atrapalha o sono?"
```

Nesse caso:

- O tema será pesquisado diretamente.
- A pergunta será convertida pelo Gemini.
- Ambos utilizarão as mesmas bases científicas.
- Os resultados ficarão separados no arquivo de saída.

Não é necessário utilizar `--modo-busca`.

A modalidade é definida automaticamente pelo parâmetro informado.

---

# 8. Parâmetros do coletor

## Quantidade de registros consultados

```bash
python coletor_artigos.py --temas "sleep health" --limite-busca 100
```

O valor define o limite de resultados consultados por fonte antes da triagem.

Ele não representa a quantidade de artigos selecionados.

## Quantidade máxima de selecionados

```bash
python coletor_artigos.py --temas "sleep health" --limite-selecionados 10
```

Limita operacionalmente a quantidade de artigos enviados à fila editorial por entrada.

Para manter todos os elegíveis:

```bash
python coletor_artigos.py --temas "sleep health" --limite-selecionados 0
```

## Definir arquivo de saída

```bash
python coletor_artigos.py --temas "sleep health" --saida minha_coleta.json
```

## Definir modelo de busca

```bash
python coletor_artigos.py --perguntas "Creatina faz mal aos rins?" --modelo-busca NOME_DO_MODELO
```

Substitua `NOME_DO_MODELO` por um modelo Gemini disponível.

## Testar acesso ao Embase

```bash
python coletor_artigos.py --testar-embase
```

A API Embase necessita de credenciais e permissões institucionais apropriadas.

A existência de uma chave não garante autorização de acesso.

---

# 9. Estrutura do arquivo de coleta

O resultado é armazenado em:

```text
artigos_coletados.json
```

A estrutura principal separa as modalidades:

```json
{
  "gerado_em": "...",
  "versao_pipeline": "...",
  "parametros": {},
  "temas": {},
  "perguntas": {},
  "total_artigos": 0
}
```

Em TEMAS, os registros são organizados pelo assunto informado.

Em PERGUNTAS, os registros são organizados pela pergunta original.

A modalidade de perguntas também registra informações sobre a preparação da busca:

- Pergunta original.
- Formulação científica.
- Consultas utilizadas nas bases.
- Modelo responsável pela conversão.
- Versão do prompt.
- Observações e data da preparação.

Esses dados permitem reconstruir a estratégia de descoberta dos artigos.

Cada artigo selecionado pode carregar o campo `origem_busca`, indicando sua modalidade de descoberta.

---

# 10. Deduplicação e elegibilidade

## Deduplicação

O coletor identifica possíveis registros duplicados utilizando:

1. DOI normalizado.
2. Título normalizado, quando o DOI não está disponível.

Dessa forma, um artigo localizado em mais de uma base pode ser tratado como um único registro.

## Elegibilidade

A triagem operacional considera:

- Registro não retratado.
- Tipo de publicação aceito.
- Disponibilidade de resumo científico suficiente para o pipeline.

O resumo deve possuir pelo menos 100 caracteres.

Revisões narrativas ou genéricas sem identificação de revisão sistemática ou meta-análise são excluídas conforme a regra editorial implementada.

## Seleção editorial

A ordenação considera a relevância retornada pelas bases e utiliza o desenho do estudo e a data de publicação conforme os critérios implementados.

Revisões sistemáticas e meta-análises recebem preferência editorial quando disponíveis e elegíveis.

Essa preferência não substitui a avaliação crítica da metodologia científica.

---

# 11. Painel de revisão editorial

Arquivo principal:

```text
revisor_jornal_ciencia.py
```

Execução:

```bash
streamlit run revisor_jornal_ciencia.py
```

O painel é responsável por processar e revisar conteúdos selecionados para divulgação.

O fluxo geral envolve:

```text
ARTIGO CIENTÍFICO
       |
       v
EXTRAÇÃO E ESTRUTURAÇÃO DA EVIDÊNCIA
       |
       v
ADAPTAÇÃO DA LINGUAGEM
       |
       v
DIVULGAÇÃO CIENTÍFICA
E LEITURA FACILITADA
       |
       v
VERIFICAÇÃO DA FIDELIDADE
       |
       v
REVISÃO HUMANA
       |
       v
PUBLICAÇÃO
```

A revisão de fidelidade considera sustentação das afirmações, cobertura de informações essenciais e preservação da incerteza científica.

A revisão humana continua obrigatória antes da publicação.

---

# 12. Portal público

Os principais arquivos do portal são:

```text
index.html
app.js
styles.css
artigo.html
artigo.js
noticias.json
```

O portal disponibiliza os conteúdos publicados de acordo com sua modalidade de exploração.

A página inicial possui duas abas:

```text
TEMAS | PERGUNTAS
```

## Aba TEMAS

Permite explorar os conteúdos por assunto científico.

Exemplos:

- Sono.
- Alimentação.
- Atividade física.
- Saúde mental.
- Vacinas.

A navegação utiliza a classificação temática registrada nas notícias.

## Aba PERGUNTAS

Permite explorar conteúdos encontrados a partir de perguntas cotidianas.

Exemplos:

- Creatina faz mal aos rins?
- Vermífugo cura câncer?
- Colágeno em pó melhora a pele?

A pergunta funciona como ponto de acesso ao conteúdo científico.

O portal não deve apresentar uma conclusão que o artigo utilizado não sustente.

### Identificação da origem

Para que uma matéria seja identificada como proveniente de uma pergunta, deve preservar no `noticias.json` o campo de origem.

Exemplo:

```json
{
  "origem_busca": {
    "tipo": "pergunta",
    "entrada_original": "Creatina faz mal aos rins?",
    "pergunta_formal": "Relação entre suplementação de creatina e função renal."
  }
}
```

O objeto é ilustrativo e representa apenas os campos de origem da busca, não uma notícia completa.

Matérias sem identificação de pergunta continuam disponíveis na exploração por TEMAS.

Na implementação atual, a aba TEMAS também permite encontrar matérias provenientes de perguntas, desde que possuam um tema científico registrado.

A aba PERGUNTAS apresenta somente registros identificados com uma pergunta de origem.

**Atenção:** o campo `origem_busca` deve ser preservado pelo painel editorial desde a coleta até a publicação. Apenas modificar o portal não garante essa transferência.

---

# 13. Executar o portal localmente

O portal utiliza JavaScript para carregar o arquivo `noticias.json`.

Recomenda-se executar um servidor HTTP local em vez de abrir diretamente o arquivo HTML.

Na pasta do projeto:

```bash
python -m http.server 8000
```

Acesse:

```text
http://localhost:8000
```

A página inicial é:

```text
http://localhost:8000/index.html
```

O servidor deve ser executado na pasta que contém o `index.html` e o `noticias.json`.

---

# 14. Rastreabilidade da pesquisa

A plataforma busca preservar a relação entre a descoberta científica, a geração de textos e a publicação.

A rastreabilidade envolve:

- Entrada original utilizada na busca.
- Estratégia bibliográfica aplicada.
- Base de dados em que o artigo foi encontrado.
- Identificação do artigo científico.
- Resumo científico utilizado como referência.
- Conteúdos adaptados.
- Avaliação da fidelidade intelectual.
- Revisão editorial humana.

Na modalidade PERGUNTAS, a formulação científica gerada pelo Gemini também deve permanecer registrada.

Isso permite verificar se a interpretação da dúvida popular foi adequada.

---

# 15. Limitações

O coletor identifica possíveis fontes científicas, mas não comprova automaticamente a qualidade metodológica dos estudos.

A conversão por modelo de linguagem pode apresentar erros e deve ser conferida.

A presença de uma palavra-chave no artigo não garante que o estudo responda à pergunta popular.

Resultados encontrados em células ou animais não devem ser interpretados automaticamente como evidência de eficácia clínica em humanos.

Os conteúdos publicados devem respeitar as limitações e incertezas dos respectivos estudos.

A avaliação automatizada de fidelidade não substitui revisão humana.

---

# 16. Objetivo acadêmico

O Jornal Cienc.IA investiga a utilização de tecnologias de processamento de linguagem natural para ampliar a acessibilidade de conteúdos científicos em saúde.

A proposta combina descoberta de fontes científicas, adaptação da linguagem, rastreabilidade e avaliação da fidelidade intelectual.

As modalidades TEMAS e PERGUNTAS representam estratégias complementares para aproximar a produção científica dos interesses do público.

Em ambos os casos, o artigo científico continua sendo a fonte de referência para os conteúdos apresentados.
