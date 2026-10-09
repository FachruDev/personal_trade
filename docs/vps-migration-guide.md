# Panduan VPS: menjalankan 56 hari paper run dan membawa hasilnya pulang

Panduan ini untuk menjalankan bot **Binance Spot dry-run** (uang virtual) di VPS Linux selama 24 jam, lalu
mengambil seluruh hasilnya kembali ke komputer lokal. Tidak ada order riil di jalur mana pun di sini.

Alur singkat:

```text
komputer lokal  ──(git)──►  VPS: deploy, jalan 56 hari  ──(portable state)──►  komputer lokal: hasil
```

## 0. Pilih skenario awal

| Skenario | Kapan dipilih |
| --- | --- |
| **A. Mulai segar di VPS** (disarankan) | Bot lokal baru dipakai untuk uji coba. Bukti 56 hari memang baru dihitung sejak VPS berjalan tanpa putus. |
| **B. Bawa state lokal ke VPS** | Anda ingin ikut membawa audit, snapshot order book (riset empat minggu), dan konteks makro/berita yang sudah terkumpul. |

Hitungan 56 hari selalu mulai dari heartbeat pertama pada segmen kontinu terakhir. Perpindahan yang lebih
lama dari 30 menit memulai segmen baru; itu disengaja dan lebih jujur daripada mengklaim bukti yang tidak
kontinu.

## 1. Pilih dan siapkan VPS

- **Wilayah**: pilih Singapura, Tokyo, atau Eropa (Frankfurt, Amsterdam). **Jangan wilayah Amerika Serikat**:
  Binance menolak IP data center AS dengan HTTP 451 dan bot tidak akan mendapat data pasar.
- Spesifikasi: Ubuntu 22.04 atau 24.04, 2 vCPU, RAM 2–4 GB, disk 25 GB atau lebih.
- Akses: login SSH dengan kunci (bukan kata sandi).

Satu kali di VPS (ganti `USER` dengan nama pengguna Anda):

```bash
# Docker Engine + Compose v2 (ikuti dokumentasi resmi Docker untuk Ubuntu), lalu:
sudo usermod -aG docker "$USER"            # keluar dan masuk SSH lagi setelah ini
sudo systemctl enable --now docker

# Firewall: hanya SSH dari luar. Dashboard diakses lewat SSH tunnel, bukan port publik.
sudo ufw allow OpenSSH && sudo ufw enable

# Jam harus sinkron: selisih lebih dari 2 detik dari Binance akan ditolak oleh preflight.
sudo timedatectl set-ntp true

# RAM 2 GB: tambahkan swap supaya build image web tidak kehabisan memori.
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Bila server dipakai bersama layanan lain

Server yang sudah menjalankan database, web server, atau container lain perlu perhatian ekstra:

- `compose.vps.yaml` membatasi memori tiap container (total batas sekitar 3,4 GB, pemakaian normal jauh lebih
  rendah) dan memindahkan Freqtrade UI ke port 18080. Ubah `FREQTRADE_UI_PORT` atau `API_PORT` di `.env` bila
  port itu juga terpakai; `vps-preflight.sh` memeriksa bentrok port.
- Build image web memakai memori besar. Tambahkan swap dulu dan bangun satu per satu:
  `bash scripts/vps-compose.sh build api freqtrade` lalu `bash scripts/vps-compose.sh build web`.
- Periksa pemakaian nyata setelah sehari (`docker stats --no-stream`) dan sesuaikan batas memori.
- Bot ini mengumpulkan bukti berkelanjutan: reboot atau beban berat di server bersama memutus kontinuitas
  (gap lebih dari 30 menit memulai segmen baru). Untuk 56 hari yang bersih, VPS khusus lebih aman.

## 2. Deploy

```bash
git clone <URL-repositori-private> trading_bot && cd trading_bot
git checkout development                      # atau branch yang sudah Anda merge

