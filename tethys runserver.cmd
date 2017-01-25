echo Starting Tethys...
cd startup\windows
start cmd /k "tethys django.cmd"
start cmd /k "tethys celery.cmd"
tethys opensite.cmd