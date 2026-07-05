# Hidamari Fork — İlerleme Analizi

> Fork: `MrSqy/hidamari` · Upstream: `jeffshee/hidamari` (GPL-3.0, Python/GTK3/VLC, meson)
> Analiz tarihi: 2026-07-05 · Temel alınan referans: `master` = `edfa052`

İncelenen dallar:

| Dal | `master`'a göre | İçerik |
|-----|-----------------|--------|
| `feature/playlist-support` | +2 commit | Playlist motoru + oynatma modu seçici |
| `feature/local-video-folder-navigation` | +4 commit | Playlist + klasör gezinme (playlist dalını **kapsar**) |

**Önemli topoloji notu:** `feature/playlist-support`, `feature/local-video-folder-navigation`'ın atasıdır (`git merge-base --is-ancestor` doğruladı). Yani ikinci dal, birincinin 2 commit'ini birebir içerir; üzerine 2 commit daha ekler. Bu, PR stratejisini doğrudan etkiler (bkz. Bölüm 7).

Commit zinciri:

```
a662fde feat(ui): add local video folder navigation   ┐ sadece local-video dalında
289360f fix(player): reset video transform on playlist switch ┘
029c791 feat(ui): add playback mode selector          ┐ her iki dalda ortak
e751519 feat(player): add playlist playback support without UI ┘
edfa052 (master) feature: solves some cpu leaks (#233)
```

---

## 1. DEĞİŞİKLİK ÖZETİ

### 1.1 Dosya bazında satır değişimi

**`feature/playlist-support` (master..):** 6 dosya, **+430 / −52**

| Dosya | Değişim |
|-------|---------|
| `src/player/playlist.py` | **+103 (yeni dosya)** |
| `src/player/video_player.py` | +252 / −51 |
| `src/assets/control.ui` | +45 |
| `src/utils.py` | +41 |
| `src/gui/control.py` | +26 |
| `src/commons.py` | +15 |

**`feature/local-video-folder-navigation` (master.., kümülatif):** 6 dosya, **+783 / −100**

| Dosya | Değişim | Not |
|-------|---------|-----|
| `src/gui/control.py` | +238 / −? | 537 → **717 satır** |
| `src/player/video_player.py` | +267 / −? | 610 → **793 satır** |
| `src/assets/control.ui` | +129 | Nav çubuğu + mod seçici |
| `src/utils.py` | +131 | 550 → **649 satır** |
| `src/player/playlist.py` | +103 (yeni) | 103 satır |
| `src/commons.py` | +15 | Config anahtarları |

### 1.2 Yeni sınıflar / fonksiyonlar

**`src/player/playlist.py` — yeni `VideoPlaylist` sınıfı** (tek sorumluluk, doğru şekilde ayrı dosyaya çıkarılmış):
`__init__`, `_load_paths`, `_load_folder`, `_normalize_path`, `_is_valid_video`, `is_empty`, `get_current`, `next`, `previous`, `_next_random_index`, `__len__`. Sınıf sabitleri: `SUPPORTED_EXTENSIONS`, `VALID_MODES`.

**`src/player/video_player.py`:**
- `PlayerWindow.attach_media_events()`, `PlayerWindow.reset_video_transform()`
- `VideoPlayer`: `_playlist_mode`, `_is_playlist_mode`, `_setup_playlist`, `_normalize_data_source` (static), `_source_for_monitor` (static), `_probe_video_dimensions`, `_set_window_video_source`, `_set_single_video_sources`, `_set_playlist_video_source`, `_attach_playlist_events`, `_on_playlist_end_reached`, `_on_playlist_error`, `_advance_playlist`, `_current_video_source`
- `data_source.setter` tamamen refactor edildi: eski monolitik blok, `_set_single_video_sources` / `_set_playlist_video_source` yardımcılarına bölündü.

**`src/utils.py`:**
- `get_video_root`, `is_path_inside_video_root`, `normalize_video_path`, `_is_video_file`, `get_local_video_items`
- `get_video_paths` yeni `get_local_video_items` üzerinden yeniden yazıldı (geriye uyumlu imza, `folder=None`)
- `ConfigUtil._applyDefaults` (yeni)
- Sabitler: `LOCAL_VIDEO_ITEM_FOLDER`, `LOCAL_VIDEO_ITEM_VIDEO`, `LOCAL_VIDEO_SUPPORTED_EXTENSIONS`

