# Web scraping explicado: como um programa lê um site

Material da oficina "Da Web ao Databricks", UESC, 07/11/2026. Prof. Rafael Santos Novo Pereira.
Tudo o que está aqui foi executado em 06/11/2026; os números são dessa execução.

---

## 1. O que é web scraping

Web scraping é pedir uma página a um site **com um programa**, em vez de com o navegador, e extrair dela os dados que interessam.

O navegador faz três coisas quando você digita um endereço: pede a página ao servidor (um pedido HTTP), recebe um texto enorme chamado HTML, e desenha esse texto como uma página bonita. O scraper faz só a primeira e a segunda: pede e recebe. A terceira, em vez de desenhar, é **procurar** no texto o que você quer: preço, área, quartos, bairro.

```python
import requests
r = requests.get("https://www.vivareal.com.br/aluguel/bahia/ilheus/",
                 headers={"User-Agent": "oficina-uesc-estatistica/1.0 (uso educacional)"})
print(r.status_code)        # 200 = o site aceitou; 403 = recusou; 429 = "devagar"
print(len(r.text))          # o HTML inteiro, como texto
```

Dois números para guardar: **200** é "aqui está"; **403** é "não". Quando vem 403, o site decidiu não falar com você. A regra desta oficina é respeitar.

---

## 2. Antes de qualquer linha de código: o robots.txt

Todo site pode ter um arquivo de texto em `https://site.com.br/robots.txt`. Ele diz, para robôs, quais caminhos o site permite e quais proíbe. É uma convenção técnica (não é lei), mas é o primeiro lugar onde se olha, e desobedecer é o jeito mais rápido de ser bloqueado e de fazer algo que você não deveria.

Como se lê:

```
User-agent: *           <- vale para qualquer robô
Allow: /                <- pode entrar em tudo...
Disallow: /*?*placeId=  <- ...menos em URLs com este filtro
Disallow: /favorites    <- e nesta área
```

Três casos reais lidos em 06/11/2026:

| Site | O que o robots.txt diz | O que fizemos |
|---|---|---|
| VivaReal | `Allow: /`; proíbe URLs com filtros (`precoMaximo=`, `quartos=`, `ordem=`...) e áreas como `/favorites` | usamos `/aluguel/bahia/ilheus/?pagina=N`, que não está proibido; filtramos depois, no pandas, nunca na URL |
| Chaves na Mão | `Disallow: /*?*` (qualquer URL com `?`) e a paginação é `?pg=N` | só a página 1, que não tem `?`. 30 de 159 anúncios em Ilhéus. É pouco, e é o permitido |
| OLX | até o robots.txt responde 403 ao nosso robô | fora |

O robots.txt é a primeira camada. A segunda são os **termos de uso** do site (nesta oficina lemos só o robots.txt; está dito assim nos materiais). A terceira é a **LGPD** (Lei 13.709/2018): dado pessoal tem regras próprias. Preço de um imóvel não é dado pessoal; nome e telefone do anunciante são, e por isso não coletamos.

---

## 3. Como o robô se comporta (as cinco regras)

1. **Diz quem é.** Cada pedido leva um `User-Agent` com nome e finalidade: `oficina-uesc-estatistica/1.0 (uso educacional)`. O site pode ver, e pode nos bloquear se quiser.
2. **Espera.** `time.sleep(2)` entre páginas. Mais lento que um humano clicando, de propósito.
3. **Para quando o site diz não.** Se vier 403 ou 429, o programa interrompe. Não troca de IP, não muda o User-Agent, não "disfarça".
4. **Coleta só o necessário.** Atributos do imóvel. Nada do anunciante.
5. **Uso educacional, sem redistribuição.** O CSV fica na oficina.

Sobre a regra 3, um fato de 06/11/2026: QuintoAndar e Lopes montam os anúncios por JavaScript e não os entregam a um programa simples. Testamos com um navegador automatizado (Playwright) que se identificava como automatizado: a moldura do site apareceu, anúncio nenhum. Fazer aparecer exigiria o navegador fingir ser humano. Não fizemos. Dois portais que recusam é uma lição melhor do que quatro coletados na marra.

