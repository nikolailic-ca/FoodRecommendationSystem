# Rezultati i uputstvo za pokretanje (`ai/`)

Ovaj direktorijum je dokazni materijal za rad. U njemu zavrsavaju:

| Fajl | Sadrzaj |
|---|---|
| `<model>.json` | metrike jednog modela u oba pogleda, hiperparametri, najbolja epoha, vreme treniranja, commit |
| `summary.md` | tabela poredjenja svih sest modela |
| `figures/` | figure koje crta `ai/notebooks/06_results.ipynb` (PNG za pregled, PDF za rad) |

Sve ostalo sto pipeline proizvede (`ai/data/processed/`, `ai/artifacts/`) je van
verzionisanja - to su medjurezultati koji se u svakom trenutku mogu ponovo
izracunati iz ovih komandi.

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
uv run python -m foodrec.train --model ease              # zaseban proces, vidi nize
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

Korak 5 sam pokrece izvoz; ako treba da se ponovi zasebno:
`uv run python -m foodrec.export --model multvae`.

Figure za rad crta `ai/notebooks/06_results.ipynb` - cita `ai/results/*.json` i
snima u `ai/results/figures/`.

`--device auto` bira MPS na Apple Silicon masini, `--device cpu` je bit-po-bit
reproducibilan za dati seed (provereno: dva CPU treniranja Mult-VAE daju identican
SHA-256 svih tezina).

---

## 2. Sta je koji model

Svih sest je trenirano i mereno na istoj podeli, sa istim seed-om.

**Popularity** - broj korisnika iz trening skupa koji imaju pozitivnu ocenu za
recept. Nema personalizacije; sluzi kao donja granica i kao fallback u backend-u
dok korisnik nema nijednu ocenu koju model prepoznaje.

**ItemKNN** - kosinusna slicnost izmedju recepata sa prigusenjem
`c_ij / (sqrt(n_i * n_j) + 10)`, cuva se 100 najblizih suseda po receptu.
Prigusenje je bitno: bez njega dva nepoznata recepta koje je slucajno ocenio isti
korisnik dobijaju savrsenu slicnost 1.0 i zatrpaju susedstvo. Skorovanje je jedan
redak proizvod `istorija @ S`.

**EASE** (Steck, 2019) - linearni model u zatvorenoj formi: `G = X'X + 500*I`,
`B = -G^-1 / diag(G^-1)`, sa nulom na dijagonali. Bez ijedne epohe gradijentnog
spusta obicno je u rangu neuronskih modela, pa je u radu najposteniji "jak
klasican" takmac.

**Mult-DAE** (Liang i dr., 2018) - denoising autoenkoder `n_items -> 200 -> n_items`,
tanh, dropout 0.5 na L2-normalizovanom ulazu, multinomijalna verodostojnost.

**Mult-VAE** (Liang i dr., 2018) - **model koji se servira**. Enkoder
`Linear(n_items, 600) -> tanh -> Linear(600, 400)` se deli na `mu` i `logvar`
dimenzije 200; dekoder `Linear(200, 600) -> tanh -> Linear(600, n_items)`. Gubitak
je multinomijalna log-verodostojnost plus `beta * KL`, gde beta linearno raste od 0
do 0.2 kroz prvih 20 epoha pa se drzi. U inferenciji se koristi `mu`, bez dropout-a
i bez uzorkovanja - inace metrike variraju izmedju pokretanja.

**NeuMF** (He i dr., 2017) - GMF grana (dimenzija 32) i MLP grana (32+32
ugradjivanja kroz slojeve 64-32-16-8), spojene u jedan logit; binarna unakrsna
entropija sa 4 uniformno uzorkovana negativna primera po pozitivnom, iznova
uzorkovana svake epohe. **Bez pretreniranja grana** - u originalnom radu se GMF i
MLP prvo treniraju odvojeno; ovde su obe od nule, sto je svesno pojednostavljenje i
kosta nesto tacnosti.

---

## 3. Dva pogleda evaluacije iz jedne podele

