# Rezultati i uputstvo za pokretanje (`ai/`)

Ovaj direktorijum je dokazni materijal za rad. U njemu su:

| Fajl | Sadrzaj |
|---|---|
| `<model>.json` | metrike jednog modela u oba pogleda, hiperparametri, najbolja epoha, vreme treniranja, commit |
| `summary.md` | tabela poredjenja svih sest modela |
| `figures/` | figure koje crta `ai/notebooks/06_results.ipynb` (PNG za pregled, PDF za rad) |

Sve ostalo sto pipeline proizvede (`ai/data/processed/`, `ai/artifacts/`) je van
verzionisanja - to su medjurezultati koji se u svakom trenutku mogu ponovo
izracunati iz komandi ispod.

---

## 1. Redosled komandi

Sve se pokrece iz korena repozitorijuma. Preduslov je Food.com dataset
("Food.com Recipes and Interactions" sa Kaggle-a) raspakovan u `datasets/`:
`RAW_recipes.csv` (231.637 redova) i `RAW_interactions.csv` (1.132.367 redova).
Ako fajlova nema, svaka komanda staje odmah, sa porukom sta nedostaje i odakle se
preuzima.

```bash
# 1. priprema podataka: filtriranje, k-core i zamrznuto mapiranje indeksa
uv run python -m foodrec.data

# 2. jedna podela, dva pogleda evaluacije
uv run python -m foodrec.split --seed 42

# 3. treniranje - svaki model na istoj podeli
uv run python -m foodrec.train --model popularity
uv run python -m foodrec.train --model itemknn
uv run python -m foodrec.train --model ease              # zaseban proces, ~10,7 GB
uv run python -m foodrec.train --model multdae --device auto
uv run python -m foodrec.train --model multvae --device auto
uv run python -m foodrec.train --model neumf   --device auto

# 4. evaluacija u oba pogleda + tabela
uv run python -m foodrec.evaluate --model all --summary

# 5. finalni model: ponovno treniranje na svim podacima + izvoz za backend
uv run python -m foodrec.train --model multvae --full --device auto

# 6. provera artefakta koji backend ucitava
uv run python -m foodrec.serving --smoke
```

Korak 5 sam pokrece izvoz; za ponavljanje zasebno:
`uv run python -m foodrec.export --model multvae`.

Hiperparametri koji su podeseni na validacionom skupu (sekcija 5) su podrazumevani,
pa gornje komande reprodukuju tabelu bez dodatnih zastavica. Za ponavljanje samih
pretraga postoje `--knn-k`, `--knn-shrinkage`, `--ease-lambda` i `--knn-block`.

Figure crta `ai/notebooks/06_results.ipynb` - cita `ai/results/*.json` i snima u
`ai/results/figures/`.

`--device auto` bira MPS na Apple Silicon masini; `--device cpu` je bit-po-bit
reproducibilan za dati seed (provereno: dva CPU treniranja Mult-VAE daju identican
SHA-256 svih tezina).

---

## 2. Podaci posle filtriranja

| Korak | Rezultat |
|---|---|
| sirove interakcije | 1.132.367 |
| ocena 0 (recenzija bez ocene) | 60.847 |
| udeo petica medju ocenjenima | 76,2% |
| pozitivne (ocena >= 4) | 1.003.724 |
| posle k-core (korisnik >= 3, recept >= 5), 8 iteracija | **539.959** |
| korisnici x recepti | **25.959 x 39.886** |
| gustina | 0,052% |

Raspodela istorije po korisniku posle podele je ono sto objasnjava skoro sve
rezultate u sekciji 5: p10 = 1, p25 = 2, **medijana = 4**, p75 = 10, p90 = 24,
p99 = 193 trening stavke. **23,3% korisnika ima najvise jednu trening stavku.**
Recept ima medijanu od 5 pozitivnih ocena u treningu, prosek 8,2, maksimum 595.

---

## 3. Sta je koji model

Svih sest je trenirano i mereno na istoj podeli, sa istim seed-om.

**Popularity** - broj korisnika iz trening skupa koji imaju pozitivnu ocenu za
recept. Nema personalizacije; sluzi kao donja granica i kao fallback u backend-u
dok korisnik nema nijednu ocenu koju model prepoznaje.