**`src/gui/control.py`:**
- Playlist modu: `_valid_playback_mode` (static), `set_playback_mode_combo`, `get_selected_playback_mode`
- Klasör gezinme: `_ensure_current_video_folder`, `_is_current_video_root`, `_set_current_video_folder`, `_get_icon_view_item`, `_get_selected_local_video_item`, `_local_video_folder_label`, `set_local_video_nav_widgets`, `on_local_video_parent`, `on_local_video_dir`, `on_icon_view_item_activated`
- `_reload_icon_view`, `on_set_as`, `on_local_video_apply`, `on_icon_view_button_press` genişletildi (ListStore artık 2 → 4 kolon: pixbuf, ad, tam yol, öğe tipi)

**`src/commons.py`:** `CONFIG_VERSION` 4 → 5; yeni anahtarlar `playback_mode`, `playlist_folder`, `playlist_paths`, `change_on_video_end`, `change_interval_minutes`; sabitler `PLAYBACK_MODE_{SINGLE,SEQUENTIAL,RANDOM}`; `CONFIG_TEMPLATE`'e karşılıkları eklendi.

---

## 2. KOD KALİTESİ

### 2.1 Genel değerlendirme — İYİ, birkaç uyarıyla

Genel kod kalitesi upstream ortalamasının **üzerinde**: playlist mantığı ayrı dosyaya çıkarılmış, yeni yardımcı fonksiyonlar küçük ve tek işlevli, log önekleri (`[Playlist]`, `[LocalVideo]`) upstream'in `[Config]`/`[GUI]` konvansiyonuyla uyumlu, hata yönetimi çoğunlukla dar `except` kullanıyor.

### 2.2 God-file riski — ORTA (izlenmeli)

| Dosya | master | branch | Büyüme |
|-------|-------:|-------:|-------:|
| `video_player.py` | 610 | **793** | +30% |
| `control.py` | 537 | **717** | +34% |
| `utils.py` | 550 | **649** | +18% |

- **`video_player.py` (793 satır):** `VideoPlayer` sınıfı artık tek başına şunları taşıyor — tekli video, playlist orkestrasyonu (ilerletme, olay bağlama, hata sayacı), statik duvar kağıdı üretimi, DBus arayüzü, monitör yönetimi. **SRP ihlali.** Playlist'in *veri* katmanı (`VideoPlaylist`) doğru şekilde ayrılmış, ancak *kontrol* katmanı (`_advance_playlist`, `_on_playlist_*`, `_attach_playlist_events`, `playlist_error_count`) `VideoPlayer` içinde. Öneri: bir `PlaylistController` sınıfına çıkarılabilir.
- **`control.py` (717 satır):** `ControlPanel` upstream'de zaten şişkindi; klasör gezinme mantığı satır içine eklenerek büyüdü. Navigasyon durumu (`current_video_folder`, `video_root`, sınır kontrolleri) ayrı bir küçük yardımcıya taşınabilir.

### 2.3 Tekrar eden kod — GERÇEK, düzeltilmeli (DRY)

1. **Desteklenen uzantı kümesi iki yerde tanımlı, birebir aynı:**
   - `playlist.py` → `VideoPlaylist.SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}`
   - `utils.py` → `LOCAL_VIDEO_SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}`
   → Tek kaynağa (`commons.py`) taşınmalı. İleride biri güncellenip diğeri unutulursa sessiz tutarsızlık doğar.

2. **Yol normalizasyon / video-doğrulama mantığı çift:**
   - `playlist.py._normalize_path` + `_is_valid_video` (sadece `abspath`/`expanduser`)
   - `utils.py.normalize_video_path` + `_is_video_file` (`realpath` + sandbox kontrolü)
   → İkisi benzer işi yapıyor ama **farklı güvenlik seviyelerinde** (bkz. Bölüm 4.1). Ortak bir yardımcıda birleştirmek hem tekrarı hem güvenlik tutarsızlığını çözer.

### 2.4 Docstring / stil uyumu — KISMEN

