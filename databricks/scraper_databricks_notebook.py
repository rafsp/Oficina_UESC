# Databricks notebook source
# MAGIC %md
# MAGIC # Oficina UESC: coleta VivaReal dentro do Databricks (Free Edition)
# MAGIC Só funciona se o serverless do Free Edition alcançar www.vivareal.com.br. A documentação diz que a saída
# MAGIC para a internet é restrita a "um conjunto limitado de domínios confiáveis", sem lista pública.
# MAGIC Rode a célula 1 primeiro. Resultado em 06/11/2026, 22h29 (conta MBA_Turma9): 403, 5 KB, sem ld+json. O site bloqueia IP de datacenter.
# MAGIC Portanto a coleta roda no notebook de cada um e o CSV sobe pelo volume. As células 2 a 4 ficam como referência de como seria.
# MAGIC Sem bibliotecas extras: usa só requests, re, json e pandas, que já vêm no ambiente serverless.

# COMMAND ----------

# Célula 1: teste de rede (30 segundos). Esperado se funcionar: "200 OK, ld+json encontrado: True"
import requests, re, json, time
UA = {"User-Agent": "oficina-uesc-estatistica/1.0 (uso educacional)", "Accept-Language": "pt-BR,pt;q=0.9"}
try:
    r = requests.get("https://www.vivareal.com.br/aluguel/bahia/ilheus/", headers=UA, timeout=20)
    print(r.status_code, "OK" if r.ok else "", "ld+json encontrado:", "application/ld+json" in r.text)
except Exception as e:
    print("Sem acesso a partir do Databricks:", type(e).__name__, str(e)[:200])
    print("Plano: rodar scraper_imoveis.py no seu computador e subir anuncios_limpo.csv pelo volume.")

# COMMAND ----------

# Célula 2: extração sem BeautifulSoup (regex pega os blocos <script type="application/ld+json">)
from datetime import datetime
BLOCO = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)

def extrair_pagina(html, cidade, pagina):
    regs = []
    for bruto in BLOCO.findall(html):
        try:
            d = json.loads(bruto)
        except json.JSONDecodeError:
            continue
        if not (isinstance(d, dict) and d.get("@type") == "ItemList"):
            continue
        for el in d.get("itemListElement", []):
            it = el.get("item", {})
            url = it.get("url", "")
            m = re.search(r"/imovel/[a-z0-9-]+?-(?:[0-9]+-quartos?-)?(.+?)-bairros-", url)
            regs.append({
                "portal": "vivareal",
                "id_anuncio": it.get("@id"),
                "cidade": (it.get("address") or {}).get("addressLocality", cidade),
                "bairro_url": m.group(1).replace("-", " ") if m else None,
                "tipo": (it.get("additionalType") or "").split("/")[-1],
                "preco": (it.get("offers") or {}).get("price"),
                "area_m2": (it.get("floorSize") or {}).get("value"),
                "quartos": it.get("numberOfBedrooms"),
                "banheiros": it.get("numberOfBathroomsTotal"),
                "pagina": pagina,
                "url": url,
                "coletado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
    return regs

def coletar(cidade, max_paginas=30, pausa=2.0):
    base = f"https://www.vivareal.com.br/aluguel/bahia/{cidade}/"
    todos = []
    for p in range(1, max_paginas + 1):
        r = requests.get(base + (f"?pagina={p}" if p > 1 else ""), headers=UA, timeout=30)
        if r.status_code != 200:
            print(cidade, "pagina", p, "status", r.status_code, "parando"); break
        regs = extrair_pagina(r.text, cidade, p)
        print(cidade, "pagina", p, len(regs), "anuncios")
        if not regs: break
        todos.extend(regs); time.sleep(pausa)
    return todos

# COMMAND ----------

# Célula 3: coleta (comece com 3 páginas; depois 30). Ilhéus levou 1 min 11 s em 06/11/2026 fora do Databricks.
import pandas as pd
registros = coletar("ilheus", 3) + coletar("itabuna", 3)
df = pd.DataFrame(registros)
print(df.shape); display(df.head())

# COMMAND ----------

# Célula 4: limpeza (as mesmas quatro decisões do roteiro) e gravação como tabela Delta
limpo = df.drop_duplicates("id_anuncio").copy()
limpo["bairro"] = (limpo.bairro_url.fillna("")
    .str.replace("^comercial ", "", regex=True)
    .str.replace("^deposito armazem ", "", regex=True).str.title())
limpo["bairro"] = limpo.bairro.mask(limpo.bairro == "")
limpo["residencial"] = limpo.tipo.isin(["Apartment", "House"])
limpo["preco"] = pd.to_numeric(limpo.preco, errors="coerce")
limpo["area_m2"] = pd.to_numeric(limpo.area_m2, errors="coerce")
limpo["quartos"] = pd.to_numeric(limpo.quartos, errors="coerce")      # float com NaN: vira DOUBLE com NULL
limpo["banheiros"] = pd.to_numeric(limpo.banheiros, errors="coerce")
limpo["preco_m2"] = (limpo.preco / limpo.area_m2).round(1)
print("brutos", len(df), "unicos", len(limpo), "residenciais", int(limpo.residencial.sum()))

spark.createDataFrame(limpo).write.mode("overwrite").saveAsTable("workspace.default.anuncios")
display(spark.sql("SELECT cidade, COUNT(*) n, PERCENTILE(preco, 0.5) mediana FROM workspace.default.anuncios WHERE residencial GROUP BY cidade"))