**ItemKNN** - kosinusna slicnost sa prigusenjem `c_ij / (sqrt(n_i * n_j) + s)`,
`s = 500`, `k = 1000` suseda, odsecanje po redu (red `i` drzi `k` najblizih suseda
recepta `i`). Skorovanje je jedan redak proizvod `istorija @ S`.

**EASE** (Steck, 2019) - linearni model u zatvorenoj formi: `G = X'X + lambda*I`,
`B = -G^-1 / diag(G^-1)`, nula na dijagonali, `lambda = 5000`.

**Mult-DAE** (Liang i dr., 2018) - denoising autoenkoder `n_items -> 200 -> n_items`,
tanh, dropout 0.5 na L2-normalizovanom ulazu, multinomijalna verodostojnost,
Adam 1e-3, weight decay 1e-4.

**Mult-VAE** (Liang i dr., 2018) - **model koji se servira**. Enkoder
`Linear(n_items, 600) -> tanh -> Linear(600, 400)` se deli na `mu` i `logvar`
dimenzije 200; dekoder `Linear(200, 600) -> tanh -> Linear(600, n_items)`. Gubitak
je multinomijalna log-verodostojnost plus `beta * KL`, beta linearno raste od 0 do
0,2 kroz prvih 20 epoha pa se drzi. U inferenciji se koristi `mu`, bez dropout-a i
bez uzorkovanja - inace metrike variraju izmedju pokretanja.

**NeuMF** (He i dr., 2017) - GMF grana (dimenzija 32) i MLP grana (32+32
ugradjivanja kroz slojeve 64-32-16-8), spojene u jedan logit; binarna unakrsna
entropija sa 4 uniformno uzorkovana negativna primera po pozitivnom, iznova
uzorkovana svake epohe. **Bez pretreniranja grana** - u originalnom radu se GMF i
MLP prvo treniraju odvojeno; ovde su obe od nule, sto je svesno pojednostavljenje.

---

## 4. Dva pogleda evaluacije iz jedne podele

Podela se pravi jednom (`splits_seed42.npz`) i daje pet matrica oblika
`(n_users, n_items)`, sa praznim redovima tamo gde pogled ne vazi. Zato se svaki
model trenira **tacno jednom**, a meri se u oba pogleda.

**Weak generalizacija (primarni pogled).** 90% korisnika (23.363) je u treningu. Za
svakog 20% pozitivnih interakcija ide u test (najmanje jedna), jos 10% u validaciju
za rano zaustavljanje, ostatak u trening: 328.204 / 56.651 / 99.311 interakcija. Pri
merenju se rangira ceo katalog, a trening i validacione stavke se izbacuju
(postavljaju se na `-inf`).

**Strong generalizacija (sekundarni pogled).** Preostalih 10% korisnika (2.596)
nikada nije u treningu. Njihovih 80% interakcija se ubacuje kao ulaz u trenutku
merenja (44.356 fold-in), a preostalih 20% su ciljevi (11.437). Ovo je hladan start.

Posle podele **98 recepata (0,246%) nema nijednu trening interakciju** - ocekivano
ispod 1%.

**NeuMF u strong pogledu ima N/A**, i to nije propust nego rezultat. NeuMF skoruje
indeksiranjem tabele korisnickih ugradjivanja; za nepoznatog korisnika tog reda
nema. Mult-VAE, Mult-DAE, EASE i ItemKNN primaju istoriju kao ulaz i mogu da posluze
korisnika registrovanog pre pet sekundi. To je glavni argument zasto se servira
Mult-VAE, a ne NeuMF.

**Metrike.** Recall@10/20, NDCG@10/20 i pokrivenost kataloga@20. Recall se deli sa
`min(K, |ciljevi|)` (konvencija iz Mult-VAE rada): sa sirovim `|ciljevi|` korisnik sa
40 izdvojenih recepata nikada ne bi mogao da predje 0,5 na K=20. NDCG koristi binarne
dobitke, IDCG preko `min(K, |ciljevi|)`.

