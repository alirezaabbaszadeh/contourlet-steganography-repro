# 32c64g host preparation intent

Target host decision, frozen before any benchmark results on the resized host:

- 32 logical CPUs
- 64 GiB nominal RAM
- 100 GB decimal storage
- 1024 Mb/s shared network bandwidth
- reserve 3 logical CPUs by capping scientific workers at 29
- first measured worker trial: 16
- fallback ladder: 12 -> 8 -> 4
- scale-up ladder: 20 -> 24 -> 27 -> 29
- maximum workers: 29
- scientific worker internals remain single-threaded

Worker selection is data-driven. A fixed host CPU-busy percentage is not a scale-up gate. CPU percentages may remain in telemetry for diagnosis, but worker-count decisions use measured throughput per added worker together with OOM/swap evidence, memory headroom/projection, storage headroom, and I/O pressure. The 29-worker ceiling preserves three logical CPUs of scheduling capacity for the OS, control plane, monitoring, and incidental work.

This file records intent only. Production execution remains blocked until the resized host is booted, hardware identity is verified, worker tuning is measured with fresh caches, and all runtime/control gates pass.
