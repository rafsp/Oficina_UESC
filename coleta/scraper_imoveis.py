"""
scraper_imoveis.py  ·  Oficina UESC "Da Web ao Databricks", 07/11/2026

O QUE ESTE ARQUIVO FAZ, EM UMA FRASE
  Pede ao portal de imóveis a mesma página que você veria no navegador, encontra dentro dela
  o bloco de dados que o próprio site publica para programas (JSON-LD, padrão schema.org)
  e guarda cada anúncio como uma linha de CSV.

FONTES (testadas em 06/11/2026 com o robô identificado)
  VivaReal      entrega 30 anúncios por página, paginação por ?pagina=N        -> coletamos tudo
  ZAP Imóveis   mesmo grupo, mesmo formato, mesmo estoque                      -> coletamos tudo (serve para a lição da duplicação)
  Chaves na Mão entrega, mas o robots.txt proíbe qualquer "?" na URL (Disallow: /*?*)
                e a paginação é ?pg=N                                          -> só a página 1, por respeito ao robots.txt
  QuintoAndar, Lopes   a página chega, o anúncio não (é montado por JavaScript) -> fora
  OLX, Imovelweb       403 (bloqueio Cloudflare)                               -> fora. Não se disfarça.

REGRAS DE CONDUTA DO ROBÔ
  1. Diz quem é (User-Agent).           2. Espera 2 s entre páginas.
  3. Para se o site responder != 200.   4. Guarda só atributos do imóvel; nada do anunciante.
  5. Uso educacional, sem redistribuir.

COMO RODAR
  python scraper_imoveis.py                 # Ilhéus e Itabuna, até 30 páginas por portal
  python scraper_imoveis.py ilheus 5        # só Ilhéus, 5 páginas
  Saída: anuncios_<portal>_<cidade>.csv e anuncios_todos.csv (uma linha por anúncio, 13 colunas)
"""

# ---------- bibliotecas ----------
import csv, json, re, sys, time          # csv: salvar; json: ler o bloco de dados; re: achar padrões em texto; time: pausa
from datetime import datetime            # para anotar quando cada linha foi coletada
import requests                          # faz o pedido HTTP (o mesmo que o navegador faz, sem desenhar a página)
from bs4 import BeautifulSoup            # lê o HTML e deixa buscar etiquetas (<script>, <div>...) com facilidade

# ---------- configuração ----------
# Quem somos. O site vê isto em cada pedido. Um robô honesto se identifica.
UA = {"User-Agent": "oficina-uesc-estatistica/1.0 (uso educacional; contato: professor)",
      "Accept-Language": "pt-BR,pt;q=0.9"}

# Pausa entre páginas, em segundos. Mais lento que um humano clicando, de propósito.
PAUSA = 2.0

# Endereço da busca de aluguel em cada portal. {cidade} vira "ilheus" ou "itabuna".
BASES = {"vivareal": "https://www.vivareal.com.br/aluguel/bahia/{cidade}/",
         "zap": "https://www.zapimoveis.com.br/aluguel/imoveis/ba+{cidade}/"}