---

## 5. Rezultati

### Weak generalizacija (primarni pogled)

| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |
|---|---|---|---|---|---|
| Popularity | 0,0274 | 0,0430 | 0,0167 | 0,0212 | 0,001 |
| ItemKNN | 0,0256 | 0,0381 | 0,0173 | 0,0210 | 0,714 |
| EASE | 0,0262 | 0,0382 | 0,0179 | 0,0214 | 0,667 |
| **Mult-DAE** | **0,0293** | **0,0450** | **0,0191** | **0,0236** | 0,023 |
| Mult-VAE | 0,0258 | 0,0412 | 0,0157 | 0,0200 | 0,283 |
| NeuMF | 0,0268 | 0,0432 | 0,0162 | 0,0210 | 0,010 |
| _slucajno rangiranje_ | 0,0003 | 0,0005 | 0,0003 | 0,0005 | - |

### Strong generalizacija (hladan start)

| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |
|---|---|---|---|---|---|
| Popularity | 0,0318 | 0,0466 | 0,0196 | 0,0239 | 0,001 |
| ItemKNN | 0,0276 | 0,0440 | 0,0178 | 0,0226 | 0,144 |
| EASE | 0,0287 | 0,0434 | 0,0195 | 0,0238 | 0,124 |
| **Mult-DAE** | **0,0355** | **0,0532** | **0,0225** | **0,0277** | 0,016 |
| Mult-VAE | 0,0329 | 0,0482 | 0,0212 | 0,0256 | 0,024 |
| NeuMF | N/A | N/A | N/A | N/A | N/A |

### Cena treniranja i skorovanja

| Model | Najbolja epoha | Trening (s) | Vrhunac RAM (GB) | Skorovanje (ms/korisnik) |
|---|---|---|---|---|
| Popularity | - | 0,0 | 0,26 | 0,002 |
| ItemKNN | - | 17,7 | 4,73 | 0,089 |
| EASE | - | 77,3 | 10,68 | 6,702 |
| Mult-DAE | 32 | 219,3 | 1,24 | 0,038 |
| Mult-VAE | 20 | 198,3 | 1,49 | 0,062 |
| NeuMF | 3 | 47,9 | 0,84 | 1,002 |

Skorovanje je mereno u evaluatoru, u serijama korisnika, na MPS-u za neuronske
modele. **NeuMF je 16 puta skuplji od Mult-VAE** jer mora da provuce svaki par
(korisnik, recept) kroz MLP, dok Mult-VAE skoruje ceo katalog jednim prolazom.
EASE je najskuplji (gust proizvod sa matricom 39.886 x 39.886), ali se to placa
jednom po korisniku, ne po receptu.

### Glavni nalaz: popularnost je ovde jak takmac

Najvazniji rezultat nije koji je model najbolji nego **koliko je mala razlika**.
Mult-DAE, jedini model koji ubedljivo pobedjuje popularnost, dobija 4,7% relativno
na weak Recall@20 (0,0450 prema 0,0430) i 14,2% na strong (0,0532 prema 0,0466).
ItemKNN i EASE su **ispod** popularnosti po Recall-u, a tek neznatno iznad po NDCG-u.

Ovo je bio dovoljno neocekivan rezultat da je proveren pre nego sto je prihvacen.
Cela istraga je u sekciji 6; zakljucak je da su brojevi tacni i da je uzrok
retkost podataka: medijana korisnika ima 4 trening ocene, medijana recepta 5, a
23,3% korisnika ima najvise jednu trening stavku. Signal ko-pojavljivanja na tom
nivou retkosti nosi manje informacije od same popularnosti na K=20.

Uz to, **pokrivenost pokazuje da modeli nisu isti iako im se brojevi poklapaju**:
popularnost ikada preporuci 0,1% kataloga (56 recepata), ItemKNN 71%, EASE 67%.
Sistem koji svima nudi istih 20 recepata i sistem koji koristi 28.000 recepata za
istu tacnost nisu ista stvar za korisnika, i to je argument koji ide u rad.

