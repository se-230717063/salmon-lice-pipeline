# M3 devir notu: Cagatay -> Egemen

Bu devirde Cagatay'in olcum profili, temizleme kurallari, tablo semalari ve rapor 1-5
bolumleri tamamlandi. **M3 tamamlanmadi; m3 etiketi atilmayacak.** README'deki genel
durumun M2 kalmasi bu asamada kasitli. Veri, mevcut M1 arsivinden; API tekrar cagrilmadi.

## Calistirma

```bash
git pull --rebase
python src/load.py
python notebooks/profile_quick.py
python src/clean.py
python notebooks/check_m3_safety.py
```

Notebook: `notebooks/m3_profile.ipynb`; ciktilari kayitli, M2 DB uzerinde bastan sona
calisir. Jupyter arayuzu kullaniliyorsa kendi Python ortamini kernel olarak sec.
Kodun kendisi ek Python kutuphanesi gerektirmez. Notebook M2'ye veya clean tablolara yazmaz.

`clean.py` su an yalnizca iki olcum tablosunu doldurur. Diger dort clean tablo ile
esleme tablolari sema sozlesmesidir; bu asamada bostur. Bu nedenle cikti acikca
`MEASUREMENTS COMPLETE; M3 INCOMPLETE` der. Bu, nihai teslim ciktisi degildir.

## Egemen'in yapacaklari (sirayla)

1. Tedavi, metin, kategori, birim ve kimlik incelemesini kendin yap. Notebook'taki
   repr envanterleri baslangic kanitidir; tum islemleri Cagatay'in bulgusu olarak
   kopyalama. Belediye 5054'un M2 Type 1 kaydi iki eski yazimi bir arada gostermeyebilir;
   kaybolmus tarihi M3'te uydurma. Gerekirse M2 dokumani/arsivine kanit icin bak,
   ancak clean.py yalniz M2 tablolarindan veri okumali.
2. Gerekli esleme CSV'lerini `data/mappings/` altina koy. Her karar icin decided_by,
   decided_at (ISO tarih/zaman), note ve kaynak ID kullan; surrogate key kullanma.
3. `src/clean_categories.py` icinde asagidaki fonksiyonu uygula; clean.py bunu varsa
   otomatik cagirir. Import yan etkisi, API/ham dosya okumasi, commit, executescript,
   bagimsiz DB baglantisi veya M2 tablosuna yazma olmamali.

```python
def build_categories(con, mappings_dir):
    # con: clean.py'nin acik transaction'i, foreign_keys=ON
    # municipality_clean, locality_clean, treatment_weekly_clean,
    # treatment_event_clean ve kullanilan mapping tablolarini burada doldur.
    # DELETE/INSERT veya upsert, yalniz kendi clean/mapping tablolarinda.
    # Her degeri SQL placeholder'i ile gonder.
    # Hata olursa exception firlat; clean.py tum isi geri alir.
    return {
        "mapping_rows_loaded": {},
        "unmatched_mapping_entries": [],
        "table_rows": {},
        "flag_counts": {},
    }
```

4. Semanin tamami `sql/clean_schema.sql` icinde. Alti clean tablo M2 anahtar/satir
   duzeyini korur. Tedavi category anahtarini degistirme; standardize edilen kategori
   `category_clean` alanina gider. Esleme sozlesmeleri:

| CSV / tablo adi | Kolonlar |
|---|---|
| municipality_name_mapping | municipality_no, raw_name, clean_name, decided_by, decided_at, note |
| locality_name_mapping | locality_no, raw_name, clean_name, decided_by, decided_at, note |
| treatment_value_mapping | field, raw_value, clean_value, decided_by, decided_at, note |
| locality_identity_mapping | source_locality_no, canonical_locality_no, decided_by, decided_at, note |

   `field`: category, treatment_type, substance_name veya substance_id. CSV basliklari
   tablo kolonlariyla ayni olmali. Eslesmeyen girdileri ciktiya yaz; otomatik fuzzy karar
   verme. Kimlik sorunu bulamazsan yapay esleme uretme; yoklugunu kontrolle belgele.
   Bos/uygulanmayan esleme turlerini raporda acikla. Gerekirse semayi devirden sonra
   sen guncelleyebilirsin; ayni dosyalarda es zamanli calisma yok.
