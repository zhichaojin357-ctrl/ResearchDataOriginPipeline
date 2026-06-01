# Auto Queue Forbidden Type Guard

`auto-queue` now normalizes forbidden type variants before accepting future no-Origin candidates. It blocks variants such as `sem_image_data`, combined labels like `SEM/TEM/NMR/MS`, and Chinese `动力学`.

Focused test:

```text
D:\Python\python.exe -m pytest tests\test_auto_queue.py -q
5 passed in 0.07s
```

No real processing or Origin export was run.