Kvalitativno, `similar()` nad izvezenim modelom vraca recepte koji se **zajedno
konzumiraju**, a ne koji imaju slicne sastojke: za "sandra s key lime pie" susedi su
"my no roll pie crust" (0,483) i "creamy burrito casserole" (0,482). To je ocekivano
za cisto kolaborativni model bez sadrzaja i opravdava tag fallback koji backend vec
ima za slicne recepte.

---

## 6. Istraga: zasto su ItemKNN i EASE ispod popularnosti

Prvo merenje sa podrazumevanim hiperparametrima iz literature dalo je ItemKNN
Recall@20 = 0,0147, sto je trecina popularnosti. To je oblik greske, ne oblik
rezultata, pa je provereno sledecim redom.

**1. Da li je evaluacioni aparat ispravan?** Dva vestacka modela, ista funkcija
`evaluate_ranking`:

| Model | Recall@20 | NDCG@20 |
|---|---|---|
| oracle (skoruje same ciljeve) | **1,0000** | **1,0000** |
| slucajno rangiranje | 0,000506 | 0,000418 |

Ocekivana vrednost za slucajno rangiranje je `20 / 39.886 = 0,000501`; izmereno je
0,000506. Podela, maskiranje istorije i metrike su time dokazano ispravni.

**2. Da li je ItemKNN pogresno okrenut?** Provereno rucno, na jednom stvarnom
korisniku sa 20 trening recepata. `S` je 39.886 x 39.886, dijagonala je nula pre
odsecanja, a top-10 kandidata zaista ko-postoje sa istorijom (`c_ij` od 1 do 25),
dok nasumican par recepata ima prosecno `c_ij = 0,035`. Mehanika je ispravna.

Ali ista provera pokazuje uzrok: **kandidati na vrhu liste su recepti sa 1, 2 i 5
pozitivnih ocena**. Kada recept ima dva ocenjivaca i oba su u istoriji ovog
korisnika, kosinus je skoro savrsen. Prigusenje od 10 je premalo da to zaustavi kada
je medijana popularnosti recepta 5.

**3. Da li je to hladan start?** Nije. Recall po duzini istorije korisnika
(ItemKNN sa podrazumevanim parametrima prema popularnosti):

| trening stavki | korisnika | popularity R@20 | ItemKNN R@20 | odnos |
|---|---|---|---|---|
| 1 | 5.449 | 0,0396 | 0,0116 | 0,29 |
| 2-3 | 5.444 | 0,0487 | 0,0162 | 0,33 |
| 4-7 | 5.188 | 0,0438 | 0,0127 | 0,29 |
| 8-15 | 3.456 | 0,0372 | 0,0142 | 0,38 |
| 16-31 | 2.020 | 0,0298 | 0,0227 | 0,76 |
| 32+ | 1.806 | 0,0246 | 0,0177 | 0,72 |

Ispod popularnosti je na **svakoj** duzini istorije, pa nije rec o hladnom startu.

**4. Podesavanje na validacionom skupu.** Sve pretrage su radjene iskljucivo nad
`weak_val`; test skup nije korisen ni jednom.

ItemKNN, prigusenje (k=1000, odsecanje po redu), validacioni Recall@20:

| prigusenje | 10 | 200 | 500 | 1000 | 3000 | 10000 |
|---|---|---|---|---|---|---|
| Recall@20 | 0,0136 | 0,0361 | **0,0378** | 0,0376 | 0,0376 | 0,0376 |

Monotono raste i zaustavlja se na oko 500. To ima smisla: kada prigusenje raste,
`s_ij -> c_ij / s`, pa se model pretvara u cist broj ko-pojavljivanja i prestaje da
gura retke recepte. Plato je na 0,89 popularnosti.

EASE, lambda, validacioni Recall@20:

| lambda | 1 | 10 | 50 | 200 | 500 | 2000 | 5000 | 20000 |
|---|---|---|---|---|---|---|---|---|
| Recall@20 | 0,0173 | 0,0236 | 0,0310 | 0,0348 | 0,0354 | 0,0373 | **0,0381** | 0,0381 |