---

## 4. Onde os dados estão dentro da página

Aqui está o segredo que torna o scraping desta oficina fácil. Abra `https://www.vivareal.com.br/aluguel/bahia/ilheus/` no navegador, aperte **Ctrl+U** (ver código-fonte) e **Ctrl+F** por `ld+json`. Você vai achar isto (abreviado):

```html
<script type="application/ld+json">
{ "@type": "ItemList", "numberOfItems": 30,
  "itemListElement": [ { "item": {
      "@id": "2902416120",
      "additionalType": "https://schema.org/Apartment",
      "address": { "addressLocality": "Ilhéus", "addressRegion": "BA" },
      "offers": { "price": 4500, "priceCurrency": "BRL" },
      "floorSize": { "value": 76, "unitCode": "M2" },
      "numberOfBedrooms": 2,
      "numberOfBathroomsTotal": 2,
      "url": "https://www.vivareal.com.br/imovel/..." } },
    ... ] }
</script>
```

Isso é **JSON-LD no vocabulário schema.org**: um formato que o próprio site publica para que programas (o Google, por exemplo) entendam o conteúdo. Quando o site publica assim, não há HTML para adivinhar: é só `json.loads` e pronto.

Agora faça o mesmo em `https://www.lopes.com.br/busca/aluguel/ba/ilheus`: Ctrl+U, Ctrl+F `R$`. Zero ocorrências. A página que o programa recebe não tem nenhum preço; eles chegam depois, por JavaScript. Mesma cidade, mesmo tipo de site, e o programa recebe coisas completamente diferentes. **A fonte escolhe você.**

### O método geral, para qualquer site (cinco passos)

1. Ler o `robots.txt`.
2. Pedir a página com `requests` e olhar o `status_code` e o tamanho.
3. Procurar os dados na forma mais estruturada que existir, nesta ordem: `application/ld+json` (schema.org) → JSON embutido pelo framework (`__NEXT_DATA__`, `__INITIAL_STATE__`) → só então HTML com classes (`soup.select(".classe")`, o caminho mais frágil).
4. Se os dados só aparecem por JavaScript: F12 > Network > Fetch/XHR mostra a chamada interna que o site faz. É uma API não documentada: muda sem aviso. Ou um navegador automatizado honesto. Se nem assim, respeite.
5. Validar com **uma página** antes de coletar tudo: conte os registros, compare com o que o site declara ("mais de 726 imóveis"), confira se preço e área vieram como número.

---

## 5. O código, linha a linha

O arquivo é `coleta/scraper_imoveis.py`. Tem comentários em cada passo; aqui está o esqueleto.

```python
UA = {"User-Agent": "oficina-uesc-estatistica/1.0 (uso educacional)"}   # quem somos
PAUSA = 2.0                                                               # segundos entre páginas

def extrair_pagina(html, cidade, pagina, portal):
    soup = BeautifulSoup(html, "lxml")                                    # HTML vira árvore pesquisável
    for sc in soup.select("script[type='application/ld+json']"):          # cada bloco ld+json...
        d = json.loads(sc.string)                                         # ...vira dicionário
        if d.get("@type") != "ItemList": continue                         # só a lista de anúncios interessa
        for el in d["itemListElement"]:                                   # cada anúncio...
            it = el["item"]
            registros.append({"id_anuncio": it["@id"],                    # ...vira um dicionário nosso
                              "preco": it["offers"]["price"],
                              "area_m2": it["floorSize"]["value"], ...})

def coletar(cidade, max_paginas, portal):
    for p in range(1, max_paginas + 1):
        r = requests.get(BASE + f"?pagina={p}", headers=UA)               # o pedido
        if r.status_code != 200: break                                    # recusou? paramos
        regs = extrair_pagina(r.text, cidade, p, portal)
        if not regs: break                                                # página vazia? acabou
        time.sleep(PAUSA)                                                 # a pausa. Sempre.
```

O que cada linha do CSV guarda (13 colunas): `portal, id_anuncio, cidade, bairro_texto, bairro_url, tipo, preco, area_m2, quartos, banheiros, pagina, url, coletado_em`.

---

