"""
Oficina UESC 07/11/2026. Um comando faz tudo que roda fora do Databricks:
coleta no VivaReal (Ilheus e Itabuna), limpeza, resumo na tela, CSV e 4 graficos.

  python oficina_coleta.py            # completo: ~2 min (30 paginas por cidade)
  python oficina_coleta.py --rapido   # 5 paginas por cidade: ~50 s
  python oficina_coleta.py --so-limpeza   # nao coleta: relê anuncios_todos.csv e refaz limpeza, resumo e graficos
"""
import sys, time, unicodedata
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scraper_imoveis import coletar, tipo_chavesnamao

MAXP = 5 if "--rapido" in sys.argv else 30
def linha(t=""): print(t)
def titulo(t): print("\n" + "=" * 70 + "\n" + t + "\n" + "=" * 70)

t0 = time.time()
titulo("1. COLETA  (VivaReal, ZAP e Chaves na Mao; robo identificado, 2 s entre paginas)")
if "--so-limpeza" in sys.argv:
    df = pd.read_csv("anuncios_todos.csv")
    linha(f"(sem coleta) lendo anuncios_todos.csv: {len(df)} linhas, coletadas em {df.coletado_em.min()} a {df.coletado_em.max()}")
else:
    regs = []
    for cidade in ["ilheus", "itabuna"]:
        for portal in ["vivareal", "zap", "chavesnamao"]:
            regs += coletar(cidade, MAXP, portal)
    df = pd.DataFrame(regs)
    df.to_csv("anuncios_todos.csv", index=False)
    linha(f"\n{len(df)} linhas coletadas em {time.time()-t0:.0f} s  ->  anuncios_todos.csv")
# Chaves na Mao: tipo pela URL (o schema.org desse portal chama de 'Accommodation' tanto flat quanto galpao)
df.loc[df.portal == "chavesnamao", "tipo"] = df.loc[df.portal == "chavesnamao", "url"].map(tipo_chavesnamao)
for (portal, cidade), n in df.groupby(["portal", "cidade"]).size().items(): linha(f"   {portal:9s} {cidade:8s} {n}")
linha("   chavesnamao: so a pagina 1 por cidade, porque o robots.txt proibe query string (e a paginacao e ?pg=N).")
linha("   quintoandar, lopes: nao entregam anuncios a programas. olx, imovelweb: 403. (testados em 06/11/2026) Ficam fora.")

titulo("2. DOIS PORTAIS, UM ESTOQUE")
viva = set(df[df.portal == "vivareal"].id_anuncio); zap = set(df[df.portal == "zap"].id_anuncio)
linha(f"ids no VivaReal ..... {len(viva)}")
linha(f"ids no ZAP .......... {len(zap)}")
linha(f"nos dois ............ {len(viva & zap)}   (mesmo grupo, mesmo estoque)")
linha(f"so em um deles ...... {len(viva ^ zap)}")
linha("quem soma os dois portais sem olhar o id conta quase tudo em dobro.")

titulo("3. O QUE A BASE ESCONDE")
dup = df.id_anuncio.duplicated().sum()
linha(f"ids repetidos (entre paginas e entre portais) .. {dup}")
linha(f"bairro vazio, lido do texto ........ {df.bairro_texto.isna().sum()}   (no VivaReal a regra falha nos comerciais)")
linha(f"bairro vazio, lido da URL .......... {df.bairro_url.isna().sum()}   (ZAP e Chaves na Mao nao separam o bairro na URL)")
linha("tipos de imovel:")
for t, n in df.tipo.value_counts().items(): linha(f"   {t:16s} {n}")
linha(f"maior preco ........................ R$ {df.preco.max():,.0f}  ({df.sort_values('preco').iloc[-1].bairro_url})".replace(",", "."))

titulo("4. QUATRO DECISOES")
limpo = df.drop_duplicates("id_anuncio").copy()
limpo["bairro"] = (limpo.bairro_url.fillna("").str.replace("^comercial ", "", regex=True)
                   .str.replace("^deposito armazem ", "", regex=True).str.title())
# no ZAP a URL nao separa o bairro; usa o texto do anuncio quando a URL nao deu
limpo["bairro"] = limpo.bairro.where(limpo.bairro != "", limpo.bairro_texto.fillna(""))
# mesmo bairro, duas grafias (URL sem acento, texto com acento): tira acentos de todos e padroniza
sem_acento = lambda t: unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode()
limpo["bairro"] = limpo.bairro.map(sem_acento).str.strip().str.title()
limpo["bairro"] = limpo.bairro.mask(limpo.bairro == "")
limpo["residencial"] = limpo.tipo.isin(["Apartment", "House", "Accommodation"])   # Accommodation = flat/kitnet/studio
limpo["preco_m2"] = (limpo.preco / limpo.area_m2).round(1)
limpo.to_csv("anuncios_limpo.csv", index=False)
res = limpo[limpo.residencial & (limpo.area_m2 > 0) & limpo.preco.notna()]
linha(f"sem duplicata ........ {len(df)} -> {len(limpo)}   (drop_duplicates por id_anuncio; fica a primeira ocorrencia, do VivaReal)")
linha(f"so moradia ........... {len(limpo)} -> {len(res)}   (Apartment, House ou kitnet; com preco e area)")
linha(f"mediana, nao media ... ver tabela abaixo")
linha(f"bairro padronizado ... prefixos 'comercial' e 'deposito armazem' removidos; texto do anuncio quando a URL nao separa (ZAP); sem acento, para 'Vitória' e 'Vitoria' serem um so")
linha(f"\n-> anuncios_limpo.csv  ({len(limpo)} linhas, sobe no Databricks)")