# ---------- 1. ler uma página do VivaReal ou do ZAP ----------
def extrair_pagina(html, cidade, pagina, portal="vivareal"):
    """Recebe o HTML de UMA página de busca e devolve uma lista de anúncios (um dicionário por anúncio).

    Onde estão os dados: dentro de <script type="application/ld+json"> ... </script>.
    É um JSON no vocabulário schema.org, feito para programas lerem. Não precisamos adivinhar classes de HTML.
    """
    soup = BeautifulSoup(html, "lxml")   # transforma o texto HTML numa árvore pesquisável
    registros = []

    # Pode haver vários blocos ld+json na página (empresa, breadcrumb, lista...). Olhamos um a um.
    for sc in soup.select("script[type='application/ld+json']"):
        try:
            d = json.loads(sc.string or "{}")      # texto -> dicionário Python
        except json.JSONDecodeError:
            continue                               # bloco quebrado: ignora e segue

        # Só nos interessa o bloco que é uma lista de itens (os 30 anúncios da página).
        if not (isinstance(d, dict) and d.get("@type") == "ItemList"):
            continue

        for el in d.get("itemListElement", []):    # cada elemento da lista...
            it = el.get("item", {})                # ...tem um "item" com os dados do imóvel
            url = it.get("url", "")

            # Bairro, caminho 1: o texto do anúncio termina em "... em <bairro>, <cidade>"
            kw = it.get("keywords", "") or it.get("name", "")
            m = re.search(r"em\s+(.+?),\s*([^,]+)$", kw)
            bairro_texto = m.group(1).strip() if m else ""

            # Bairro, caminho 2: a URL do VivaReal tem ".../<bairro>-bairros-<cidade>/..."
            # Guardamos os dois de propósito: na limpeza vemos qual é mais confiável.
            m2 = re.search(r"/imovel/[a-z0-9-]+?-(?:[0-9]+-quartos?-)?(.+?)-bairros-", url)
            bairro_url = m2.group(1).replace("-", " ") if m2 else ""

            fs = it.get("floorSize") or {}         # área: {"value": 76, "unitCode": "M2"}
            of = it.get("offers") or {}            # oferta: {"price": 4500, "priceCurrency": "BRL"}
            tipo = (it.get("additionalType") or "").split("/")[-1]   # "https://schema.org/Apartment" -> "Apartment"

            registros.append({
                "portal": portal,
                "id_anuncio": it.get("@id"),                                     # identificador do anúncio no portal
                "cidade": (it.get("address") or {}).get("addressLocality", cidade),
                "bairro_texto": bairro_texto,
                "bairro_url": bairro_url,
                "tipo": tipo,                                                    # Apartment, House, Store, Place...
                "preco": of.get("price"),                                        # aluguel mensal, R$
                "area_m2": fs.get("value"),
                "quartos": it.get("numberOfBedrooms"),
                "banheiros": it.get("numberOfBathroomsTotal"),
                "pagina": pagina,                                                # de qual página veio (serve para achar duplicatas)
                "url": url,
                "coletado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),       # carimbo de data e hora
            })
    return registros


# ---------- 2. ler a página 1 do Chaves na Mão ----------
def tipo_chavesnamao(url):
    """No Chaves na Mão o @type do schema.org não é confiável: 'Accommodation' serve tanto para flat
    quanto para galpão. O tipo verdadeiro está no começo da URL: /imovel/<tipo>-para-alugar-...
    Lição: nem todo campo bem formatado é um campo correto."""
    m = re.search(r"/imovel/([a-z]+)", url or "")
    t = m.group(1) if m else ""
    return {"apartamento": "Apartment", "cobertura": "Apartment", "casa": "House", "sobrado": "House", "chacara": "House", "sitio": "House",
            "flat": "Accommodation", "kitnet": "Accommodation", "kitchenette": "Accommodation", "studio": "Accommodation",
            "loja": "Store", "ponto": "Store", "sala": "Place", "galpao": "Place", "predio": "Place", "terreno": "Landform", "lote": "Landform"}.get(t, "Place")