5. **Kimlik birlestirme veya birim degisikligi kanitlanirsa**, per-entity istatistiklerden
   once coz. Su an temizleyici M2 locality_key gruplarini kullanir ve kategori modulu
   olcum yazimindan sonra calisir. Boyle bir bulguda once mapping asamasini ayirip
   gruplamayi guncelle, sonra olcumleri yeniden hesapla; mevcut sayilari korumaya calisma.
6. `validate.py`: en az alti gerekli PASS/WARN/STOP kontrolu; her STOP'u gecici DB'de
   bilerek boz ve non-zero exit kanitini ekle. Altı clean tablo icin satir/key uyumunu,
   fiziksel kurallari, FK'leri, eksiklik/kapsami ve veriye ozel sorunu kontrol et.
   Kapsam evreni 2.710 sicil kaydi degil, `config/cohort.txt` icindeki 40 locality.
   Tedavisi olmayan ciftligi otomatik hatali sayma. Gunchelligi 2026-10-10 cekimiyle
   iliskilendir; bugunun tarihine gore bu sabit snapshot'i gereksiz STOP yapma.
7. Rapor 6-8, issues register'a kendi bulgularin ve README Data Quality bolumunu tamamla.
   Tum notebook'u yeniden calistir. 1-5'te nihai sayilar degistiyse guncelle.
8. Nihai entegrasyon: `python src/clean.py --require-categories`, iki clean calistirmasi,
   validate.py ve tum clean/mapping tablolarinin hash/rollback kanitlari. Mevcut
   `check_m3_safety.py` yalnizca olcum tablolari ve yedi M2 tablosunu hashler;
   kategori asamasinin kendi hash ve hata enjeksiyon kanitlarini da ekle.
9. Son kontrol ve anlamli commit'lerden sonra teslim: repo URL, temizlenmis DB,
   iki clean ciktisi, validate ciktisi, **ham veri ZIP**. M3 etiketi en son.

## Tamamlanan kanitlar ve sinirlar

- Ham dosyalardan yeniden uretilen M2 mevcut DB ile yedi tabloda ayni.
- Iki olcum clean tablosunun tum anahtar ve raw degerleri kaynakla ayni.
- M2 hashleri clean oncesi/sonrasi ayni; ilk kurulum ve yeniden kurulumda yarida hata
  tum transaction'i geri aliyor, ilk kurulum DDL'i de geri aliniyor.
- IQR katsayisi 3 -> 4 -> 3: sadece IQR bayraklari degisiyor, eski icerik geri geliyor.
- Gecersiz ISO hafta, gelecek dolu gozlem ve has_reported celiskisi sentetik kayitlarla
  kontrol edildi. Eksik hafta tekrar serisini kiriyor; sifir bit sayisi ariza sayilmiyor.
- Bayrak onceligi ve esik duyarliligi raporda. 196.18 C temizde NULL; 34.29 C korunuyor.
- Eksikligin gercek nedeni, tedavi yoklugunun anlami ve kimlik gecmisi kesinlesmedi.
- `docs/evidence/m3_measurements_*` dosyalari **ara asama** kanitlari; nihai teslim
  ciktisi diye kullanma. `m3_measurement_safety.json` M2 ve olcum hashlerini kaydeder.

## Katki ve commitler

Cagatay'in bu devir icin dort anlamli commiti var: profil araci, calistirilmis notebook,
temizleme hatti/semalar, guvenlik kanitlari/rapor/devir. Sen de kendi Git hesabinla
arastirma/eslemeler, kategori uygulamasi, validate/testler, rapor/README seklinde dort
anlamli commit hedefle. Sayiyi esitlemek icin bos commit atma. Push oncesi temiz calisma
agacinda `git pull --rebase`; raporda "Investigated by" alanina gercek katkini yaz.