- Upstream zaten docstring açısından fakir; yeni kod da çoğunlukla docstring'siz. **`VideoPlaylist` gibi yeni bir public sınıf en azından sınıf-düzeyi docstring hak ediyor** (mod semantiği, sandbox uygulamıyor uyarısı vb.).
- İsimlendirme upstream'e uyumlu (snake_case, `_private` önekleri, `CONFIG_KEY_*` sabitleri).
- `reset_video_transform` içindeki geniş `except Exception` VLC bağlamında kabul edilebilir (log'a `debug` seviyesinde düşüyor).

---

## 3. TEST DURUMU

### 3.1 Mevcut durum — TEST YOK

Repoda hiçbir test altyapısı yok: `pytest.ini`/`tox.ini`/`conftest.py` yok, `tests/` dizini yok, `requirements.txt`'te `pytest` yok, meson'da test hedefi yok. **`VideoPlaylist`, klasör gezinme ve crop reset için sıfır test kapsamı.**

İyi haber: `VideoPlaylist`, `is_path_inside_video_root`, `normalize_video_path`, `get_local_video_items`, `ConfigUtil._applyDefaults` gibi çekirdek mantık **GTK/VLC'den bağımsız, saf Python** — GUI olmadan pytest ile kolayca test edilebilir.

### 3.2 Eklenmesi gereken somut senaryolar

**`tests/test_playlist.py` — `VideoPlaylist`:**
- `single` modda `next()`/`previous()` indeksi değiştirmez (aynı videoyu döndürür).
- `sequential` modda `next()` sona gelince başa sarar (`(i+1) % n`); `previous()` başta iken sona sarar.
- `random` modda `_next_random_index()` **asla mevcut indeksi seçmez** (tek elemanlı listede mevcut indeksi döndürür — sonsuz döngü yok).
- `is_empty()` boş/geçersiz girişte `True`.
- `_load_paths`: kopya yollar tekilleştirilir; geçersiz uzantı/olmayan dosya atlanır ve uyarı loglanır.
- `paths` list değilse yok sayılır (uyarı).
- `folder` geçersizse boş liste; geçerli klasörde dosyalar `str.lower` ile sıralı gelir.
- `mode` geçersizse `"single"`'a düşer.

**`tests/test_local_video_sandbox.py` — sandbox (Bölüm 4):**
- `is_path_inside_video_root`: kök içi dosya `True`; kök dışı dosya `False`; `../` traversal denemesi `False`.
- `normalize_video_path`: kök dışına işaret eden **symlink** `None` döndürür (symlink escape engellenmeli).
- `normalize_video_path`: `None`/boş/dizin-olmayan girişte `None`.
- `get_local_video_items`: klasörler önce, videolar sonra; her ikisi `display_name.lower()` sıralı; kök dışı öğeler atlanır.
- `VIDEO_WALLPAPER_DIR`'i `tmp_path`'e monkeypatch ederek izole çalıştırılmalı.

**`tests/test_config_migration.py` — geriye uyumluluk (Bölüm 5):**
- v4 config → `_applyDefaults` sonrası 5 yeni playlist anahtarı eklenir, `version` 5 olur, mevcut değerler korunur.
- v3 config → `_migrateV3To4` + `_applyDefaults` zinciri bozmadan çalışır.
- `version` `None`/string ise `_invalid()` döner (çökme yok).
- `data_source` `None` veya dict-olmayan ise `_checkDefaultSource`/`_checkMissingMonitors` çökmeden döner.
- `playlist_paths` non-list / `playlist_folder` non-str ise `_setup_playlist` güvenli düşer.

**`tests/test_crop_reset.py` — crop reset (fake VLC player ile):**
- `reset_video_transform` üç çağrıyı (`video_set_crop_geometry(None)`, `video_set_aspect_ratio(None)`, `video_set_scale(0)`) yapar.
- Herhangi bir çağrı istisna fırlatırsa diğerleri yine de çalışır (döngü yutar).
- `centercrop` başında `reset_video_transform` çağrılır (mock ile doğrula) — playlist geçişinde önceki crop kalıntısı temizlenir.

**`tests/test_playlist_skip.py` — bozuk video atlama:**
- `_advance_playlist(is_error=True)` her hatada `playlist_error_count` artırır; sayı `len(playlist)`'e ulaşınca ilerlemeyi durdurur (sonsuz döngü yok).
- Başarılı ilerleme sayacı sıfırlar.

---

## 4. GÜVENLİK

### 4.1 Sandbox mantığı — SAĞLAM, ama katmanlar arası TUTARSIZ

Sandbox `utils.py`'de doğru kurulmuş:

```python
def is_path_inside_video_root(candidate):
    root = get_video_root()                              # realpath(VIDEO_WALLPAPER_DIR)
    candidate = os.path.realpath(os.path.expanduser(candidate))
    return os.path.commonpath([root, candidate]) == root
```

- **Symlink escape → ENGELLENMİŞ.** `realpath` sembolik bağları *commonpath kontrolünden önce* çözdüğü için, Hidamari klasörü içindeki kök-dışına işaret eden bir symlink çözülmüş gerçek yola göre reddedilir. ✅
  *Yan etki:* Klasör içindeki meşru symlink'li videolar da reddedilir (fonksiyonel kısıt, güvenlik açısından muhafazakâr — kabul edilebilir, dokümante edilmeli).
- **Path traversal (`../`) → ENGELLENMİŞ.** realpath + commonpath ikilisi `..` bileşenlerini çözüp kök dışına çıkışı yakalar. ✅
- **`ValueError` yönetimi:** Farklı sürücü/mount (`commonpath` `ValueError` atar) durumları `try/except` ile `False`'a düşüyor. ✅

**BULGU (düşük/orta önem) — Sandbox yalnızca GUI katmanında zorunlu, oynatıcı katmanında DEĞİL:**
`VideoPlaylist._normalize_path` sadece `os.path.abspath(os.path.expanduser(...))` yapıyor; `is_path_inside_video_root` **çağrılmıyor**. Yani `VideoPlaylist`, config'ten gelen `playlist_folder`/`playlist_paths` değerlerini sandbox uygulamadan yükler. GUI her zaman güvenli yol yazsa da, **elle düzenlenmiş bir config** (`~/.config/hidamari/config.json`) keyfi bir klasörü oynatabilir. Yerel bir uygulama için istismar yüzeyi dar (kullanıcı kendi config'ini düzenliyor) ama savunma-derinlik ilkesi ihlal ediliyor. Öneri: `VideoPlaylist`'e opsiyonel `path_validator` enjekte et veya `_setup_playlist` içinde yolları `normalize_video_path`'ten geçir.