bash scripts/vps-init-env.sh                  # membuat .env dengan rahasia acak; tidak ada yang dicetak
sudo chown -R 1000:1000 freqtrade             # pengguna di dalam container Freqtrade adalah uid 1000
bash scripts/vps-preflight.sh                 # semua baris harus [ ok ] sebelum lanjut
```

`.env` dibuat langsung di VPS dengan strategi `DailyTrendVolStrategy`, profil `paper-daily-trend`, dan
`TRADING_ENVIRONMENT=paper`. Binance API key **tidak diperlukan** untuk paper trading; biarkan kosong.
Jangan menyalin `.env` dari komputer lokal.

**Skenario B** (bawa state) lakukan ini sebelum menyalakan layanan; lihat bagian 5, jalur lokal → VPS.

Nyalakan:

```bash
bash scripts/vps-compose.sh up -d --build
bash scripts/vps-compose.sh ps
```

`vps-compose.sh` menambahkan `compose.vps.yaml`: semua layanan restart otomatis setelah crash atau reboot,
dan log container dirotasi agar tidak memenuhi disk.

## 3. Verifikasi

```bash
curl -s http://127.0.0.1:8000/health
bash scripts/paper-run-summary.sh
```

Heartbeat pertama muncul sampai 15 menit setelah menyalakan; sebelum itu status masih menampilkan strategi
lama atau `not_started`. Pastikan kemudian `strategy: DailyTrendVolStrategy`, `revision: daily-trend-v2`,
dan `status: collecting`.

Dashboard dan Freqtrade UI hanya tersedia di `127.0.0.1` VPS. Dari komputer lokal buka SSH tunnel:

```bash
ssh -L 3000:127.0.0.1:3000 -L 8080:127.0.0.1:18080 USER@ALAMAT-VPS
```

Di VPS, Freqtrade UI terbit di port **18080** (bukan 8080, yang sering sudah terpakai di server bersama);
tunnel di atas memetakannya kembali ke `localhost:8080` di komputer Anda, sehingga tautan di dashboard tetap
bekerja. Buka `http://localhost:3000` (dashboard) dan `http://localhost:8080` (Freqtrade UI, login dengan
`FREQTRADE_API_USERNAME` dan `FREQTRADE_API_PASSWORD` dari `.env` VPS).

## 4. Operasi selama 56 hari

**Backup harian** (di luar repositori, menyimpan 14 terakhir). Tambahkan lewat `crontab -e`:

```cron
17 3 * * * cd /home/USER/trading_bot && bash scripts/vps-backup.sh --keep 14 >> /home/USER/trading-bot-backups/backup.log 2>&1
```

Cek berkala:

```bash
bash scripts/paper-run-summary.sh                 # status bukti, posisi terbuka, jumlah event audit
bash scripts/vps-compose.sh logs --tail 100 freqtrade
```

Henti darurat atau lanjut entri baru tanpa menaruh token di riwayat shell:

```bash
bash scripts/control-bot.sh stop
bash scripts/control-bot.sh resume
```

**Jangan** selama masa bukti: mengubah `DailyTrendVolStrategy.py`, `PAPER_RUN_REVISION`, atau profil. Itu memulai
segmen bukti baru. Memperbarui kode lain (dashboard, dokumentasi) aman, tetapi rebuild tetap
`bash scripts/vps-compose.sh up -d --build`. Reboot VPS aman: container menyala sendiri, tetapi gap lebih
dari 30 menit memutus kontinuitas.

Folder `freqtrade/db/` menyimpan database trade dry-run. Ia berada di luar container sehingga tetap ada saat
container dibuat ulang. Jangan menghapusnya selama paper run berjalan.

## 5. Memindahkan state (portable state)

Satu paket `portable-state/` berisi dump PostgreSQL (audit, heartbeat, order book, konteks), snapshot database
trade Freqtrade, `manifest.json`, dan `results-summary.json`. Format manifest sama untuk skrip PowerShell
(Windows) dan bash (Linux), sehingga paket dari satu sistem bisa dipulihkan di sistem lainnya. Rahasia tidak
pernah ikut.

Aturan keras: **hanya satu bot yang boleh berjalan**. Hentikan sumber sebelum snapshot terakhir dan jangan
menyalakannya kembali setelah tujuan aktif.

### Lokal (Windows) → VPS