Isti oblik. Malo lambda je ovde posebno lose iz strukturnog razloga: `G = X'X` je
39.886 x 39.886, ali joj je rang najvise `n_users = 25.959`, pa je **singularna** -
regularizacija nije samo podesavanje nego uslov da inverzija uopste ima smisla.
Argmax po NDCG@20 je lambda = 5000.

Podrazumevane vrednosti u kodu su promenjene na ove izmerene (`s = 500`, `k = 1000`,
`lambda = 5000`); originalne vrednosti iz zadatka (`s = 10`, `k = 100`,
`lambda = 500`) kalibrisane su na MovieLens-20M, gde recept ima hiljade ocena.

**5. Mult-VAE se zaustavljao prerano.** Sa `patience = 10` model je stajao na epohi
15, sa najboljom epohom 5. Duga dijagnosticka voznja (80 epoha bez zaustavljanja)
pokazuje zasto:

| epoha | 1 | 6 | 11 | 16 | 21 | 41 | 67 |
|---|---|---|---|---|---|---|---|
| beta | 0,01 | 0,06 | 0,11 | 0,16 | 0,20 | 0,20 | 0,20 |
| val NDCG@20 | 0,0184 | 0,0172 | 0,0159 | 0,0170 | 0,0191 | 0,0182 | 0,0197 |

Validacioni NDCG **pada dok beta raste** i vraca se tek kada anneal zavrsi. Pad traje
duze od 10 epoha, pa je `patience = 10` uz anneal od 20 epoha bio protivrecan sam
sebi: model je uvek bio ubijen pre nego sto stigne u rezim za koji je projektovan.
Ispravka nije veci broj nego uklanjanje protivrecnosti - **epohe tokom annealing-a se
ne racunaju u strpljenje**. Posle toga model staje na epohi 30 sa najboljom 20.

**6. Beta je ipak dobro izabrana.** Posto KL clan izgleda kao krivac, i on je
proveren, opet samo na validaciji:

| beta | 0,00 | 0,02 | 0,05 | 0,10 | 0,20 | 0,05 (latent 64) |
|---|---|---|---|---|---|---|
| najbolja epoha | 1 | 4 | 4 | 4 | **20** | 4 |
| val NDCG@20 | 0,0184 | 0,0185 | 0,0186 | 0,0185 | **0,0191** | 0,0187 |

Sa manjom beta model prenauci vec u prvim epohama. `beta = 0,2` iz zadatka je
najbolja izmerena vrednost i ostaje.

**Zakljucak.** Nijedna od pet provera nije nasla gresku. Rezultat je tacan: na
Food.com skupu, sa pozitivnom ocenom >= 4 i k-core (3, 5), popularnost je jak takmac
na K=20, a razlike medju modelima su male. To je poznata pojava u literaturi o
reproducibilnosti preporucivackih sistema (Dacrema i dr., 2019) i sama po sebi je
nalaz vredan izvestavanja.

Zbog toga su provere u `foodrec.metrics.sanity_check` podeljene na dve grupe:

- **tvrde** (prekidaju izvrsavanje) - popularnost mora biti iznad slucajnog
  rangiranja, nijedan model ne sme da bude na nivou slucajnog izbora. To su potpisi
  greske u podeli, mapiranju indeksa ili maskiranju.
- **meke** (glasno upozorenje, ne prekidaju) - ItemKNN i EASE oko dvostruke
  popularnosti, Mult-VAE iznad popularnosti. To su ocekivanja prenesena iz
  literature o gustim skupovima i na ovom skupu se ne ispunjavaju iz gore
  dokumentovanog razloga.

Meke provere i dalje pisu upozorenje pri svakom pokretanju `evaluate`. Nisu
uklonjene - da je ovo bio bag, ostale bi kao jedini trag.

---

## 7. Greska sa mapiranjem indeksa - i zasto se vise ne moze ponoviti

Ovo je nalaz koji ide u rad.

U istrazivackim notebook-ima (`ai/notebooks/03..05`) recnici `user_to_idx` i
`recipe_to_idx` gradjeni su bar cetiri puta, izrazom oblika:

```python
recipe_to_idx = {rid: i for i, rid in enumerate(df["recipe_id"].unique())}
```