titulo("5. A RESPOSTA  (residencial, sem duplicata)")
bruto = limpo.groupby("cidade").preco.mean().round(0)
tab = res.groupby("cidade").agg(n=("preco", "size"), media=("preco", "mean"), mediana=("preco", "median"),
                                 minimo=("preco", "min"), maximo=("preco", "max"), preco_m2=("preco_m2", "median")).round(1)
tab.insert(0, "media_bruta", bruto)
print(tab.to_string())
linha("\nmedia_bruta = com galpoes e lojas: Itabuna parecia mais cara. Mediana residencial diz o contrario.")

titulo("6. ILHEUS POR BAIRRO  (10 ou mais anuncios residenciais)")
tb = res[res.cidade == "Ilhéus"].groupby("bairro").preco.agg(n="size", mediana="median").query("n >= 10").sort_values("mediana", ascending=False)
print(tb.to_string())

# ---- graficos ----
MAG, INK, GRAY = "#ED145B", "#181818", "#75838B"
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": GRAY})
x = res[res.cidade == "Ilhéus"].preco
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=160)
ax.hist(x, bins=range(0, 20001, 1000), color=MAG, edgecolor="white")
ax.axvline(x.median(), color=INK, ls="--"); ax.text(x.median() + 200, ax.get_ylim()[1] * .9, f"mediana R$ {x.median():,.0f}".replace(",", "."), color=INK)
ax.axvline(x.mean(), color=GRAY, ls=":"); ax.text(x.mean() + 200, ax.get_ylim()[1] * .78, f"média R$ {x.mean():,.0f}".replace(",", "."), color=GRAY)
ax.set_xlabel("Aluguel mensal (R$)"); ax.set_ylabel("Anúncios"); ax.set_title(f"Ilhéus, residencial, 3 portais (n = {len(x)}), coleta de {pd.to_datetime(df.coletado_em).max():%d/%m/%Y}", fontsize=10, color=GRAY, loc="left")
fig.tight_layout(); fig.savefig("g1_hist_ilheus.png"); plt.close()
fig, ax = plt.subplots(figsize=(8, 4.6), dpi=160); t2 = tb.sort_values("mediana")
ax.barh(t2.index, t2.mediana, color=MAG)
for i, (n, m) in enumerate(zip(t2.n, t2.mediana)): ax.text(m + 60, i, f"R$ {m:,.0f}  (n={n})".replace(",", "."), va="center", fontsize=8)
ax.set_xlim(0, t2.mediana.max() * 1.35); ax.set_xlabel("Mediana do aluguel (R$)"); ax.set_title("Ilhéus, mediana por bairro", fontsize=10, color=GRAY, loc="left")
fig.tight_layout(); fig.savefig("g2_bairros_ilheus.png"); plt.close()
fig, ax = plt.subplots(figsize=(8, 4.2), dpi=160)
for c, col in [("Ilhéus", MAG), ("Itabuna", INK)]:
    s = res[(res.cidade == c) & (res.area_m2 <= 400)]; ax.scatter(s.area_m2, s.preco, s=14, alpha=.55, color=col, label=f"{c} (n={len(s)})", edgecolors="none")
ax.set_xlabel("Área (m²)"); ax.set_ylabel("Aluguel (R$)"); ax.legend(frameon=False); ax.set_title("Preço e área, residencial até 400 m²", fontsize=10, color=GRAY, loc="left")
fig.tight_layout(); fig.savefig("g3_preco_area.png"); plt.close()
fig, ax = plt.subplots(figsize=(8, 3.6), dpi=160)
ct = limpo.groupby(["cidade", "tipo"]).size().unstack(fill_value=0)
ren = {"Apartment": "Apartamento", "House": "Casa", "Store": "Loja", "Place": "Sala/outros", "Landform": "Terreno", "ParkingFacility": "Vaga"}
ct = ct[[c for c in ren if c in ct.columns]].rename(columns=ren)
ct.plot.barh(stacked=True, ax=ax, color=[MAG, INK, GRAY, "#BDBFC7", "#D9D9D9", "#F4F5F7"][:ct.shape[1]], edgecolor="white")
ax.set_xlabel("Anúncios"); ax.set_ylabel(""); ax.legend(frameon=False, ncol=3, fontsize=8); ax.set_title("O que há na base: nem tudo é moradia", fontsize=10, color=GRAY, loc="left")
fig.tight_layout(); fig.savefig("g4_tipos.png"); plt.close()

titulo("PRONTO")
linha("arquivos: anuncios_todos.csv, anuncios_limpo.csv, g1_hist_ilheus.png, g2_bairros_ilheus.png, g3_preco_area.png, g4_tipos.png")
linha(f"tempo total: {time.time()-t0:.0f} s")
