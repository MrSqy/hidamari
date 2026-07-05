# Playlist Süre Sayacı + Video-Özel Süre — Tasarım

- Tarih: 2026-07-05
- Dal: `feature/local-video-folder-navigation`
- Durum: onaylandı (implementasyon bekliyor)

## Amaç

Random/sequential playback modlarında, videonun kendi uzunluğu yerine bir
**süre sayacı** geçişi yönetsin. Genel bir varsayılan süre olsun, kullanıcı
değiştirebilsin; ayrıca her video için ayrı süre atanabilsin. Video için özel
süre atanmadıysa varsayılan kullanılsın.

## Davranış

- Random/sequential'da her video **efektif süresi** kadar gösterilir.
- **Efektif süre** = video-özel override varsa o (`0` dahil), yoksa genel varsayılan.
- Süre `> 0`: video N saniye gösterilir. Video daha kısaysa **loop'lar** (süre
  dolana kadar); daha uzunsa süre dolunca **kesilir**. Sonra sonraki videoya geçilir.
- Süre `= 0`: video **doğal sonuna** kadar oynar, sonra geçilir (mevcut davranış).
- Single mod etkilenmez (geçiş yok).

### Video başına üç durum

| Durum | Anlam |
|-------|-------|
| Override yok (dict'te anahtar yok) | Genel varsayılanı kullan |
| Override = `0` | Bu video kendi sonuna kadar oynar |
| Override = `N > 0` | Bu video N saniye gösterilir |

Genel varsayılan da `0` olabilir → tüm videolar (override'sız) sonuna kadar oynar.

## Config (`commons.py`)

**Emekliye ayrılan (kullanılmıyor):**
- `change_interval_minutes` (dakika, ölü)
- `change_on_video_end` (bool) — 0-semantiği bunun yerine geçiyor

**Yeni anahtarlar:**
- `playlist_default_interval_sec` — genel varsayılan saniye. Başlangıç değeri
  **4** (test amaçlı; her şey oturunca **30** yapılacak).
- `playlist_interval_overrides` — `{}`; `{normalize_edilmiş_path: saniye}`.

**Kurallar:**
- Değer aralığı: `0`–`3600` sn.
- Override anahtarları `normalize_video_path` (realpath) ile tutulur ki
  playlist'in kullandığı path'lerle bire bir eşleşsin.
- `_applyDefaults` eksik anahtarları eklediği için eski config'ler bozulmaz;
  emekliye ayrılan iki anahtarın kaldırılması eklemeli-güvenli.

## Player mekanizması (`video_player.py`)

- Bir video "current" olduğunda efektif süre hesaplanır (aşağıdaki saf yardımcı).
- **Süre `> 0`:** kaynak `repeat=True` (loop) ile kurulur + iptal edilebilir bir
  `GLib.timeout_add(saniye*1000, ...)` başlatılır; dolunca `_advance_playlist(False)`.
- **Süre `= 0`:** `repeat=False`; geçiş mevcut `MediaPlayerEndReached` ile olur.
- Aktif timer bir alanda tutulur (`self._interval_timeout_id`); **her geçişte,
  mod değişiminde, `reload_config`'te ve `quit_player`'da iptal edilir**
  (`GLib.source_remove`). Sızıntı olmamalı (geçmişteki CPU-leak fix'ine dikkat).
- `EndReached` handler korunur: hem `süre = 0` geçişi hem bozuk-video skip için.

### Saf yardımcı (test edilebilir)

```
effective_interval(path, default_sec, overrides) -> int
    # path overrides içinde varsa overrides[path], yoksa default_sec döndürür.
    # Dönen değer 0..3600 arasına clamp'lenir; geçersiz/None girişte default.
```

Bu fonksiyon GTK/VLC'den bağımsız → pytest ile test edilir.

## GUI (`control.py` + `assets/control.ui`)

- **Varsayılan süre:** mod combo'sunun yanına bir spin butonu — "Varsayılan süre
  (sn)", aralık 0–3600. Altına açıklama etiketi: **"0 = video sonuna kadar oynat"**.
  Değişince `playlist_default_interval_sec` güncellenir ve config kaydedilir.
- **Video-özel süre:** icon view'da bir **videoya** sağ tık → menüde "Süre ayarla…"
  → küçük dialog:
  - Spin (0–3600); yanında not: "0 = bu video sonuna kadar".
  - **"Varsayılana dön"** butonu → o path'in override'ını siler (varsayılana döner).
  - Kaydet → `playlist_interval_overrides[normalize(path)] = değer`, config kaydedilir.
  - Klasör öğelerinde bu menü öğesi gösterilmez (yalnızca video).

## Hata yönetimi / kenar durumlar

- `overrides`'ta artık playlist'te olmayan path'ler zararsızca yok sayılır.
- `overrides` dict değilse / değerler int değilse: yardımcı varsayılana düşer,
  uyarı loglanır.
- Süre 0 iken video zaten uzun → mevcut EndReached akışı; timer başlatılmaz.
- Timer aktifken kullanıcı modu single'a çevirirse timer iptal edilir.

## Test

- `tests/test_interval.py`: `effective_interval` için — override yok → default;
  override = 0 → 0; override = N → N; bozuk overrides → default; clamp (>3600, <0).
- Timer/loop/GUI kısmı manuel doğrulama (kullanıcının X11/GNOME ortamında):
  4sn'de geçiş, kısa videonun loop'laması, per-video override'ın çalışması,
  0 → sonuna kadar.

## Kapsam / sıra

1. Config anahtarları (commons) — küçük.
2. `effective_interval` yardımcısı + testleri — küçük.
3. Player: timer + repeat mantığı + iptal — orta.
4. GUI: varsayılan spin + not — küçük.
5. GUI: sağ-tık dialog + override depolama + reset — orta (en ağır parça).