Podela se pravi jednom (`splits_seed42.npz`) i daje pet matrica oblika
`(n_users, n_items)`, sa praznim redovima tamo gde pogled ne vazi. Zato se svaki
model trenira **tacno jednom**, a meri se u oba pogleda.

**Weak generalizacija (primarni pogled).** 90% korisnika je u treningu. Za svakog
od njih 20% pozitivnih interakcija ide u test (najmanje jedna), jos 10% u
validaciju za rano zaustavljanje, ostatak u trening. Pri merenju se rangira ceo
katalog, a trening i validacione stavke se izbacuju iz rangiranja (postavljaju se
na `-inf`). Ovo je pogled koji odgovara stvarnom radu aplikacije za postojeceg
korisnika.

**Strong generalizacija (sekundarni pogled).** Preostalih 10% korisnika nikada nije
u treningu. Njihovih 80% interakcija se ubacuje kao ulaz u trenutku merenja
(fold-in), a preostalih 20% su ciljevi. Ovo je hladan start: sta model radi sa
korisnikom koga nije video.

**NeuMF u ovom pogledu ima N/A**, i to nije propust nego rezultat. NeuMF skoruje
tako sto indeksira tabelu korisnickih ugradjivanja; za nepoznatog korisnika tog
reda nema, pa se model mora ponovo trenirati da bi ga uopste video. Mult-VAE,
Mult-DAE, EASE i ItemKNN primaju istoriju kao ulaz i zato mogu da posluze i
korisnika koji je registrovan pre pet sekundi. To je glavni argument zasto se
servira Mult-VAE, a ne NeuMF.

**Metrike.** Recall@10, Recall@20, NDCG@10, NDCG@20 i pokrivenost kataloga@20.
Recall se deli sa `min(K, |ciljevi|)` (konvencija iz Mult-VAE rada): sa sirovim
`|ciljevi|` u imeniocu korisnik sa 40 izdvojenih recepata nikada ne bi mogao da
predje 0.5 na K=20, pa bi prosek vise govorio o velicini izdvojenog skupa nego o
modelu. NDCG koristi binarne dobitke, a IDCG se racuna preko `min(K, |ciljevi|)`.
Pokrivenost@20 je udeo recepata koji se bar jednom pojave u necijih prvih 20.

---

## 4. Greska sa mapiranjem indeksa - i zasto se vise ne moze ponoviti

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
sasvim drugom. Posledica je `05_ncf_v2`, gde je trening AUC 0.83, a test AUC
**0.4929** - to jest, tacno nivo slucajnog pogadjanja.

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
   koja bi izmislila indeks. Uz to, `foodrec.data.load_positives()` odbija kes ciji
   indeksi ne staju u ucitano mapiranje, a `foodrec.export` odbija da izveze model
   ciji se broj recepata ne poklapa sa `index.json`.

Peti sloj su provere zdravog razuma u `foodrec.metrics.sanity_check`, koje
`evaluate` pokrece nad gotovim rezultatima i koje glasno padaju: popularnost mora
biti iznad slucajnog rangiranja (`20 / n_items`), ItemKNN i EASE osetno iznad
popularnosti, a Mult-VAE ne sme da bude ispod nje. Model koji rangira na nivou
slucajnog izbora ne moze da zavrsi u tabeli neprimecen.

---

## 5. Rezultati

Tabela se generise u `summary.md` i imace ovaj oblik (sest modela, plus red sa
ocekivanom vrednoscu slucajnog rangiranja):

| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |
|---|---|---|---|---|---|
| Popularity | | | | | |
| ItemKNN | | | | | |
| EASE | | | | | |
| Mult-DAE | | | | | |
| Mult-VAE | | | | | |
| NeuMF | | | | | |

> Brojevi se popunjavaju kada se pipeline pokrene nad pravim Food.com skupom -
> `ai/results/*.json` i `summary.md` se tada commit-uju kao dokaz.

### Provera pipeline-a na sintetickim podacima

