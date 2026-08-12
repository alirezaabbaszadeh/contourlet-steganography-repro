# 32c64g host preparation intent

Target host decision, frozen before any benchmark results on the resized host:

- 32 logical CPUs
- 64 GiB nominal RAM
- 100 GB decimal storage
- 1024 Mb/s shared network bandwidth
- reserve 2 CPUs for OS/control/monitoring
- first measured worker trial: 16
- fallback ladder: 12 -> 8 -> 4
- scale-up ladder: 20 -> 24 -> 28 -> 30
- maximum workers: 30
- scientific worker internals remain single-threaded

This file records intent only. Production execution remains blocked until the resized host is booted, hardware identity is verified, worker tuning is measured with fresh caches, and all runtime/control gates pass.
