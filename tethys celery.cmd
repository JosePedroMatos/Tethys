del celerybeat.pid
start cmd /k "celery -A tethys beat -l info"
start cmd /k "celery -A tethys worker -Q train -n train -l info --pool=solo"
start cmd /k "celery -A tethys worker -Q download -n download -l info --pool=solo" && exit