### 4.2 Race condition (TOCTOU) — DÜŞÜK risk

`normalize_video_path` ile kontrol ile VLC'nin dosyayı açması arasında bir zaman penceresi var (kontrol-et-sonra-kullan). Ağ paylaşımı/symlink değişimiyle teorik olarak sömürülebilir ama yerel tek-kullanıcılı duvar kağıdı bağlamında pratik risk düşük. Not olarak bırakılabilir.

### 4.3 Bozuk video atlama — unhandled exception riski DÜŞÜK

- `_probe_video_dimensions` dar `except (CalledProcessError, ValueError, OSError)` ile sarılı, `(None, None)` döner. ✅
- `_advance_playlist` hata sayacıyla sınırlı (`playlist_error_count >= len(playlist)` → durur), sonsuz döngü yok. ✅
- `_on_playlist_end_reached`/`_on_playlist_error` VLC callback thread'inden `GLib.idle_add` ile ana döngüye devrediyor — doğru pattern. `idle_add` handler'ları `False` döndürüp kendini kaldırıyor. ✅
- **Küçük boşluk:** `_set_window_video_source` içindeki `window.media_new(source)` / `set_media` çağrıları `try` ile sarılı değil. VLC'nin burada istisna atması olası değil ama teorik olarak bir bozuk kaynak callback zincirini kesebilir. Testte gözlenmeli.

---

## 5. GERİYE UYUMLULUK

### 5.1 Config migration / fallback — GÜÇLENDİRİLMİŞ

`e751519` config yönetimini birden çok yerden **daha sağlam** hale getirdi:

