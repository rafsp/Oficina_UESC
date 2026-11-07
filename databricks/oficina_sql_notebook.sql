-- Databricks notebook source
-- MAGIC %md
-- MAGIC # Oficina UESC: a pergunta em SQL
-- MAGIC Tabela `workspace.default.anuncios`, criada a partir de `anuncios_limpo.csv` (VivaReal, ZAP e Chaves na Mão, 06/11/2026, 23h38 a 23h42).
-- MAGIC Rode célula a célula (Shift+Enter). Resultados esperados com a base de 06/11 estão em cada célula.

-- COMMAND ----------

-- 1. A tabela chegou inteira? (esperado: 846 linhas, 16 colunas)
SELECT COUNT(*) AS linhas FROM workspace.default.anuncios;

-- COMMAND ----------

-- 2. O que há na base (esperado: Ilhéus Apartment 437, Place 132, House 105, Store 75 ...)
SELECT cidade, tipo, COUNT(*) AS n
FROM workspace.default.anuncios
GROUP BY cidade, tipo
ORDER BY cidade, n DESC;

-- COMMAND ----------

-- 3. A PERGUNTA DA OFICINA: aluguel residencial por cidade
-- esperado: Ilhéus 542 | 4231 | 3500 | 40.0      Itabuna 52 | 4457 | 2850 | 18.6
SELECT cidade,
       COUNT(*)                                   AS n,
       ROUND(AVG(preco))                          AS media,
       PERCENTILE(preco, 0.5)                     AS mediana,
       ROUND(PERCENTILE(preco / area_m2, 0.5), 1) AS preco_m2_mediano
FROM workspace.default.anuncios
WHERE residencial AND area_m2 > 0 AND preco IS NOT NULL   -- preço nulo = 'sob consulta' (Chaves na Mão)
GROUP BY cidade;

-- COMMAND ----------

-- 4. Média bruta (com galpões e lojas): Itabuna parece mais cara. Compare com a célula 3.
-- esperado: Ilhéus 4780   Itabuna 6678
SELECT cidade, ROUND(AVG(preco)) AS media_bruta, MAX(preco) AS maior_anuncio
FROM workspace.default.anuncios
GROUP BY cidade;

-- COMMAND ----------

-- 5. Ilhéus por bairro, 10 ou mais anúncios residenciais. Clique em "+" > Visualization: barras de mediana por bairro.
-- esperado: Jardim Atlantico 34 | 5500 no topo; Nossa Senhora Da Vitoria 193 | 3300
SELECT bairro, COUNT(*) AS n, PERCENTILE(preco, 0.5) AS mediana
FROM workspace.default.anuncios
WHERE residencial AND cidade = 'Ilhéus' AND preco IS NOT NULL
GROUP BY bairro
HAVING n >= 10
ORDER BY mediana DESC;

-- COMMAND ----------

-- 6. Os anúncios que puxavam a média (esperado: galpões de R$ 90.000 em Iguape e R$ 60.000 em Ferradas, Itabuna)
SELECT cidade, tipo, bairro, preco, area_m2, url
FROM workspace.default.anuncios
ORDER BY preco DESC
LIMIT 5;

-- COMMAND ----------

-- 7. Para a turma: o imóvel residencial de 2 quartos mais barato no Pontal (esperado: casa de 100 m² por R$ 2.500). Depois, a mesma pergunta no Genie
SELECT preco, area_m2, quartos, url
FROM workspace.default.anuncios
WHERE residencial AND cidade = 'Ilhéus' AND bairro = 'Pontal' AND quartos = 2
ORDER BY preco
LIMIT 3;

-- COMMAND ----------

-- 8. De onde veio cada anúncio único (esperado: vivareal 748, zap 62, chavesnamao 36). O ZAP tinha 811 linhas; 749 eram o mesmo id do VivaReal.
SELECT portal, COUNT(*) AS n FROM workspace.default.anuncios GROUP BY portal ORDER BY n DESC;
