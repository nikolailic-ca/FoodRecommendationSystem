# Rezultati poredjenja modela

Podaci: 539,959 pozitivnih interakcija (25,959 korisnika x 39,886 recepata), pozitivna ocena >= 4, k-core (korisnik >= 3, recept >= 5).

Seed: 42 | commit: `9e34808` | weak korisnici: 23,363 | strong korisnici: 2,596

## Weak generalizacija (primarni pogled)

Svi korisnici su u treningu; 20% njihovih pozitivnih interakcija je izdvojeno za test.

| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |
|---|---|---|---|---|---|
| Popularity | 0.0274 | 0.0430 | 0.0167 | 0.0212 | 0.0014 |
| ItemKNN | 0.0256 | 0.0381 | 0.0173 | 0.0210 | 0.7139 |
| EASE | 0.0262 | 0.0382 | 0.0179 | 0.0214 | 0.6670 |
| Mult-DAE | 0.0293 | 0.0450 | 0.0191 | 0.0236 | 0.0233 |
| Mult-VAE | 0.0258 | 0.0412 | 0.0157 | 0.0200 | 0.2829 |
| NeuMF | 0.0268 | 0.0432 | 0.0162 | 0.0210 | 0.0099 |
| _slucajno rangiranje_ | 0.0003 | 0.0005 | 0.0003 | 0.0005 | - |

## Strong generalizacija (hladan start)

10% korisnika nikada nije bilo u treningu; 80% njihovih interakcija se ubacuje kao ulaz, 20% su ciljevi. NeuMF ovo ne moze - nema red u tabeli korisnickih ugradjivanja za nepoznatog korisnika.

| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |
|---|---|---|---|---|---|
| Popularity | 0.0318 | 0.0466 | 0.0196 | 0.0239 | 0.0010 |
| ItemKNN | 0.0276 | 0.0440 | 0.0178 | 0.0226 | 0.1438 |
| EASE | 0.0287 | 0.0434 | 0.0195 | 0.0238 | 0.1243 |
| Mult-DAE | 0.0355 | 0.0532 | 0.0225 | 0.0277 | 0.0164 |
| Mult-VAE | 0.0329 | 0.0482 | 0.0212 | 0.0256 | 0.0242 |
| NeuMF | N/A | N/A | N/A | N/A | N/A |

## Cena treniranja i skorovanja

| Model | Najbolja epoha | Trening (s) | Skorovanje (ms/korisnik) |
|---|---|---|---|
| Popularity | - | 0.0 | 0.002 |
| ItemKNN | - | 17.7 | 0.089 |
| EASE | - | 77.3 | 6.702 |
| Mult-DAE | 32 | 219.3 | 0.038 |
| Mult-VAE | 20 | 198.3 | 0.062 |
| NeuMF | 3 | 47.9 | 1.002 |

Skorovanje je mereno nad celim katalogom po korisniku, na istom uredjaju na kome je model treniran. Razlika izmedju NeuMF-a i Mult-VAE je sustinska: Mult-VAE skoruje ceo katalog jednim prolazom kroz mrezu, dok NeuMF mora da provuce svaki par (korisnik, recept) kroz MLP.

## Upozorenja

Ocekivanja prenesena iz literature o gustim skupovima koja ovaj skup ne ispunjava. Provereno je da nisu posledica greske - oracle model daje Recall@20 = 1,000, slucajni 0,000506 pri ocekivanih 20/n_items = 0,000501, a ItemKNN je rucno proveren nad stvarnim korisnikom. Puna istraga je u ai/results/README.md, sekcija 6.

- itemknn Recall@20 (0.0381) nije dostigao dvostruku popularnost (0.0861) - ocekivanje kalibrisano na gustim skupovima.
- ease Recall@20 (0.0382) nije dostigao dvostruku popularnost (0.0861) - ocekivanje kalibrisano na gustim skupovima.
- multvae Recall@20 (0.0412) je ispod popularity (0.0430) - proverite normalizaciju ulaza i maskiranje istorije pre arhitekture.