def extrair_chavesnamao(html, cidade):
    """Chaves na Mão publica em ld+json também, mas com outra estrutura:
    RealEstateListing > offers (ItemList) > Offer > itemOffered. Só a página 1 (ver cabeçalho)."""
    soup = BeautifulSoup(html, "lxml")
    regs = []
    for sc in soup.select("script[type='application/ld+json']"):
        try:
            d = json.loads(sc.string or "{}")
        except json.JSONDecodeError:
            continue
        if not (isinstance(d, dict) and d.get("@type") == "RealEstateListing"):
            continue
        for of in (d.get("offers") or {}).get("itemListElement", []):
            it = of.get("itemOffered") or {}
            url = of.get("url", "")
            m = re.search(r"/imovel/.*?-ba-" + cidade + r"-(.+?)-\d+m2", url)        # bairro vem da URL
            fs = it.get("floorSize") or {}
            area = re.search(r"[\d\.,]+", str(fs.get("unitText") or fs.get("value") or ""))   # a área vem como texto "90m²"
            tipo = tipo_chavesnamao(url)
            addr = it.get("address") or {}
            regs.append({
                "portal": "chavesnamao", "id_anuncio": re.search(r"/id-(\d+)/", url).group(1) if re.search(r"/id-(\d+)/", url) else None,
                "cidade": {"ilheus": "Ilhéus", "itabuna": "Itabuna"}[cidade], "bairro_texto": addr.get("addressLocality", ""),
                "bairro_url": m.group(1).replace("-", " ") if m else "",
                "tipo": tipo, "preco": float(of["price"]) if of.get("price") and float(of["price"]) > 0 else None,  # preço 0 = "sob consulta" -> vazio
                "area_m2": float(area.group(0).replace(".", "").replace(",", ".")) if area else None, "quartos": it.get("numberOfBedrooms"), "banheiros": it.get("numberOfBathroomsTotal"),
                "pagina": 1, "url": url, "coletado_em": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
    return regs


# ---------- 3. o laço de páginas ----------
def coletar(cidade, max_paginas=30, portal="vivareal"):
    """Pede página por página até vir uma vazia (ou até max_paginas). Dorme PAUSA segundos entre pedidos."""
    if portal == "chavesnamao":
        # Uma página só, sem "?" na URL, porque o robots.txt do site proíbe query string.
        r = requests.get(f"https://www.chavesnamao.com.br/imoveis-para-alugar/ba-{cidade}/", headers=UA, timeout=30)
        regs = extrair_chavesnamao(r.text, cidade) if r.status_code == 200 else []
        print(f"chavesnamao {cidade} pagina 1: {len(regs)} anuncios (so a pagina 1: robots.txt proibe query string, e a paginacao e ?pg=N)")
        time.sleep(PAUSA)
        return regs

    todos = []
    for p in range(1, max_paginas + 1):
        url = BASES[portal].format(cidade=cidade) + (f"?pagina={p}" if p > 1 else "")   # página 1 sem "?pagina="
        r = requests.get(url, headers=UA, timeout=30)   # o pedido. r.status_code diz se o site aceitou (200) ou recusou (403, 429...)
        if r.status_code != 200:
            print(f"{portal} {cidade} pagina {p}: status {r.status_code}, parando")   # recusou? paramos. Não insistimos.
            break
        regs = extrair_pagina(r.text, cidade, p, portal)
        print(f"{portal} {cidade} pagina {p}: {len(regs)} anuncios")
        if not regs:                                    # página vazia = acabaram os anúncios
            break
        todos.extend(regs)
        time.sleep(PAUSA)                               # a pausa. Sempre.
    return todos


# ---------- 4. salvar ----------
def salvar(regs, nome):
    """Lista de dicionários -> arquivo CSV com cabeçalho, em UTF-8."""
    if not regs:
        return
    with open(nome, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(regs[0].keys()))
        w.writeheader(); w.writerows(regs)
    print("salvo", nome, len(regs), "linhas")


# ---------- 5. ponto de entrada ----------
if __name__ == "__main__":
    cidades = [sys.argv[1]] if len(sys.argv) > 1 else ["ilheus", "itabuna"]   # argumento 1: cidade (opcional)
    maxp = int(sys.argv[2]) if len(sys.argv) > 2 else 30                       # argumento 2: máximo de páginas (opcional)
    tudo = []
    for c in cidades:
        for portal in ["vivareal", "zap", "chavesnamao"]:
            regs = coletar(c, maxp, portal)
            salvar(regs, f"anuncios_{portal}_{c}.csv")
            tudo.extend(regs)
    salvar(tudo, "anuncios_todos.csv")      # tudo junto: é este arquivo que oficina_coleta.py limpa
