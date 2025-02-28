## ATC Controller tasks

ATC controllers runs in a celery task on the "atc" queue.

```bash
celery -A fgserver worker -Q atc
```