`pandas.Series.unique()` vraca vrednosti **redosledom prvog pojavljivanja**, a ne
sortirano. Kada se isti izraz pokrene nad drugim DataFrame-om - nad trening skupom
umesto nad celim, ili nad drugacije sortiranim redovima - dobija se **drugaciji**
recnik. Model je onda treniran pod jednim mapiranjem, a evaluiran pod drugim: red
ugradjivanja broj 17 tokom treninga pripadao je jednom receptu, a tokom evaluacije
sasvim drugom. Posledica je `05_ncf_v2`, gde je trening AUC 0,83, a test AUC
**0,4929** - tacno nivo slucajnog pogadjanja.

Uz to, `Series.map()` nad nepoznatim id-jem daje `NaN`, a `astype(np.int32)` je taj
`NaN` tiho pretvarao u proizvoljan ceo broj umesto da podigne gresku. Nepoznat
recept tako nije bio preskocen nego preslikan na nasumican red matrice.

Pipeline to onemogucava na cetiri mesta:

1. **Jedno mapiranje, izgradjeno jednom.** `IndexMapping` se pravi iz
   `np.unique(...)`, dakle iz **sortiranih** jedinstvenih id-jeva, i to tek nakon
   sto je skup potpuno filtriran (k-core). Mapiranje je time cista funkcija skupa
   id-jeva, potpuno nezavisna od redosleda redova bilo kog DataFrame-a.
2. **Mapiranje se pravi pre podele, ne posle.** Podela radi vec kodiranim
   indeksima, pa nema koraka u kome bi trening i test mogli da vide razlicite
   recnike.
3. **Mapiranje se cuva na disk** (`ai/data/processed/index.json`) i isti fajl se
   izvozi uz model (`item_index.json`). Backend i model dele bukvalno isti niz.
4. **Nepoznat id se odbacuje eksplicitno.** `encode(ids, strict=False)` izbacuje
   nepoznate id-jeve; `strict=True` podize `KeyError`. Ne postoji treca varijanta
   koja bi izmislila indeks. Uz to, `load_positives()` odbija kes ciji indeksi ne
   staju u ucitano mapiranje, a `foodrec.export` odbija da izveze model ciji se broj
   recepata ne poklapa sa `index.json`.

Peti sloj su tvrde provere iz sekcije 6, plus oracle/random test kojim je aparat
dokazan.

---

## 8. Artefakt za serviranje

`uv run python -m foodrec.train --model multvae --full` trenira Mult-VAE na **svim**
pozitivnim interakcijama (539.959) za broj epoha koji je rano zaustavljanje izabralo
na podeli (20), i zatim izvozi `ai/artifacts/mult_vae/` (414 MB):

| Fajl | Namena |
|---|---|
| `model.pt` | samo `state_dict`, pa `torch.load(weights_only=True)` radi |
| `weights.npz` | isti tenzori za numpy runtime; prva matrica enkodera je transponovana |
| `item_embeddings.npy` | redovi izlaznog sloja dekodera, L2-normalizovani, float16 |
| `item_index.json` | zamrznuto mapiranje id recepta -> indeks |
| `popularity.npy` | broj pozitivnih ocena po receptu, poravnat sa indeksom |
| `config.json` | arhitektura, hiperparametri, seed, datum, statistika skupa, obe metrike, verzije biblioteka, commit |

Backend ga nalazi preko `MODEL_ARTIFACT_DIR` (podrazumevano
`ai/artifacts/mult_vae`) i ucitava jednom, u FastAPI lifespan-u.
`foodrec.serving` **ne uvozi torch** - radi iskljucivo nad numpy nizovima.

Trik koji cini serviranje jeftinim: ulaz enkodera je binaran vektor podeljen svojom
L2 normom, pa je

```
W1 @ (x / ||x||)  ==  (1 / sqrt(k)) * zbir k redova matrice W1 transponovano
```

umesto mnozenja gustog vektora od kojih je skoro sve nula. Jedina operacija pune
sirine koja ostaje je izlazni GEMV dekodera.