- **Paylaşılan-referans hatası düzeltildi:** `_migrateV3To4` artık `deepcopy(CONFIG_TEMPLATE[...])` kullanıyor (önce şablon sözlüğü doğrudan referanslanıyordu — tüm config'ler aynı iç sözlüğü paylaşabilirdi). `_applyDefaults` de `deepcopy` ile ekliyor. ✅
- **Yeni `_applyDefaults`:** Eksik anahtarları şablondan tamamlıyor ve `version`'ı `CONFIG_VERSION`'a çekiyor. v5 için ayrı bir `_migrateV4To5` fonksiyonu yok — ancak yeni anahtarların tümü **eklemeli (additive)** olduğu için bu güvenli; eski v4 config'ler bozulmadan 5 yeni playlist anahtarını kazanıyor.
- **`None`/bozuk `version` yönetimi:** Eskiden `config.get("version") <= 3` ifadesi `version` `None` ise `TypeError` ile çökerdi. Artık `config.get("version", 0)` + `isinstance(..., int)` kontrolü → bozuk config `_invalid()`'e düşüyor. ✅
- **`data_source` sertleştirmesi:** `_checkDefaultSource` ve `_checkMissingMonitors` artık `data_source`'un `None` veya dict-olmayan olma ihtimaline karşı korumalı; değerlerin `str` olup olmadığını kontrol ediyor. ✅
- **`_normalize_data_source`:** Eski string `data_source` veya eksik `'Default'` anahtarı güvenli şekilde `{'Default': ...}`'a normalize ediliyor.

### 5.2 Eksik — bu edge-case'ler test EDİLMEMİŞ

Kod savunmacı yazılmış ama **hiçbiri testle doğrulanmamış.** Yukarıdaki `test_config_migration.py` senaryoları (v3→, v4→, `None` version, dict-olmayan `data_source`, non-list `playlist_paths`) mutlaka eklenmeli — config migration bir kez bozulursa kullanıcının kayıtlı duvar kağıdı ayarları kaybolur, bu yüksek etkili bir regresyon sınıfıdır.

---

## 6. CI/CD

**Mevcut durum:** Ne fork'ta ne de upstream'de `.github/workflows/` var. Hiç otomatik kontrol yok.

Aşağıdaki minimal workflow bu repoyla birlikte **`.github/workflows/ci.yml`** olarak yazıldı. GTK/VLC sistem bağımlılıkları CI'da tam kurulmadan `import` edilemeyeceği için, çalıştırma **derleme kontrolü (`py_compile`) + lint (`ruff`) + saf-Python testleri (`pytest`)** ile sınırlı tutuldu. GUI/VLC gerektiren modüller pytest tarafında import edilmemeli (test dosyaları yalnızca `playlist.py` gibi bağımsız modülleri hedeflemeli).

Bkz: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

---

## 7. UPSTREAM PR HAZIRLIĞI

### 7.1 Upstream'in mevcut durumu

- **CONTRIBUTING.md yok, CHANGELOG yok, CI yok, PR şablonu yok.** Katkı süreci gayri resmi.
- **Commit mesaj stili karışık:** upstream'de `feature:`, `fix:`, `change:`, `Fix ...`, `Multi monitor feature (#153)` gibi tutarsız biçimler var. Fork'un **conventional-commit** stili (`feat(ui):`, `fix(player):`) aslında upstream'den **daha temiz** — sorun olmaz, hatta iyileştirme.
- Sürüm notları `data/io.github.jeffshee.Hidamari.appdata.xml.in` içinde tutuluyor (ayrı CHANGELOG yerine).

### 7.2 PR açmadan önceki eksikler

1. **Test yok** — en az `VideoPlaylist` + sandbox + migration için pytest (Bölüm 3). Maintainer güveni için kritik.
2. **UI kanıtı** — mod seçici ve klasör gezinme için ekran görüntüsü/GIF (upstream görsel özelliklerde bunu bekliyor, bkz. #240 screenshot commit'i).
3. **appdata.xml sürüm notu** — yeni özellikler için `<release>` girdisi.
4. `change_interval_minutes` config anahtarı tanımlı ama koda bağlanmamış görünüyor (yalnızca `change_on_video_end` kullanılıyor) — ya bağla ya PR'dan çıkar; yarım özellik review'da soru işareti yaratır.

   **Karar (2026-07-05): ÇIKARILDI.** `change_interval_minutes` anahtarı `feature/playlist-support` dalında hiçbir yerden okunmuyordu (`git grep` yalnızca `commons.py`'deki tanım + template girdisini buldu) ve onu ayarlayacak bir UI öğesi de yoktu. Timer'a bağlamak; `change_on_video_end` ile çakışma yönetimi, config-reload/quit'te temizlik ve yeni bir UI spinner'ı gerektiren, kendi başına test isteyen ayrı bir özelliktir — bir P0 temizliğinin kapsamını aşar. Yarım/ölü bir config anahtarını PR'da bırakmak review'da gereksiz soru yaratacağı için anahtar `commons.py`'den (hem sabit tanımı hem `CONFIG_TEMPLATE` girdisi) kaldırıldı; ekleme-tabanlı (additive) bir anahtar olduğundan kaldırılması eski config'leri bozmaz (varsa artık okunmayan anahtar zararsızca kalır). İhtiyaç olursa ilerleyen bir sürümde UI + timer ile birlikte yeniden eklenebilir.
5. Bölüm 2.3'teki DRY tekrarını ve Bölüm 4.1'deki sandbox tutarsızlığını PR öncesi temizle.

### 7.3 Tek PR mı, ayrı PR mı? → **İKİ AYRI (stacked) PR öner**

**Gerekçe:**

- İki dal doğal olarak **stacked**: `local-video`, `playlist-support`'un üstüne kurulu (onun config anahtarlarına ve player refactor'una bağımlı).
- **PR #1 = `playlist-support`** kendi başına anlamlı ve self-contained: playlist motoru + oynatma modu seçici + **riskli kısım olan config migration ve `data_source.setter` refactor'u**. Bu PR'ı önce/ayrı incelemek, migration hatalarını UI gürültüsünden izole eder.
- **PR #2 = `local-video`** (#1 merge sonrası veya #1'e dayalı stacked): yalnızca klasör gezinme + sandbox. Diff temiz kalır (~+350 satır), review'cu tek bir konuya odaklanır.
- Tek PR'da birleştirmek 783 satır + 6 dosya + config migration + UI'yi aynı anda inceletir; büyük, riskli ve yavaş review demektir. Maintainer tek PR isterse yapılabilir ama **varsayılan öneri ayrı.**

---

## 8. SONRAKI ADIMLAR (öncelik sıralı, her biri ~tek oturum)

**P0 — Güvenlik & doğruluk (önce bunlar):**
1. `VideoPlaylist`'e sandbox uygula: `_setup_playlist` içinde `playlist_folder`/`playlist_paths` yollarını `normalize_video_path`'ten geçir (Bölüm 4.1).
2. Desteklenen uzantı kümesini `commons.py`'de tek kaynağa taşı; `playlist.py` ve `utils.py` oradan alsın (Bölüm 2.3).

**P1 — Test altyapısı (regresyon kalkanı):**
3. `pytest`'i `requirements.txt`/dev-deps'e ekle + `tests/` iskeleti + `VIDEO_WALLPAPER_DIR` için `tmp_path` fixture'ı.
4. `tests/test_playlist.py` yaz (Bölüm 3.2).
5. `tests/test_local_video_sandbox.py` yaz — özellikle symlink-escape ve `../` traversal senaryoları.
6. `tests/test_config_migration.py` yaz — v3→/v4→/None-version/dict-olmayan-data_source.
7. `tests/test_crop_reset.py` + `tests/test_playlist_skip.py` (fake VLC player ile).

**P2 — CI & kod sağlığı:**
8. `.github/workflows/ci.yml`'i yeşile çıkar (ruff uyarılarını temizle, pytest'i bağla).
9. Playlist *kontrol* mantığını `VideoPlayer`'dan bir `PlaylistController`'a çıkar (god-file, Bölüm 2.2).
10. `VideoPlaylist` ve sandbox yardımcılarına sınıf/fonksiyon docstring'leri ekle; symlink-red yan etkisini dokümante et.

**P3 — Upstream PR hazırlığı:**
11. `change_interval_minutes`'ı ya bağla ya çıkar (Bölüm 7.2/4).
12. Mod seçici + klasör gezinme için ekran görüntüsü/GIF hazırla; `appdata.xml`'e `<release>` girdisi ekle.
13. PR #1 (`playlist-support`) aç → merge sonrası PR #2 (`local-video`) aç (Bölüm 7.3).
