# Passo a passo do aluno: da Web ao Databricks em 10 passos

Oficina "Da Web ao Databricks", UESC, 07/11/2026. Prof. Rafael Santos Novo Pereira.
Cada passo diz o que fazer e o que deve aparecer. Os números são da coleta de 06/11/2026; os seus vão diferir um pouco, porque o portal muda todo dia.

**O que você precisa:** um computador com Python 3.10 ou superior (para os passos 1 a 4) e uma conta Databricks Free Edition (para os passos 5 a 10). Sem Python, pule para o passo 5: a tabela vem pronta do Blob.

---

## Parte A: no seu computador (Python)

### Passo 1. Baixar o repositório
Botão verde **Code > Download ZIP** nesta página do GitHub. Descompacte. Abra a pasta `coleta` no terminal (ou no VS Code: File > Open Folder > `coleta`, depois Terminal > New Terminal).

### Passo 2. Instalar as bibliotecas (uma vez)
```
python -m pip install -r requirements.txt
```
Se `python` não for reconhecido no Windows, tente `py -m pip install -r requirements.txt`.

### Passo 3. Olhar o que o site permite (2 min, no navegador)
1. Abra `https://www.vivareal.com.br/robots.txt`. Veja `Allow: /` e os `Disallow` de filtros.
2. Abra `https://www.vivareal.com.br/aluguel/bahia/ilheus/`, aperte **Ctrl+U** e **Ctrl+F** `ld+json`. Esse bloco é o que o programa vai ler.
3. Abra `https://www.lopes.com.br/busca/aluguel/ba/ilheus`, Ctrl+U, Ctrl+F `R$`. Zero. Por isso a Lopes fica fora.

### Passo 4. Rodar a coleta
Teste rápido (50 s, 5 páginas por portal):
```
python oficina_coleta.py --rapido
```
Coleta completa (3 min, 60 requisições com 2 s de pausa):
```
python oficina_coleta.py
```
**O que aparece:** `vivareal ilheus pagina 1: 30 anuncios` ... até a página 26 (vazia), depois `zap`, `chavesnamao`, e Itabuna. Em seguida seis seções: coleta, dois portais um estoque, o que a base esconde, quatro decisões, a resposta, bairros. No fim, `PRONTO`.

**Arquivos gerados na pasta:** `anuncios_todos.csv` (bruto), `anuncios_limpo.csv` (846 linhas, pronto para o Databricks), `g1` a `g4.png` (gráficos).

Se alguma linha disser `status 403` ou `429`: o portal recusou naquele momento. O script continua com os outros portais. Espere 5 minutos e rode de novo. Não tente "burlar": é a regra da oficina.

Só para refazer a limpeza e os gráficos sem coletar de novo: `python oficina_coleta.py --so-limpeza`.

---

## Parte B: no Databricks Free Edition (navegador)

### Passo 5. Criar a conta (5 min, faça em casa)
`databricks.com/try-databricks` > **Get Free Edition** (lado "Personal", "Free forever") > entre com Google, Microsoft ou e-mail (código de 6 dígitos) > finalidade "uso pessoal" > espere "configurando sua conta". Telas reais em `docs/03_Databricks_Jornada.md`.

### Passo 6. Criar um notebook
Barra lateral > **New** > **Notebook**. Linguagem: Python. No canto superior direito, compute: **Serverless**.

### Passo 7. Do Blob à tabela (uma célula)
Cole e aperte **Shift+Enter**. A primeira execução espera o serverless ligar (até 1 min).

