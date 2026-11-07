# Databricks notebook source
# MAGIC %md
# MAGIC # Oficina UESC: do Azure Blob para a tabela `anuncios` no Databricks Free Edition
# MAGIC Lê `anuncios_limpo.csv` do container `vendas` (conta `fiapmbadados`) com um SAS de leitura
# MAGIC e grava como tabela Delta `workspace.default.anuncios`. Rode célula a célula (Shift+Enter).
# MAGIC
# MAGIC Não usa conector Spark para Azure (que o Free Edition pode não ter): baixa com `requests`,
# MAGIC lê com `pandas`, converte com `spark.createDataFrame`. Funciona em qualquer edição.
# MAGIC
# MAGIC O SAS é só de leitura (`sp=r`) e vale até 13/05/2027. Quem tem este notebook lê o container inteiro até lá.

# COMMAND ----------

# Célula 1: configuração. Só mude ARQUIVO se o nome no Blob for outro.
CONTA     = "fiapmbadados"
CONTAINER = "vendas"
ARQUIVO   = "anuncios/anuncios_limpo.csv"
SAS       = "sp=r&st=2026-11-07T01:51:29Z&se=2027-05-13T10:06:29Z&sv=2026-02-06&sr=c&sig=ZXLuwNVtDrh9bz0G3rJZ%2FXCKBqpij%2FuHW4hnva6dW%2B8%3D"
URL = f"https://{CONTA}.blob.core.windows.net/{CONTAINER}/{ARQUIVO}?{SAS}"
print("vai ler:", URL.split("?")[0])

# COMMAND ----------

# Célula 2: teste de rede (o Free Edition restringe a saída para a internet; aqui se descobre se o Blob passa)
# Esperado se passar: "200 | 209 KB". Testado em 06/11/2026, 23h17: o Free Edition alcança o Blob (200). Se der ConnectionError ou timeout: o Blob está fora da lista; use o upload pela interface.
import requests
try:
    r = requests.get(URL, timeout=30)
    print(r.status_code, "|", len(r.content) // 1024, "KB")
    if r.status_code == 404: print("Arquivo não encontrado: confira o nome em ARQUIVO (o SAS não permite listar o container).")
    if r.status_code == 403: print("SAS recusado: confira se a URL foi colada inteira (o sig termina em %3D).")
except Exception as e:
    print("SEM ACESSO a partir do Databricks:", type(e).__name__, str(e)[:200])

# COMMAND ----------

# Célula 3: CSV -> pandas -> Spark -> tabela Delta
import io, pandas as pd
pdf = pd.read_csv(io.BytesIO(r.content))
print(pdf.shape)                                   # esperado: (846, 16)

# tipos conferidos antes de virar tabela: preço e área numéricos; quartos e banheiros com NULL; residencial booleano
for c in ["preco", "area_m2", "quartos", "banheiros", "preco_m2"]:
    pdf[c] = pd.to_numeric(pdf[c], errors="coerce")
pdf["residencial"] = pdf["residencial"].astype(bool)
pdf["id_anuncio"] = pdf["id_anuncio"].astype(str)

df = spark.createDataFrame(pdf)
df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable("workspace.default.anuncios")
print("tabela gravada:", spark.table("workspace.default.anuncios").count(), "linhas")   # esperado: 846

# COMMAND ----------

# Célula 4: a pergunta da oficina (esperado: Ilhéus 542 | 4231 | 3500 | 40.0  e  Itabuna 52 | 4457 | 2850 | 18.6)
display(spark.sql("""
SELECT cidade, COUNT(*) AS n, ROUND(AVG(preco)) AS media,
       PERCENTILE(preco, 0.5) AS mediana,
       ROUND(PERCENTILE(preco / area_m2, 0.5), 1) AS preco_m2_mediano
FROM workspace.default.anuncios
WHERE residencial AND area_m2 > 0 AND preco IS NOT NULL
GROUP BY cidade
"""))

# COMMAND ----------

# MAGIC %md
# MAGIC Depois disto: importe `oficina_sql_notebook.sql` para as demais consultas e a visualização, e crie o espaço Genie
# MAGIC em **Genie > New** apontando para `workspace.default.anuncios` (instruções no passo a passo).