Di komputer lokal:

```powershell
docker compose stop freqtrade api web
.\scripts\export-portable-state.ps1 -Destination C:\temp\state-ke-vps
scp -r C:\temp\state-ke-vps USER@ALAMAT-VPS:~/state-masuk
```

Di VPS, sebelum layanan dinyalakan:

```bash
cd ~/trading_bot
bash scripts/import-portable-state.sh --source ~/state-masuk --force
bash scripts/vps-compose.sh up -d --build
```

Impor menolak berjalan bila `api`, `web`, atau `freqtrade` sedang aktif, supaya database hidup tidak tertimpa
snapshot lama.

### VPS → lokal (mengambil hasil)

Di VPS:

```bash
cd ~/trading_bot
bash scripts/paper-run-summary.sh                      # catat ringkasannya
bash scripts/vps-compose.sh stop freqtrade api web     # hentikan bot sebelum snapshot terakhir
bash scripts/export-portable-state.sh --destination ~/hasil-paper-run
```

Di komputer lokal, pastikan stack lokal berhenti dulu, lalu:

```powershell
scp -r USER@ALAMAT-VPS:~/hasil-paper-run C:\temp\hasil-paper-run
docker compose stop freqtrade api web
.\scripts\import-portable-state.ps1 -Source C:\temp\hasil-paper-run -Force
```

Untuk **melihat** hasilnya di dashboard lokal nyalakan hanya `docker compose up -d api web`, jangan
`freqtrade`. Status paper-run akan terbaca `interrupted` karena heartbeat terakhir sudah lama, dan
`elapsed_days` terus bertambah karena dihitung dari heartbeat pertama sampai **hari ini**, jadi abaikan angka
itu setelah bot berhenti. Rentang run yang sebenarnya adalah `first_observed_at` sampai `last_observed_at`,
bersama `observations`; semuanya tersimpan di `results-summary.json` dalam paket. Database trade ada di
`freqtrade/db/` setelah impor.

Setelah hasil aman di lokal, simpan paket itu sebagai arsip (repositori private atau penyimpanan
terenkripsi). Dump berisi data audit tetapi tidak berisi rahasia.

## 6. Rollback dan masalah umum

| Gejala | Penyebab dan tindakan |
| --- | --- |
| Preflight: `could not reach api.binance.com` | Wilayah VPS diblokir (HTTP 451) atau tidak ada jalur keluar. Pindah ke wilayah non-AS. |
| Preflight: `freqtrade/db is owned by uid ...` | `sudo chown -R 1000:1000 freqtrade`. Container tidak bisa menulis database bila pemilik folder berbeda. |
| `clock drift ... limit 2000` | `sudo timedatectl set-ntp true`, tunggu beberapa menit, jalankan preflight lagi. |
| Build web berhenti karena memori | Tambahkan swap 2 GB (bagian 1). |
| Status `interrupted` setelah restart | Normal sampai heartbeat pertama (maksimal 15 menit). Bila gap lebih dari 30 menit, segmen bukti baru dimulai. |
| Impor ditolak karena layanan aktif | Hentikan `api web freqtrade` dulu. Jangan memakai `--force` untuk menimpa database yang sedang hidup. |

Bila verifikasi VPS gagal sebelum bot berjalan, hentikan layanan VPS, perbaiki, dan impor ulang paket yang
sama. Bila Anda kembali ke komputer lokal, pulihkan snapshot terbaru dari VPS lebih dulu agar audit tidak
bercabang. Jangan pernah menyalakan dua instance Freqtrade untuk pair yang sama.

## Keamanan

Jangan commit atau kirim lewat chat: `.env`, Binance API key dan secret, FRED/NewsAPI/CoinGecko/AI key,
password Freqtrade, atau JWT secret. Repositori private bukan secret manager: bila sebuah kunci pernah masuk
commit, cabut dan buat ulang kuncinya. Dashboard dan API sengaja hanya terikat ke `127.0.0.1`; jangan membuka
port 3000, 8000, atau 8080 ke internet sebelum ada reverse proxy, TLS, dan autentikasi yang dirancang
terpisah.