Mereno na M4 Pro, nad punim katalogom od 39.886 recepata: ucitavanje modela **64 ms**,
`score()` **0,51 ms** u proseku (medijana 0,51, p95 0,55, n=200). Kompletan smoke
test (`--smoke`) proverava i da `explain()` vraca ocenjen recept i da `similar()`
radi.

---

## 9. Poznata ogranicenja

- **Mult-DAE je izmereno bolji od Mult-VAE na ovom skupu** (weak Recall@20 0,0450
  prema 0,0412; strong 0,0532 prema 0,0482). Servira se Mult-VAE, kako je
  dogovoreno pre merenja; Mult-DAE je jeftiniji i bolji, pa je zamena serviranog
  modela otvorena odluka koju vredi doneti svesno, a ne precutati.
- **EASE je memorijski najskuplji korak**: gusta matrica `B` je 5,9 GB, izmereni
  vrhunac procesa 10,68 GB (a 13,16 GB tokom pretrage po lambda, gde vise fitova ide
  jedan za drugim). Trenira se u zasebnom procesu i nikada uporedo sa MPS poslom.
  `--max-items N` ogranicava model na N najpopularnijih recepata; tada EASE ne moze
  da preporuci nista van glave kataloga. Na disku se `B` cuva kao float16 (3 GB
  umesto 6) - vrednosti su reda 1e-5 do 1e-1, a skor je zbir nekoliko desetina njih.
- **NeuMF prenauci gotovo odmah**: najbolja epoha je 3, a validacioni NDCG@20 pada
  vec od cetvrte. Sa 26k x 64 + 40k x 64 parametara ugradjivanja prema 540k
  interakcija to je ocekivano, i pogorsano je izostankom pretreniranja grana.
- **NeuMF nema strong generalizaciju** (sekcija 4).
- Nema modela zasnovanog na sadrzaju ni hibrida - poredjenje je namerno svedeno na
  cisto kolaborativne modele, zbog roka i obima rada. Sekcija 5 pokazuje da bi
  sadrzaj (sastojci, tagovi) verovatno bio najveci pojedinacni dobitak na ovom skupu.
- Metrike u `config.json` izvezenog modela su sa **podele**, ne sa finalnog modela
  treniranog na svim podacima; finalni model po definiciji nema izdvojen test skup.
- Podesavanje hiperparametara je radjeno na validacionom skupu i to samo za ItemKNN,
  EASE i Mult-VAE (beta). Mult-DAE i NeuMF su ostali na vrednostima iz zadatka, pa im
  rezultati nisu jednako "iscedjeni" - to treba imati u vidu pri poredjenju.

---

## 10. Provera pipeline-a na sintetickim podacima

Pored pravih rezultata, ceo lanac se proverava i nad sintetickim skupom sa
**zasadjenom strukturom** (`foodrec.synthetic`: 3.000 korisnika, 800 recepata,
71.481 interakcija, 12 klastera ukusa, 8% redova sa ocenom 0). To je brza
regresiona provera: na zasadjenoj strukturi svi kolaborativni modeli moraju
ubedljivo da pobede popularnost, pa bi greska u mapiranju indeksa odmah bila
vidljiva kao urusena metrika.

| Model | Recall@20 (weak) | NDCG@20 (weak) | Recall@20 (strong) | Coverage@20 |
|---|---|---|---|---|
| Popularity | 0,1080 | 0,0582 | 0,1127 | 0,039 |
| ItemKNN | 0,4487 | 0,2706 | 0,4438 | 0,941 |
| EASE | 0,4744 | 0,3006 | 0,4883 | 0,929 |
| Mult-DAE | 0,4883 | 0,3114 | 0,5013 | 0,785 |
| Mult-VAE | 0,4772 | 0,3045 | 0,4817 | 0,810 |
| NeuMF | 0,4785 | 0,3067 | N/A | 0,831 |
| _slucajno rangiranje_ | 0,0250 | | | |

Na tim podacima `similar()` vraca recept iz istog zasadjenog klastera u **100%**
slucajeva (2.000 provera; slucajno bi bilo 8,3%), a `explain()` u 50 od 50 pokusaja
pokazuje na ocenjen recept. **Ovo nisu rezultati rada** - to je provera da lanac radi.
