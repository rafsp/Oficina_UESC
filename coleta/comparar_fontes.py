"""Verifica, no dia da oficina, o que cada portal entrega a um programa simples (requests).
Resultado vai para comparar_fontes.txt. Nao coleta em massa: 1 pagina por portal e cidade."""
import json, re, time, requests
from bs4 import BeautifulSoup
import pandas as pd
UA={"User-Agent":"oficina-uesc-estatistica/1.0 (uso educacional)","Accept-Language":"pt-BR"}
out=[]
def log(s): print(s); out.append(s)
for cid in ["ilheus","itabuna"]:
    # QuintoAndar: pagina embute JSON (__NEXT_DATA__) mas a lista vem vazia para o servidor
    r=requests.get(f"https://www.quintoandar.com.br/alugar/imovel/{cid}-ba-brasil",headers=UA,timeout=30)
    soup=BeautifulSoup(r.text,"lxml"); nd=soup.find("script",id="__NEXT_DATA__")
    hits={}
    if nd:
        try: hits=json.loads(nd.string)["props"]["pageProps"]["initialState"]["search"]["markers"]["hits"]
        except Exception as e: hits={"erro":str(e)}
    log(f"QuintoAndar {cid}: status {r.status_code}, {len(r.text)//1024} KB, hits found={hits.get('found')} items={len(hits.get('items',[]))}")
    time.sleep(2)
    # Lopes: HTML grande, sem precos (renderizado por JavaScript)
    r=requests.get(f"https://www.lopes.com.br/busca/aluguel/ba/{cid}",headers=UA,timeout=30)
    log(f"Lopes {cid}: status {r.status_code}, {len(r.text)//1024} KB, ocorrencias de 'R$' no HTML: {r.text.count('R$')}")
    time.sleep(2)
    # ZAP: mesmo grupo (OLX) do VivaReal, tambem em JSON-LD
    r=requests.get(f"https://www.zapimoveis.com.br/aluguel/imoveis/ba+{cid}/",headers=UA,timeout=30)
    soup=BeautifulSoup(r.text,"lxml"); ids=[]
    for sc in soup.select("script[type='application/ld+json']"):
        try: d=json.loads(sc.string or "{}")
        except Exception: continue
        if isinstance(d,dict) and d.get("@type")=="ItemList":
            ids=[e["item"]["@id"] for e in d["itemListElement"]]
    viva=pd.read_csv(f"anuncios_{cid}.csv").id_anuncio.astype(str)
    comuns=len(set(ids)&set(viva))
    log(f"ZAP {cid}: status {r.status_code}, {len(ids)} anuncios na pagina 1, {comuns} com o mesmo id no VivaReal")
    time.sleep(2)
open("comparar_fontes.txt","w").write("\n".join(out)+"\n")
