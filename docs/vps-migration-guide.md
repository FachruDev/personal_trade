# Tutorial pindah Trading Bot ke VPS

Panduan ini memindahkan source code, audit data, snapshot order book, macro/news
context, dan paper-run evidence dari komputer lokal ke VPS. Bot tetap **Binance
Spot dry-run** selama proses ini.

## Sebelum mulai

Siapkan VPS Linux dengan Docker Engine, Docker Compose v2, Git, ruang disk yang
cukup untuk repository dan arsip state, serta jam sistem yang tersinkronisasi.

Jangan commit atau kirim melalui chat:

- `.env`;
- Binance API key dan secret;
- FRED, NewsAPI, CoinGecko, OpenAI, Gemini, atau DeepSeek key;
- password Freqtrade atau JWT secret.

Dashboard dan API Compose saat ini dibatasi ke `127.0.0.1`. Setelah pindah,
akses dashboard sebaiknya melalui SSH tunnel sampai reverse proxy, TLS, dan
autentikasi remote dirancang secara terpisah.

## 1. Buat snapshot portabel di komputer lama

Pastikan PostgreSQL Docker aktif, lalu jalankan dari root project:

```powershell
.\scripts\export-portable-state.ps1
```

Perintah membuat `portable-state/manifest.json` dan file PostgreSQL `.dump`.
Paket ini mencakup data aplikasi yang menentukan hasil riset dan audit:

- event audit dan keputusan risiko;
- paper-run heartbeat serta identity strategi;
- snapshot order book;
- global market, macro, news, dan AI shadow context;
- SQLite trade database Freqtrade bila ditemukan.

Untuk ikut membawa candle historis demi backtest yang sama di VPS, gunakan:

```powershell
.\scripts\export-portable-state.ps1 -IncludeHistoricalData
```

Data historis dapat membuat repository sangat besar. Gunakan Git LFS atau
penyimpanan backup terpisah bila ukurannya tidak lagi nyaman untuk Git biasa.

## 2. Buat perpindahan terencana

Untuk menghindari dua bot berjalan bersamaan, hentikan bot sumber sesaat sebelum
mengambil snapshot terakhir:

```powershell
docker compose stop freqtrade api web
.\scripts\export-portable-state.ps1
```

PostgreSQL dan Redis boleh tetap menyala agar export dapat dijalankan. Jangan
menjalankan Freqtrade kembali di komputer lama setelah bot VPS aktif.

Sistem mendeteksi jeda paper-run dan order-book. Perpindahan yang melewati batas
kontinuitas dapat membuat segmen evidence baru. Anggap evidence akan dimulai
ulang bila perpindahan memerlukan downtime panjang; ini lebih aman daripada
mengklaim bukti kontinu yang tidak benar.

## 3. Simpan source dan state ke repository private

Periksa dulu file yang akan dikirim:

```powershell
git status
git add portable-state scripts/export-portable-state.ps1 scripts/import-portable-state.ps1 docs/vps-migration-guide.md
```

Tambahkan perubahan source lain yang memang ingin Anda simpan, lalu commit dan
push ke repository private. Pastikan `.env` tidak muncul pada `git status`.

Private repository membantu membatasi akses, tetapi bukan pengganti secret
manager. Bila sebuah key pernah tidak sengaja masuk commit, segera revoke/rotate
key tersebut; menghapus file pada commit baru tidak menghapusnya dari riwayat.

## 4. Siapkan VPS

Clone repository pada VPS dan buat `.env` baru secara lokal. Salin nilainya
melalui jalur aman yang Anda kelola, jangan commit file tersebut.

Mulailah dengan environment paper:

```text
TRADING_ENVIRONMENT=paper
FREQTRADE_PROFILE_CONFIG=/freqtrade/user_data/config/profiles/paper-conservative.json
FREQTRADE_STRATEGY=LimitedRiskRegimeRiskStrategy
```

Pastikan waktu VPS tersinkronisasi sebelum memulai container.

## 5. Restore state sebelum menjalankan bot

Di VPS, dari root project, restore paket yang sudah ada di `portable-state/`:

```powershell
.\scripts\import-portable-state.ps1 -Source .\portable-state -Force
```

Script ini hanya menjalankan PostgreSQL dan Redis, lalu menolak restore jika API,
dashboard, atau Freqtrade sedang berjalan. Ini mencegah database aktif ditimpa
oleh snapshot lama.

Setelah restore selesai:

```powershell
docker compose up -d
docker compose ps
```

## 6. Verifikasi di VPS

Periksa kesehatan, sinkronisasi Binance, serta evidence yang dipulihkan:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/v1/market/binance/status
Invoke-RestMethod http://127.0.0.1:8000/v1/paper-run
Invoke-RestMethod http://127.0.0.1:8000/v1/context/orderbook/coverage
```

Pastikan `clock_synchronized` bernilai `true`, Freqtrade `healthy`, strategi dan
profile sesuai yang diharapkan, dan hanya VPS yang menjalankan bot.

## 7. Rollback

Jika verifikasi VPS gagal sebelum bot berjalan, hentikan service VPS dan tetap
biarkan bot sumber berhenti. Perbaiki VPS, restore ulang snapshot yang sama, lalu
verifikasi kembali. Jangan menyalakan dua instance Freqtrade pada pair yang sama.

Jika Anda memilih kembali ke komputer lama, gunakan snapshot terbaru dari VPS
untuk restore balik terlebih dahulu agar audit/order-book tidak bercabang.
