# DEALData

DEALData regroupe les services Django qui portent les donnees metier de la
plateforme DEAL:

- `core_layer`: projets, membres, objets observes et experiences.
- `gps_layer`: capteurs GPS, donnees GPS brutes, positions traitees et
  evenements WildFi `raw.gps` decodes par DEALIoT.
- `sensor_layer`: capteurs generiques, mesures associees et evenements WildFi
  `raw.sensor` decodes par DEALIoT.

Le depot est prevu comme fournisseur de donnees pour `Smartappli/DEALIoT` et
comme ensemble de modules deployables derriere `Smartappli/DEALHost`.

Les donnees WildFi arrivent via les contrats DEALIoT suivants:

- `raw.gps` vers `gps_data.WildFiGPSFix`
- `raw.sensor` vers `sensor_data.WildFiDecodedSensorEvent`

Ces tables conservent l'enveloppe DEALIoT (`device_id`, `timestamp`,
`source`, `mqtt_topic`, `ingested_at`) avec le payload decode et les
metadonnees de transport.

## Verification locale

Depuis la racine du depot, avec les dependances installees dans `.venv`:

```powershell
.\.venv\Scripts\python.exe -m compileall -q core_layer gps_layer sensor_layer
cd core_layer; ..\.venv\Scripts\python.exe manage.py check; ..\.venv\Scripts\python.exe -m pytest . --ds=core.settings -q
cd ..\gps_layer; ..\.venv\Scripts\python.exe manage.py check; ..\.venv\Scripts\python.exe -m pytest . --ds=gps.settings -q
cd ..\sensor_layer; ..\.venv\Scripts\python.exe manage.py check; ..\.venv\Scripts\python.exe -m pytest . --ds=sensor.settings -q
```