## 6. O que aconteceu em 06/11/2026 (números reais)

```
vivareal ilheus pagina 1: 30 anuncios
...
vivareal ilheus pagina 25: 3 anuncios
vivareal ilheus pagina 26: 0 anuncios
zap ilheus pagina 1: 30 anuncios
...
chavesnamao ilheus pagina 1: 30 anuncios (so a pagina 1)
1658 linhas coletadas em 196 s
```

60 requisições, 2 segundos entre elas, nenhum bloqueio. Ilhéus no VivaReal: 723 anúncios (o portal declara "mais de 726"; a diferença de 3 são anúncios que mudaram entre as contagens, ou que o portal conta e não lista; não sabemos qual). Itabuna: 88.

---

## 7. Coletar é a parte fácil. A base esconde coisas.

Quatro descobertas da própria execução, todas antes de qualquer média:

| Descoberta | Número | Decisão |
|---|---|---|
| **Ids repetidos.** VivaReal e ZAP são do mesmo grupo e têm o mesmo estoque (607 ids nos dois). E o mesmo anúncio cai em duas páginas quando o portal reordena a lista entre uma requisição e outra. | 1.658 linhas → 846 anúncios únicos | `drop_duplicates("id_anuncio")` |
| **Bairro com duas grafias.** No VivaReal o bairro vem da URL, sem acento; no ZAP e no Chaves na Mão vem do texto, com acento. "Nossa Senhora da Vitória" virava dois bairros. | 193 anúncios num, 16 noutro | padronizar sem acento |
| **Nem tudo é moradia.** Salas, lojas, galpões, terrenos e vagas estão na mesma lista. E no Chaves na Mão o schema.org chama galpão de `Accommodation`. | 846 → 594 residenciais | filtrar por tipo; tipo do Chaves na Mão lido da URL |
| **Galpões de R$ 90.000 e R$ 60.000.** Iguape (Ilhéus) e Ferradas (Itabuna). | média bruta: Itabuna R$ 6.678, Ilhéus R$ 4.780 | mediana, não média |

Resultado, residencial e sem duplicata:

| cidade | n | média | mediana | R$/m² mediano |
|---|---|---|---|---|
| Ilhéus | 542 | R$ 4.231 | **R$ 3.500** | 40,0 |
| Itabuna | 52 | R$ 4.457 | **R$ 2.850** | 18,6 |

Pela média bruta, Itabuna parecia mais cara que Ilhéus. Pela mediana residencial, é R$ 650 mais barata. Nenhuma das quatro decisões é "estatística" no sentido da prova. Todas mudam o número final. **Ter muitos dados não significa ter bons dados.**

---

## 8. Glossário rápido

- **HTTP, status 200/403/429**: o protocolo do pedido e as respostas "ok", "proibido", "muitos pedidos".
- **HTML**: o texto que descreve a página. **JavaScript**: código que roda no navegador e pode montar a página depois que o HTML chegou (por isso Lopes vem "vazio").
- **JSON**: formato de dados em texto, com chaves e valores. **JSON-LD / schema.org**: JSON com vocabulário padronizado (`Apartment`, `offers`, `price`) que sites publicam para programas.
- **User-Agent**: o nome que o programa diz ao site. **robots.txt**: as regras do site para robôs.
- **requests / BeautifulSoup / pandas**: pedir a página / procurar nela / organizar e analisar a tabela.
- **Outlier**: valor muito fora do padrão (o galpão de R$ 90.000). Puxa a média; não puxa a mediana.

## 9. Para ir além

- Repita a coleta daqui a uma semana e compare: quantos anúncios entraram e saíram, a mediana mudou? Nasce uma série temporal (`coletado_em` já está lá).
- Regressão de preço em área, quartos e bairro: a base tem as colunas. Os resíduos grandes são anúncios para olhar um a um.
- Leituras: Krotov, Johnson e Silva (2020), "Tutorial: Legality and Ethics of Web Scraping", *Communications of the AIS*; Salganik (2018), *Bit by Bit*, cap. 2 (dados observacionais); Landers et al. (2016), "A Primer on Theory-Driven Web Scraping", *Psychological Methods*.
