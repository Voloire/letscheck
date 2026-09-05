# Fonti del catalogo locale

Il database `data/catalog.sqlite3` è un artefatto incluso e di sola lettura a
runtime. Si ricostruisce soltanto con un comando esplicito, dagli snapshot in
`data/raw`:

```powershell
.\.venv\Scripts\python.exe tools\build_catalog.py
```

Il builder non scarica dati. Usa Astropy 8.0.1 durante la costruzione per le
conversioni di frame; l'accesso al catalogo usa soltanto `sqlite3` della
libreria standard e non accede alla rete.

## Fonti e trasformazioni

| Catalogo | Snapshot e citazione | Coordinate importate | Licenza o termini |
| --- | --- | --- | --- |
| Messier, NGC, IC | [OpenNGC](https://github.com/mattiaverga/OpenNGC), commit `da90466031b0372c896588b85be6016c617e205b`; Mattia Verga e contributori | RA/Dec J2000, interpretate come FK5 J2000 e trasformate in ICRS | CC-BY-SA-4.0; testo integrale in `data/raw/openngc-cc-by-sa-4.0.txt` |
| Sh2 | CDS/VizieR VII/20; Sharpless, 1959, ApJS 4, 257, `1959ApJS....4..257S` | RA/Dec FK4 B1900 originali trasformate in ICRS; il file offre anche valori B1950 | Il ReadMe non indica una licenza specifica del dataset |
| LDN | CDS/VizieR VII/7A; Lynds, 1962, ApJS 7, 1, `1962ApJS....7....1L` | RA/Dec FK4 B1950 trasformate in ICRS | Il ReadMe non indica una licenza specifica del dataset |
| vdB | CDS/VizieR VII/21; van den Bergh, 1966, AJ 71, 990, `1966AJ.....71..990V`; coordinate J2000 da Magakian, 2003, A&A 399, 141, `2003A&A...399..141M` | FK5 J2000 di Magakian trasformate in ICRS quando il cross-id vdB è univoco; coordinate galattiche VII/21 trasformate in ICRS per vdB 64, 90 e 127 | I ReadMe non indicano una licenza specifica dei dataset |

Le [condizioni CDS](https://cds.unistra.fr/legals/) consultate riportano che
l'accesso è gratuito, che ogni dataset va citato e che si applica la licenza
specifica del dataset. Dicono inoltre che i dataset composti da informazioni
pubbliche sono distribuiti sotto licenze aperte, ma i quattro ReadMe conservati
non nominano quale licenza si applichi a ciascun catalogo. Lo snapshot delle
condizioni, datato dalla pagina 17 aprile 2026, è in
`data/raw/cds-terms-2026-04-17.html`. Prima di una redistribuzione esterna del
database va chiarita la licenza specifica dei cataloghi CDS; questa nota non la
presume e non introduce una restrizione “non commerciale” assente dalle fonti.

## Censimenti ed eccezioni

Il database versione `2026.09.05-1` contiene 15.569 record fisici e questi
censimenti di sigle distinte:

| Catalogo | Sigle |
| --- | ---: |
| Messier | 110 |
| NGC | 8.440 |
| IC | 5.594 |
| Sh2 | 313 |
| vdB | 158 |
| LDN | 1.787 |

OpenNGC contiene 13.970 righe: 651 `Dup` vengono ricondotte al record indicato
dalla fonte e 10 `NonEx` sono escluse. M40 e M45 provengono dall'addendum.
M102 non viene risolta in silenzio: una richiesta esatta produce un errore
ambiguo che indica M101/NGC 5457 e NGC 5866. OpenNGC contiene inoltre ambiguità
esplicite per NGC 554, NGC 704, NGC 764, NGC 6839 e IC 1459; l'API le conserva
come più candidati.

VII/7A ha 1.791 righe. Le 15 numerazioni duplicate eliminate sono già assenti
dalla versione A; non vanno sottratte di nuovo. Le quattro righe finali prive di
numero LDN restano nello snapshot ma sono escluse dall'indice, lasciando 1.787
sigle esplicite.

Magakian contiene 913 righe, delle quali 163 hanno un cross-id vdB e coprono
157 dei numeri 1–158. Il numero 127
non è presente. I numeri 64 e 90 hanno solo componenti multipli, quindi il
builder non ne sceglie uno arbitrariamente: per questi tre record usa la
posizione galattica del catalogo VII/21. Tutte le coordinate finali sono finite,
con `0 <= RA < 360` e `-90 <= Dec <= 90`.

I nomi comuni presenti nel campo `Common names` di OpenNGC vengono conservati
come alias ricercabili. Il campo controverso di IC 434 (`Flame Nebula`, `Orion
B`) viene escluso: l'identificativo di catalogo e le coordinate restano
disponibili senza propagare un'associazione dubbia.

## Integrità degli snapshot principali

I digest sono SHA-256 e sono anche registrati nei metadati del database:

```text
941f422c3be598eedd9c432b5f710c2fb5637120b96ef241f200467141495710  openngc-ngc.csv
a6220000142234b66a18a64463bbb38e1b5eff0bbd9d61d744ee0ff14a08eae2  openngc-addendum.csv
7ef4f74a2dfe6ebbb5237de101a6432d1af1491a39a10bdd93372122df1b896b  vizier-vii-20-catalog.dat.gz
44be8ef67fddbc43d5b96dad97a798e2cfe110526cc8654e50cf323f0f328832  vizier-vii-7a-ldn.dat
8d8fd85e18b77666275fdcb4e6d47dc7fd03581fbe216683f266170b14feab6d  vizier-vii-21-catalog.dat
9772e2aaf4545bead6de42b6410abb420d0e65ac5955231df9bcbe1109aea365  vizier-j-aa-399-141-table1.dat
```

Ogni oggetto conserva nel database anche le coordinate testuali originali e il
frame usato per interpretarle. Versione, statistiche di build e digest delle
fonti sono nella tabella `metadata`.
