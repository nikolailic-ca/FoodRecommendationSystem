# Food Recommendation System

Diplomski rad. Student: Nikola Ilic.
Tema: Razvoj softvera za personalizovanu preporuku hrane primenom metoda masinskog ucenja.

Web aplikacija koja korisniku preporucuje recepte na osnovu toga sta je ocenio. Podaci
dolaze iz javnog Food.com skupa sa Kaggle-a: 231.637 recepata i 1.132.367 ocena.
Novi korisnik oceni pet recepata, model iz toga izgradi profil ukusa i dalje preporucuje
bez ponovnog treniranja.

---

## Sadrzaj

- [Arhitektura](#arhitektura)
- [Portovi](#portovi)
- [Preduslovi](#preduslovi)
- [Podesavanje](#podesavanje)
- [Baza podataka](#baza-podataka)
- [Ucitavanje dataseta](#ucitavanje-dataseta)
- [Fotografije recepata](#fotografije-recepata)
- [Pokretanje aplikacije](#pokretanje-aplikacije)
- [Pregled API-ja](#pregled-api-ja)
- [AI pipeline](#ai-pipeline)
- [Resavanje problema](#resavanje-problema)

---

## Arhitektura

Cetiri sloja, svaki u svom folderu:

| Folder | Sadrzaj |
|---|---|
| `frontend/` | React 19 + TypeScript + Vite, Tailwind v4 i shadcn/ui, TanStack Query |
| `backend/` | FastAPI, SQLAlchemy 2.0, Alembic, psycopg 3 |
| `ai/` | PyTorch pipeline za preporuke i istrazivacki notebook-ovi |
| `database/` | ne postoji, baza zivi u Docker kontejneru |

**Tok podataka.** ETL skripta jednom pretvori dva CSV fajla u PostgreSQL tabele.
Backend cita iskljucivo iz baze. Model se trenira odvojeno u `ai/`, izvozi kao artefakt,
i backend ga ucitava pri pokretanju.

**Tok preporuke.** Filteri (ime, vreme, sastojci, tagovi) prvo suze skup kandidata kroz
SQL. Model oceni ceo katalog, skorovi van kandidata i vec ocenjeni recepti se maskiraju,
pa se uzme prvih N. Za svaku preporuku se trazi najblizi recept koji je korisnik vec
pozitivno ocenio, i to je objasnjenje koje se prikazuje na kartici.
**Ako artefakt modela ne postoji, backend se svejedno podize i vraca liste po
popularnosti.** Aplikacija nikad ne pada zbog modela.

**Normalizacija sastojaka.** Svaki sastojak se svodi na osnovni oblik i razlaze na reci,
pa filter pogadja celu rec a ne podniz. Zato `egg` pronalazi `eggs` i `egg whites`,
ali ne i `eggplant`.

---

## Portovi

| Servis | Port |
|---|---|
| PostgreSQL | `127.0.0.1:15432` |
| Backend API | `8001` |
| Frontend (Vite) | `5180` |

Portovi su namerno neuobicajeni. Na racunaru na kom je projekat razvijan port `5432`
koristi tunel ka produkcionoj bazi drugog projekta, a `5433`, `8000` i `5173` zauzimaju
drugi projekti. Da bi greska bila nemoguca, `backend/app/core/config.py` **odbija da se
pokrene** ako `DATABASE_URL` gadja `5432` ili `5433`, ili ako se baza ne zove `foodrec`.

---

## Preduslovi

- **Docker Desktop**, pokrenut. Baza radi u kontejneru.
- **uv** za Python pakete: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  (Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`)
- **Node.js 20 ili noviji** za frontend.
- Python se ne instalira rucno, `uv` ga sam preuzima prema `.python-version`.

Verzije na kojima je razvijano: Python 3.14, Node 25, Docker 29, uv 0.11.

---

## Podesavanje

```bash
git clone https://github.com/nikolailic-ca/FoodRecommendationSystem.git
cd FoodRecommendationSystem
cp .env.example .env
```

Otvori `.env` i podesi:

| Promenljiva | Opis |
|---|---|
| `DATABASE_URL` | Veza ka bazi. Podrazumevana vrednost odgovara Docker Compose fajlu. |
| `JWT_SECRET` | Tajni kljuc za potpisivanje tokena. **Obavezno promeni**, najmanje 32 znaka. |
| `JWT_EXPIRES_DAYS` | Koliko dana traje prijava. Podrazumevano 7. |
| `CORS_ORIGINS` | Adrese sa kojih frontend sme da zove API. |
| `PEXELS_API_KEY` | Opciono, samo za preuzimanje fotografija. |
| `MODEL_ARTIFACT_DIR` | Gde backend trazi istrenirani model. |
| `ONBOARDING_MIN_RATINGS` | Koliko ocena novi korisnik mora da da. Podrazumevano 5. |
| `POSITIVE_RATING_THRESHOLD` | Od koje ocene se recept smatra da se svideo. Podrazumevano 4. |

Nasumican `JWT_SECRET`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Instalacija Python paketa:

```bash
uv sync --all-groups
```

Ko ne koristi `uv`, moze i preko `pip install -r requirements.txt`, ali je taj fajl
izvezen iz `pyproject.toml` i sluzi samo kao rezerva.

---

## Baza podataka

```bash
docker compose up -d
docker compose ps                 # sacekaj da pise (healthy)
uv run alembic -c backend/alembic.ini upgrade head
```

Semu cine tabele `users`, `user_ratings`, `user_favorites`, `recipes`,
`recipe_ingredients`, `ingredients`, `recipe_tags`, `tags` i `recipe_images`.
Pretraga po imenu ide preko trigram indeksa, filter sastojaka preko GIN indeksa nad
nizom reci.

Za pristup bazi iz terminala:

```bash
docker compose exec db psql -U foodrec -d foodrec
```

---

## Ucitavanje dataseta

Dataset se ne nalazi u repozitorijumu jer ima oko 600 MB.

1. Skini ga sa Kaggle-a (potreban je nalog):
   https://www.kaggle.com/datasets/shuyangli94/food-com-recipes-and-user-interactions
2. Raspakuj `RAW_recipes.csv` i `RAW_interactions.csv` u folder `datasets/` u korenu
   projekta. Ostali fajlovi iz arhive nisu potrebni.
3. Pokreni ETL:

```bash
uv run python -m backend.scripts.etl
```

Traje oko dva minuta i ispisuje broj redova po tabeli. Ponovno pokretanje je bezbedno,
recepti se azuriraju a korisnicki nalozi i ocene ostaju.

Ocekivani rezultat:

| Tabela | Redova |
|---|---|
| recipes | 231.637 |
| recipe_ingredients | 2.096.582 |
| recipe_tags | 4.141.579 |
| ingredients | 13.665 |
| tags | 551 |

Za brzu probu bez dataseta postoji i skripta sa demo receptima:

```bash
uv run python -m backend.scripts.seed_demo          # ubaci demo recepte
uv run python -m backend.scripts.seed_demo --clear  # ukloni ih
```

---

## Fotografije recepata

Dataset nema slike. Svaki recept zato dobija generisanu plocicu, obojeni gradijent
izveden iz njegovog broja i ikonicu prema tagovima. To radi bez interneta i bez ikakvog
podesavanja.

Ko zeli prave fotografije, treba mu besplatan kljuc sa https://www.pexels.com/api/,
koji ide u `.env` kao `PEXELS_API_KEY`. Zatim:

```bash
uv run python -m backend.scripts.fetch_images --limit 2000
```

Skripta ide redom po popularnosti, trazi fotografiju po imenu recepta i pamti adresu
slike, ime fotografa i link ka njegovom profilu, jer Pexels trazi da autor bude naveden.
Prekid je bezbedan, novo pokretanje nastavlja odakle je stalo. Besplatni nalog dozvoljava
200 zahteva na sat.

Korisne opcije: `--delay` menja pauzu izmedju poziva, `--retry-missing` ponovo pokusava
recepte kod kojih pretraga ranije nije nasla nista.

---

## Pokretanje aplikacije

Backend, iz korena projekta:

```bash
uv run uvicorn backend.app.main:app --reload --port 8001
```

Frontend, u drugom terminalu:

```bash
cd frontend
npm install
npm run dev
```

Aplikacija je na http://localhost:5180, dokumentacija API-ja na
http://127.0.0.1:8001/docs.

Provera da je sve zivo:

```bash
curl http://127.0.0.1:8001/health
# {"status":"ok","db":"ok","model_loaded":false,"model":"popularity"}
```

Kada baza nije dostupna, endpoint vraca HTTP 503 i `"status":"error"` - monitoring
tako ne vidi zdrav servis dok svaki drugi endpoint puca.

`model_loaded` kaze da li je artefakt modela ucitan. `model` kaze cime se rangiraju
preporuke korisniku koji ima bar jednu pozitivnu ocenu iz kataloga modela. Ta dva nisu
isto: i sa ucitanim artefaktom svaki tek registrovani nalog dobija `popularity`, sve dok
ne oceni recept koji model poznaje.

---

## Pregled API-ja

| Metoda | Putanja | Opis |
|---|---|---|
| POST | `/auth/register` | Registracija, odmah vraca token |
| POST | `/auth/login` | Prijava |
| GET | `/users/me` | Podaci o nalogu, broj ocena, da li je onboarding zavrsen |
| GET | `/users/me/ratings` | Ocenjeni recepti |
| PUT | `/users/me/ratings/{id}` | Postavi ili izmeni ocenu |
| DELETE | `/users/me/ratings/{id}` | Ukloni ocenu |
| GET | `/users/me/favorites` | Sacuvani recepti |
| PUT, DELETE | `/users/me/favorites/{id}` | Sacuvaj ili ukloni |
| GET | `/recipes` | Pretraga i stranicenje |
| GET | `/recipes/{id}` | Detalji recepta |
| GET | `/recipes/{id}/similar` | Slicni recepti |
| GET | `/ingredients`, `/tags` | Predlozi za autocomplete |
| GET | `/recommendations/me` | Preporuke sa filterima i objasnjenjem |
| GET | `/recommendations/onboarding` | Raznovrstan set za nove korisnike |

Zasticene rute traze zaglavlje `Authorization: Bearer <token>`.

---

## AI pipeline

Produkcijski kod je paket `ai/src/foodrec/`. Notebook-ovi u `ai/notebooks/` su
istrazivacki trag i nisu deo aplikacije.

**Serviran model je Mult-VAE**, varijacioni autoenkoder. Bira se zato sto profil korisnika
racuna iz onoga sto je ocenio, pa novi korisnik dobija preporuke odmah, bez ponovnog
treniranja. Modeli poput NeuMF-a traze korisnika u tabeli naucenoj tokom treninga i za
novog korisnika nemaju vektor.

U radu se porede sest modela na istoj podeli podataka: Popularity, ItemKNN, EASE,
Mult-DAE, Mult-VAE i NeuMF.

Ceo lanac:

```bash
uv run python -m foodrec.data                  # filtriranje i mapiranje indeksa
uv run python -m foodrec.split --seed 42       # podela na train, val i test
uv run python -m foodrec.train --model multvae # isto za ostalih pet modela
uv run python -m foodrec.evaluate --model all --summary
uv run python -m foodrec.train --model multvae --full   # trening na svim podacima
uv run python -m foodrec.export --model multvae
uv run python -m foodrec.serving --smoke
```

Posle izvoza restartuj backend, `/health` treba da prijavi `mult_vae`.

**Evaluacija ima dva pogleda.** U prvom su svi korisnici u treningu a sakrije im se
petina ocena, sto omogucava posteno poredjenje sa NeuMF-om. U drugom je desetina
korisnika potpuno izbacena iz treninga, cime se meri koliko model vredi za tek
registrovanog korisnika. NeuMF u tom pogledu nema rezultat, i to je samo po sebi nalaz
o hladnom startu.

**Napomena o ranijoj gresci u evaluaciji.** U notebook-u `05_ncf_v2.ipynb` mapiranje
identifikatora u indekse pravljeno je vise puta iz razlicitih tabela, pa su test parovi
gledali vektore drugih recepata. Otuda tacnost ispod nasumicne. Novi pipeline pravi jedno
zamrznuto mapiranje pre podele podataka, cuva ga uz artefakt, i sirovi identifikator
nikad ne stize do modela.

Rezultati i uputstvo za ponavljanje su u `ai/results/`.

---

## Resavanje problema

**Backend nece da se pokrene i javlja da je port zabranjen.** To je namerna zastita.
Proveri da `DATABASE_URL` u `.env` koristi port `15432` i bazu `foodrec`.

**`docker compose up` javlja da je port zauzet.** Nesto drugo slusa na `15432`.
Proveri sa `lsof -nP -iTCP:15432` i ugasi to, ili promeni port i u `docker-compose.yml`
i u `.env`.

**ETL puca na Windows-u zbog kodiranja.** Fajlovi moraju da se citaju kao UTF-8.
Skripta to vec radi, ali ako menjas kod, ne izostavljaj `encoding="utf-8"`.

**`/health` uvek pokazuje `popularity`.** Artefakt modela ne postoji na putanji iz
`MODEL_ARTIFACT_DIR`. Pokreni treniranje i izvoz iz sekcije o AI pipeline-u.

**Frontend prijavljuje CORS gresku.** Vite mora da radi na portu `5180`. Ako ga pokreces
na drugom portu, dodaj tu adresu u `CORS_ORIGINS` u `.env` i restartuj backend.

**Sve kartice prikazuju plocice umesto fotografija.** To je ocekivano dok se ne pokrene
skripta za preuzimanje fotografija, i aplikacija tako radi sasvim normalno.