Dok pravi dataset nije bio dostupan, ceo lanac je proveren nad sintetickim skupom
iste strukture (`foodrec.synthetic`: 3.000 korisnika, 800 recepata, 71.481
interakcija, 12 zasadjenih klastera ukusa, 8% redova sa ocenom 0). Posle
filtriranja: 47.473 pozitivne interakcije, 2.978 korisnika x 800 recepata.

**Ovo nisu rezultati rada** - to je provera da lanac radi i da bi greska u
mapiranju indeksa bila vidljiva kao urusena metrika, a ne kao uverljiv broj.

| Model | Recall@20 (weak) | NDCG@20 (weak) | Recall@20 (strong) | Coverage@20 |
|---|---|---|---|---|
| Popularity | 0.1080 | 0.0582 | 0.1127 | 0.039 |
| ItemKNN | 0.4487 | 0.2706 | 0.4438 | 0.941 |
| EASE | 0.4744 | 0.3006 | 0.4883 | 0.929 |
| Mult-DAE | 0.4883 | 0.3114 | 0.5013 | 0.785 |
| Mult-VAE | 0.4772 | 0.3045 | 0.4817 | 0.810 |
| NeuMF | 0.4785 | 0.3067 | N/A | 0.831 |
| _slucajno rangiranje_ | 0.0250 | | | |

Sve provere zdravog razuma prolaze: popularnost je 4,3 puta iznad slucajnog
rangiranja, a svi modeli zasnovani na kolaborativnom signalu su preko 4 puta iznad
popularnosti. Na ovako malom katalogu (800 recepata, 12 cistih klastera) NeuMF je
u weak pogledu ravnopravan - njegova slabost se vidi tek u strong koloni, gde ga
uopste nema.

---

## 6. Artefakt za serviranje

`uv run python -m foodrec.train --model multvae --full` trenira Mult-VAE na **svim**
pozitivnim interakcijama (trening + validacija + test + strong korisnici) za onaj
broj epoha koji je rano zaustavljanje izabralo na podeli, i zatim izvozi
`ai/artifacts/mult_vae/`:

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

Trik koji cini serviranje jeftinim: ulaz enkodera je binaran vektor podeljen
svojom L2 normom, pa je

```
W1 @ (x / ||x||)  ==  (1 / sqrt(k)) * zbir k redova matrice W1 transponovano
```

umesto mnozenja gustog vektora od kojih je skoro sve nula. Jedina operacija pune
sirine koja ostaje je izlazni GEMV dekodera. Mereno na M4 Pro, `score()` traje
**0,03 ms** na katalogu od 800 recepata i **0,54 ms** (medijana 0,53; p95 0,59) na
katalogu velicine pravog Food.com skupa od 42.000 recepata.

---

## 7. Poznata ogranicenja

- **EASE je memorijski najskuplji korak.** Za ~42.000 recepata gusta matrica
  `B` je oko 7 GB, a vrhunac tokom inverzije oko 9 GB. Trenira se u zasebnom
  procesu i nikada uporedo sa MPS poslom. Ako masina to ne izdrzi, postoji
  `--max-items N` koji model ogranicava na N najpopularnijih recepata; tada EASE ne
  moze da preporuci nista van te glave kataloga, sto se mora navesti kao
  ogranicenje merenja. Na disku se `B` cuva kao float16 (3,5 GB umesto 7 GB) -
  vrednosti su reda 1e-3 do 1e-1, a skor je zbir nekoliko desetina njih, pa
  zaokruzivanje ne menja rangiranje.
- **NeuMF nema pretreniranje grana** (vidi sekciju 2).
- **NeuMF nema strong generalizaciju** (vidi sekciju 3).
- Nema modela zasnovanog na sadrzaju ni hibrida - poredjenje je namerno svedeno na
  cisto kolaborativne modele, zbog roka i obima rada.
- Metrike u `config.json` izvezenog modela su sa **podele**, ne sa finalnog modela
  treniranog na svim podacima; finalni model po definiciji nema izdvojen test skup.
