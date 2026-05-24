# DEALData

DEALData regroupe les services Django qui portent les donnees metier de la
plateforme DEAL:

- `core_layer`: projets, membres, objets observes et experiences.
- `gps_layer`: capteurs GPS, donnees GPS brutes et positions traitees.
- `sensor_layer`: capteurs generiques et mesures associees.

Le depot est prevu comme fournisseur de donnees pour `Smartappli/DEALIoT` et
comme ensemble de modules deployables derriere `Smartappli/DEALHost`.

## Verification locale

Depuis la racine du depot, avec les dependances installees dans `.venv`:

```powershell
.\.venv\Scripts\python.exe -m compileall -q core_layer gps_layer sensor_layer
cd core_layer; ..\.venv\Scripts\python.exe manage.py check; ..\.venv\Scripts\python.exe -m pytest . --ds=core.settings -q
cd ..\gps_layer; ..\.venv\Scripts\python.exe manage.py check; ..\.venv\Scripts\python.exe -m pytest . --ds=gps.settings -q
cd ..\sensor_layer; ..\.venv\Scripts\python.exe manage.py check; ..\.venv\Scripts\python.exe -m pytest . --ds=sensor.settings -q
```
