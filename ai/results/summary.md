# Rezultati poredjenja modela

Podaci: 539,959 pozitivnih interakcija (25,959 korisnika x 39,886 recepata), pozitivna ocena >= 4, k-core (korisnik >= 3, recept >= 5).

Seed: 42 | commit: `e7e2272` | weak korisnici: 23,363 | strong korisnici: 2,596

## Weak generalizacija (primarni pogled)

Svi korisnici su u treningu; 20% njihovih pozitivnih interakcija je izdvojeno za test.

| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |
|---|---|---|---|---|---|
| Popularity | 0.0274 | 0.0430 | 0.0167 | 0.0212 | 0.0014 |
| ItemKNN | 0.0256 | 0.0381 | 0.0173 | 0.0210 | 0.7139 |
| EASE | 0.0262 | 0.0382 | 0.0179 | 0.0214 | 0.6670 |
| Mult-DAE | 0.0302 | 0.0454 | 0.0198 | 0.0242 | 0.0936 |
| Mult-VAE | 0.0272 | 0.0432 | 0.0164 | 0.0211 | 0.2662 |
| NeuMF | 0.0281 | 0.0419 | 0.0168 | 0.0208 | 0.0114 |
| _slucajno rangiranje_ | 0.0003 | 0.0005 | 0.0003 | 0.0005 | - |

## Strong generalizacija (hladan start)

10% korisnika nikada nije bilo u treningu; 80% njihovih interakcija se ubacuje kao ulaz, 20% su ciljevi. NeuMF ovo ne moze - nema red u tabeli korisnickih ugradjivanja za nepoznatog korisnika.

| Model | Recall@10 | Recall@20 | NDCG@10 | NDCG@20 | Coverage@20 |
|---|---|---|---|---|---|
| Popularity | 0.0318 | 0.0466 | 0.0196 | 0.0239 | 0.0010 |
| ItemKNN | 0.0276 | 0.0440 | 0.0178 | 0.0226 | 0.1438 |
| EASE | 0.0287 | 0.0434 | 0.0195 | 0.0238 | 0.1243 |
| Mult-DAE | 0.0354 | 0.0534 | 0.0235 | 0.0289 | 0.0330 |
| Mult-VAE | 0.0351 | 0.0517 | 0.0223 | 0.0271 | 0.0190 |
| NeuMF | N/A | N/A | N/A | N/A | N/A |

## Cena treniranja i skorovanja

| Model | Najbolja epoha | Trening (s) | Skorovanje (ms/korisnik) |
|---|---|---|---|
| Popularity | - | 0.0 | 0.002 |
| ItemKNN | - | 17.7 | 0.081 |
| EASE | - | 77.3 | 7.514 |
| Mult-DAE | 76 | 556.1 | 0.048 |
| Mult-VAE | 27 | 290.8 | 0.060 |
| NeuMF | 5 | 58.6 | 0.545 |

Skorovanje je mereno nad celim katalogom po korisniku, na istom uredjaju na kome je model treniran. Razlika izmedju NeuMF-a i Mult-VAE je sustinska: Mult-VAE skoruje ceo katalog jednim prolazom kroz mrezu, dok NeuMF mora da provuce svaki par (korisnik, recept) kroz MLP.

## Upozorenja

Ocekivanja prenesena iz literature o gustim skupovima koja ovaj skup ne ispunjava. Provereno je da nisu posledica greske - oracle model daje Recall@20 = 1,000, slucajni 0,000506 pri ocekivanih 20/n_items = 0,000501, a ItemKNN je rucno proveren nad stvarnim korisnikom. Puna istraga je u ai/results/README.md, sekcija 6.

- itemknn Recall@20 (0.0381) nije dostigao dvostruku popularnost (0.0861) - ocekivanje kalibrisano na gustim skupovima.
- ease Recall@20 (0.0382) nije dostigao dvostruku popularnost (0.0861) - ocekivanje kalibrisano na gustim skupovima.
