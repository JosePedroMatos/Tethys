#!/bin/bash

(
(xterm -title "Redis" -e redis-server &);
(xterm -title "Celery beat" -hold -e celery -A tethys beat -l info &);
(xterm -title "Celery download" -hold -e celery -A tethys worker -Q download -n download -l info --pool=solo &);
(xterm -title "Celery train" -hold -e celery -A tethys worker -Q train -n train -l info --pool=solo &);
(xterm -title django -hold -e python manage.py runserver)
) | parallel
exit 0
