# M4 devir: Cagatay -> Egemen

> Arsivlenmis ara asama devir notu. Her iki bolum tamamlandi; guncel durum
> README, eda_report.md ve docs/evidence/m4_results.json icindedir.
> Nihai teslim referansi: `m4`. Asagidaki is bolumu devir aninin kaydidir.

Cagatay'in C1-C4 ve Egemen'in E1-E4 bolumleri tamamlandi.
M3 teslim surumu `m3` referansinda korunuyor.

## Kurulum ve tekrar uretme

Sanal ortami etkinlestirdikten sonra:

```bash
python -m pip install -r requirements.txt
python src/load.py
python src/clean.py
python src/validate.py
python notebooks/build_m4.py
jupyter nbconvert --to notebook --execute --inplace notebooks/m4_eda.ipynb
python notebooks/check_m4_reproducibility.py
```

Sirayla kaynaklar: `m4_cagatay.py`, varsa `m4_egemen.py`, sonra `m4_finalize.py`.
`m4_eda.ipynb` uretim dosyasidir; elle iki kopya halinde duzenleme. Kaynaklarda her hucre
`# %%` veya `# %% [markdown]` ile baslar. Birletirme scripti yalniz donusturur; Jupyter
komutu gercek kernelde calistirir. Butun parametreler ilk kod hucresindedir.

## Ortak arayuz

Egemen'in `notebooks/m4_egemen.py` dosyasi ilk hucresinde markdown aciklamasi ile baslasin.
Mevcut degiskenler: `ROOT`, `PARAMS`, `con`, `before`, `look_log`, `results`, `FIGURE_DIR`,
`EVIDENCE_DIR`. `con` salt okunurdur; kapatma, yeniden yazma baglantisi acma, veri duzeltme
yapma. Son ortak footer butun 17 tabloyu hashler, log/sonuclari yazar ve baglantiyi kapatir.
Sonuclarini `results['egemen']` gibi ayri bir anahtar altina ekle; Cagatay degerlerini ezme.

- Ortak yardimcilar: `src/explore.py`. `query()` yalniz beyaz listedeki SQL dosyalarini
  okur; kendi `m4_egemen_*.sql` dosyalarini listeye acikca ekle veya ayri sabit SQL yardimcisi
  kullan. Degerleri `:name`/`?` ile bagla; SQL'e string formatlama yapma.
- Her SQL'de uygulanan bayrak filtresi yorumda ve gercek WHERE kosulunda belli olmali.
  Raw icin bayrak olmadigini belirt; kullandigin saat/takvim ve payda acik olsun.
- `look_log.add(id, question, choices, owner='Mehmet Egemen Karagoz')` ile her baktigin
  karsilastirmayi kaydet. Cagatay logunu bastan sifirlama; kimlikler benzersiz olsun.
- `save_figure(...)` stil/baslik/caption sozlesmesini kullanabilir. Sekilleri FIGURE_DIR'e,
  diger uretim kanitlarini EVIDENCE_DIR'e yaz. Test bu dizinleri ortam degiskenleriyle ayirir.
- Analitik esikler `>=0.2` ve `>=0.5`; yerel mevzuat atanmadi. Il/bolge siniflandirmasi
  dogrulanmadan municipality kodundan bolge turetme.
- Primary lice: ok + unusual_high + unusual_low. Primary temperature: ok + unusual_high
  + unusual_low + suspect_stuck + suspect_spike. Strict her ikisi icin yalniz ok.
- Ana donem 2022-2025; 2026 yalniz kapsam tablosunda son tamamlanan hafta 40'a kadar.
  2026'yi zaman bolumune ekleyeceksen parcali donem olarak ayri goster.

## Hazir sonuclar

- 6004 raporda >=0.2: 1540 (%25.6496); >=0.5: 120 (%1.9987).
- Strict ok: 5881 raporda sirayla 1417 (%24.0945) ve 44 (%0.7482).
- Raw degerlerin strict-clean anahtarlarda hesaplanmasi strict sonucu aynen veriyor:
  fark temiz sayidan degil secilen gozlemlerden kaynaklaniyor.
- %75 kapsam: 71/160 tam ciftlik-yil, 3306 rapor, 37 ciftlik. Esik paylari sirayla
  %26.5880 ve %1.8451. Katilan yillar ciftlikler arasinda farkli; kompozisyonu incele.
- Uc sekil hazir: genel histogram+ECDF, yillik histogram+ECDF, kapsam isi haritasi.
- 19 konfigurasyon bakisi kayitli; bagimsiz test sayisi diye sunma.
- Rapor 2-4 ve F-01..F-05 hazir; tam sayilar notebook ve docs/evidence/M4 JSON dosyalarinda.

## E1-E4 sirasi

1. E1: kaynak hafta/takvim tanimini dogrula ve gerekcelendir. Saatlik olcum yok; UTC
   retrieval timestamp'ini olcum saati gibi kullanma. Kenarlari, iki zaman olcegini ve
   dogrulanmis takvim pencerelerini incele. Bahar pencereleri dogrulanmadan yasal oran deme.
2. E2: sicaklik-bit grafigi, ardindan Pearson/Spearman. Uc gozlem ve bayrak duyarliligi;
   ortak mevsim/ciftlik/yil yapisini katmanlayarak incele. Tahmin modeli kurma.
3. E3: karsilastirma rejimlerini sonucu secmeden once kaydet. Ciftlik-yil ozetleri
   uretilebilir ama tekrar eden ciftlik-yillari bagimsiz sayma; ciftligi kume olarak
   bootstrap et ve yillarini birlikte koru. Ayni ciftlik yeterli mevsim kontrolu degildir;
   mevsim/hafta-yil ortusmesini de incele, yetersizse acikca soyle. %95 aralik ve look sayisi.
4. E4: rapor 5-9 ve nihai ozet; kendi bulgularin, geri temizlemeye ve ileri modellemeye
   listeleri; README'de baslik grafigi. Toplam 4-8 sekil gerekir, su anda 3 var. Zaman,
   iliski ve aralik sekilleri eklendiginde en az 6 olacak. Her sekil kontrol listesini uygula.
5. Temiz kurulum + build + Restart & Run All + hash/sekil kontrollerini yeniden calistir.
   `check_m4_reproducibility.py` butun uretilen PNG'leri ve sonuc JSON'unu karsilastirir.
   Son footer'in kapsam ve durum metinlerini nihai asamaya gore guncelle.
   DYS paketi `python notebooks/package_m4.py` ile yeniden uretilir.

## Katki ve kalan durum

Cagatay icin dort anlamli commit: altyapi, hesaplamalar, calistirilmis notebook/sekiller
ve yeniden uretim kaniti, rapor/devir. Egemen asamasinda da dort anlamli commit hedefleniyor.
Nihai sonuclar, grafikler ve yeniden uretim kanitlari repoda kayitlidir.
