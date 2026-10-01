# Trading Bot Dashboard

Dashboard operator read-only untuk memantau control API dan Freqtrade dry-run.

## Menjalankan lokal

1. Pastikan stack API berjalan dari root repository.
2. Salin `.env.example` menjadi `.env` bila API tidak berjalan pada `http://127.0.0.1:8000`.
3. Jalankan `bun dev`.

Browser hanya memanggil proxy Next.js pada `/api/trading/*`; token kontrol bot dan credential exchange tidak pernah dikirim ke frontend.