```python
import requests, io, pandas as pd

# 1. baixa o CSV que o professor deixou num Blob da Azure (SAS só de leitura)
r = requests.get("https://fiapmbadados.blob.core.windows.net/vendas/anuncios/anuncios_limpo.csv?sp=r&st=2026-11-07T01:51:29Z&se=2027-05-13T10:06:29Z&sv=2026-02-06&sr=c&sig=ZXLuwNVtDrh9bz0G3rJZ%2FXCKBqpij%2FuHW4hnva6dW%2B8%3D", timeout=30)
print(r.status_code, len(r.content) // 1024, "KB")          # esperado: 200 209 KB

# 2. pandas lê o CSV; conferimos os tipos antes de virar tabela
pdf = pd.read_csv(io.BytesIO(r.content))
for c in ["preco", "area_m2", "quartos", "banheiros", "preco_m2"]:
    pdf[c] = pd.to_numeric(pdf[c], errors="coerce")           # número; vazio vira NULL
pdf["residencial"] = pdf["residencial"].astype(bool)
pdf["id_anuncio"] = pdf["id_anuncio"].astype(str)

# 3. Spark grava como tabela Delta no Unity Catalog
spark.createDataFrame(pdf).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("workspace.default.anuncios")
print("tabela gravada:", spark.table("workspace.default.anuncios").count(), "linhas")   # esperado: 846
```

**Conferir:** barra lateral > **Catalog** > `workspace` > `default` > `anuncios`.

**Plano B** (se a célula der erro de conexão): **New > Add or upload data > Upload files to a volume**, arraste `dados/anuncios_limpo.csv` deste repositório, depois **Catalog > Create table**, nome `anuncios`.

### Passo 8. A pergunta em SQL
Barra lateral > **Workspace** > sua pasta > **⋮ > Import > File** > `databricks/oficina_sql_notebook.sql`. Abra e rode célula a célula (Shift+Enter). Cada célula tem o resultado esperado em comentário. A célula 3 é a pergunta da oficina:

| cidade | n | média | mediana | R$/m² |
|---|---|---|---|---|
| Ilhéus | 542 | 4231 | 3500 | 40.0 |
| Itabuna | 52 | 4457 | 2850 | 18.6 |

Na célula 5, clique em **+ > Visualization**: barras de `mediana` por `bairro`.

### Passo 9. Genie
Barra lateral > **Genie** > **New** > escolha `workspace.default.anuncios` > Create. Em **Configure > Instructions**, cole:
```
preco é o aluguel mensal em reais (BRL). area_m2 em metros quadrados.
residencial = true significa Apartment, House ou Accommodation (flat/kitnet). Para perguntas sobre moradia, filtre residencial = true.
Dados dos portais VivaReal, ZAP e Chaves na Mão, coletados em 06/11/2026. Não representam todos os imóveis da cidade, só os anunciados nesses portais.
Prefira mediana a média para preço: há outliers (galpões de até R$ 90.000).
```
Pergunte, e abra o **SQL gerado** em cada resposta:
1. `Qual a mediana do aluguel residencial em Ilhéus e em Itabuna?` (confira: 3.500 e 2.850)
2. `Quais os 5 bairros de Ilhéus com mais anúncios residenciais?`
3. `Qual o imóvel residencial de 2 quartos mais barato no Pontal?`

Depois apague a instrução sobre `residencial` e repita a pergunta 1. A resposta muda, com a mesma confiança. Esse é o ponto.

Se o Genie não aparecer na barra lateral: use o **Assistant** do editor SQL (ícone de estrela), que também escreve SQL a partir de pergunta em português.

### Passo 10. Para casa
Rode `python oficina_coleta.py` daqui a uma semana. Quantos anúncios saíram? Quantos entraram? A mediana mudou? Suba o novo CSV e compare. É uma série temporal nascendo.

---

## Se der errado

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `python não é reconhecido` | Python fora do PATH | reinstale marcando "Add python.exe to PATH", ou use `py` |
| `ModuleNotFoundError: bs4` | passo 2 não rodou | `python -m pip install -r requirements.txt` |
| `status 403` numa página | o portal recusou naquele momento | espere 5 min e rode de novo; nunca disfarce o robô |
| célula do Blob: `ConnectionError` | rede do laboratório ou do Free Edition bloqueando | plano B do passo 7 (upload pela interface) |
| célula 3 do SQL com números diferentes | coleta de outra data | normal; compare com a data em `coletado_em` |
| `preco` aparece como string na tabela | criou a tabela pela interface sem conferir tipos | refaça pelo passo 7, que converte os tipos |
